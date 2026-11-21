"""Create local, version-matched Mesen test states without changing play saves."""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from emulator_test import run

ROOT=Path(__file__).resolve().parents[1]
SCENES=[
    ('castle','Starting castle','Walk, turn, duck, jump and attack with the normal starting stats.'),
    ('combat','Palace 1 combat corridor','Fight normal enemies with the five-shot diagonal volley at damaged health.'),
    ('spells','All spells and techniques','Safe castle with all eight spells, up/down thrust, full meters and level 4 attack. Press Space to cast Inferno. Reload F3 to refill.'),
    ('lava-ledge','Palace 6 lava ledge','Walk right off the ledge and into the lava; stop, jump and return.'),
    ('lava-surface','Standing on palace lava','Already on lava. Test moving, jumping and standing still.'),
    ('barba','Palace 6 boss encounter','Test the playable dragon against Lava Link in Palace 6.'),
    ('raft','Sea crossing','Observe the dragon crossing on the original raft route; no free-flight cheat.'),
    ('town','Rauru town street','Approach random outdoor wanderers, watch them flee, and test fireballs and town scorch/combo.'),
    ('boss-door','Before Palace 6 boss','Jump right over the lava ledges and keep holding Right. Barba roars on landing, then holds still for half a second before Lava Link rises.'),
    ('great-palace','Great Palace final boss','Great Palace Thunderbird / Dark Link corridor with max stats, all spells and full meters. Test Inferno, fireballs and ending progression.')
]
RECIPE_FILES=['tools/state_scenarios.lua','tests/newgame.lua','tests/state_pack.lua',
              'tools/create_test_pack.py','tools/checkpoint_sets.json','tests/checkpoint_features.lua']
RECIPES=json.loads((ROOT/'tools/checkpoint_sets.json').read_text())
EDGE_SCENES=[
    ('game-over-danger','Last life, one hit from death',
     'Palace 1 enemy nearby; one life and one health unit. Wait about four seconds for GAME OVER. Reload F1 to repeat.'),
    ('game-over','Game Over portrait',
     'Inspect the final black Link portrait immediately. Press Start to continue; reload F2 to inspect again.')
]
SETS=['core',*RECIPES['sets'],'edges']


TOWN_OW_COORDS = {
    0: (54, 46),   # Rauru
    1: (36, 2),    # Ruto
    2: (88, 8),    # Saria
    3: (75, 60),   # Mido
    4: (60, 23),   # Nabooru
    5: (33, 3),    # Darunia
    6: (99, 61),   # New Kasuto
    7: (99, 34),   # Old Kasuto
}
PALACE_OW_COORDS = {
    1: (32, 62),   # Palace 1
    2: (64, 11),   # Palace 2
    3: (98, 57),   # Palace 3
    4: (58, 59),   # Palace 4 (Maze Island)
    5: (60, 62),   # Palace 5
    6: (100, 45),  # Palace 6 (Hidden Palace)
    7: (73, 4),    # Great Palace
}
ENCOUNTER_OW_COORDS = {
    (0, 1): (82, 16),   # West Hyrule water bridge
    (0, 14): (69, 9),   # Medicine cave
    (0, 16): (62, 54),  # Myu cave
    (0, 34): (32, 40),  # West Hyrule grass
    (2, 2): (76, 21),   # Valley of Death Lizalfos
}


def checkpoint_writes(scene: dict) -> tuple[dict,dict]:
    p=RECIPES['profiles'][scene['profile']]
    expected={0x777+i:level for i,level in enumerate(p['levels'])}
    expected.update({0x783:p['magic'],0x784:p['hearts'],0x793:scene.get('keys',0),
                     0x794:6-p['placed'],0x796:p['tech']})
    expected.update({0x77B+i:int(i<p['spells']) for i in range(8)})
    expected.update({0x785+i:int(i in p['items']) for i in range(8)})
    expected.update({0x78D+i:int(i<p['placed']) for i in range(6)})
    expected.update({a:int(p['flags'].get(str(a),0)) for a in range(0x798,0x79E)})
    # Native XP tables: level 8 is terminal, never read a ninth entry.
    rom=(ROOT/'build/barba.nes').read_bytes()[16:]
    target=min([rom[0x1658+s*8+l]*256+rom[0x1670+s*8+l]
                for s,l in enumerate(p['levels']) if l<8] or [65535])
    expected.update({0x770:target//256,0x771:target%256,0x775:0,0x776:0})
    # Native $CB18: each container holds 32 units, full meter is count*32-1.
    writes={**expected,0x700:3,0x773:p['magic']*32-1,0x774:p['hearts']*32-1,
            0x76F:0,0x749:0,0x74A:0}
    world,region,number=scene['world'],scene['region'],scene['number']
    code={1:0,2:1,3:2,4:0,5:0,6:1,7:2}.get(number,0)
    prev_region=2 if (region==2 or (region==1 and number==4)) else 0
    writes.update({0x707:world,0x706:region,0x70A:prev_region,
                   0x769:3 if world in (1,2) else (5 if world==5 else 4),
                   0x561:scene['room'],0x568:max(0,number-1),0x56B:number,0x56C:code,
                   0x701:0,0x75C:scene['page'],0x704:0,0x736:0,0x73D:0,0x726:1})
    if scene.get('town') and number in TOWN_OW_COORDS:
        ow_y,ow_x=TOWN_OW_COORDS[number]
        writes.update({0x73:ow_y,0x74:ow_x})
    elif world in (3,4,5) and number in PALACE_OW_COORDS:
        ow_y,ow_x=PALACE_OW_COORDS[number]
        writes.update({0x73:ow_y,0x74:ow_x})
    elif world==0 and (region,scene['room']) in ENCOUNTER_OW_COORDS:
        ow_y,ow_x=ENCOUNTER_OW_COORDS[(region,scene['room'])]
        writes.update({0x73:ow_y,0x74:ow_x})
    if scene.get('town'):writes[0x748]=0x2C+(number%4)*2
    else:writes[0x748]=0x34+code
    writes.update({int(a):v for a,v in scene.get('entry',{}).items()})
    return writes,expected


def lua_value(value) -> str:
    if isinstance(value,dict):return '{'+','.join('['+lua_value(k)+']='+lua_value(v) for k,v in value.items())+'}'
    if isinstance(value,list):return '{'+','.join(map(lua_value,value))+'}'
    return json.dumps(value)


def scene_prefix(set_name: str) -> str:
    if set_name in ('core','edges'):return ''
    scenes=[]
    for scene in RECIPES['sets'][set_name]:
        writes,expected=checkpoint_writes(scene)
        scenes.append({**scene,'writes':writes,'expected':expected})
    return 'PACK_SCENES='+lua_value(scenes)+'\nPACK_IDS='+lua_value([s['id'] for s in scenes])+'\n'



def recipe_hash(set_name: str='core') -> str:
    files=RECIPE_FILES+(['tools/edge_scenarios.lua'] if set_name=='edges' else [])
    return hashlib.sha256(b''.join((ROOT/p).read_bytes() for p in files)).hexdigest()


def create(force: bool=False, set_name: str='core', rom_path: Path | None=None) -> dict:
    if set_name not in SETS:raise ValueError(f'Unknown checkpoint set: {set_name}')
    scenes=SCENES if set_name=='core' else (EDGE_SCENES if set_name=='edges' else
            [(s['id'],s['name'],s['instructions']) for s in RECIPES['sets'][set_name]])
    rom=rom_path or ROOT/'build/barba.nes'
    if not rom.exists():raise ValueError('Build the alpha first: python tools/build.py')
    digest=hashlib.sha256(rom.read_bytes()).hexdigest()
    folder=ROOT/'build/test-pack'/digest[:12]/set_name
    manifest_path=folder/'manifest.json'
    if manifest_path.exists() and not force:
        manifest=json.loads(manifest_path.read_text())
        if (manifest.get('set')==set_name
                and [s['id'] for s in manifest.get('states',[])]==[s[0] for s in scenes]
                and manifest.get('rom_sha256')==digest and manifest.get('recipe_sha256')==recipe_hash(set_name) and manifest.get('validated')
                and (folder/'barba-test.nes').exists()
                and hashlib.sha256((folder/'barba-test.nes').read_bytes()).hexdigest()==digest
                and all((folder/(s['id']+'.png')).exists() and (folder/s['file']).exists() and hashlib.sha256((folder/s['file']).read_bytes()).hexdigest()==s['sha256']
                        for s in manifest.get('states',[]))
                and len(manifest.get('states',[]))==len(scenes)):
            (ROOT/'build/test-pack/current.json').write_text(json.dumps(manifest,indent=2)+'\n')
            return manifest
    folder.mkdir(parents=True,exist_ok=True)
    manifest_path.unlink(missing_ok=True)  # A failed forced rebuild must never remain ready.
    pack_rom=folder/'barba-test.nes'
    shutil.copyfile(rom,pack_rom)
    # The generated runner is local and ignored; the reusable scenario contains no game data.
    scenario=ROOT/'build/generate-test-states.lua'
    prefix='PACK_DIR='+json.dumps(folder.as_posix())+'\n'+scene_prefix(set_name)
    if set_name=='edges':
        core=create(set_name='core',rom_path=rom_path)
        prefix+='SOURCE_STATE='+json.dumps((Path(core['folder'])/'combat.mss').as_posix())+'\n'
    scenario.write_text(prefix+(ROOT/('tools/edge_scenarios.lua' if set_name=='edges' else 'tools/state_scenarios.lua')).read_text())
    if run(scenario,pack_rom,60):raise ValueError('State generation failed; see build/*-error.txt')
    states=[]
    for slot,(key,title,instructions) in enumerate(scenes,1):
        path=folder/(key+'.mss')
        data=path.read_bytes()
        if not data.startswith(b'MSS'):raise ValueError(f'Invalid Mesen state: {key}')
        states.append({'slot':slot,'id':key,'name':title,'instructions':instructions,
                       'file':path.name,'sha256':hashlib.sha256(data).hexdigest(),
                       'loadout':None if set_name in ('core','edges') else RECIPES['profiles'][RECIPES['sets'][set_name][slot-1]['profile']]})
    validation=ROOT/'build/validate-test-states.lua'
    if set_name!='edges':
        validation.write_text(prefix+(ROOT/'tests/state_pack.lua').read_text())
        if run(validation,pack_rom,60):raise ValueError('State reload validation failed; see validation.txt in the pack folder')
    else:
        report=(folder/'validation.txt').read_text()
        if 'FAIL' in report or not report.rstrip().endswith('RESULT PASS'):
            raise ValueError('Edge state reload validation failed')
    manifest={'set':set_name,'rom_sha256':digest,'recipe_sha256':recipe_hash(set_name),'emulator':'Mesen 2.1.1','folder':str(folder),
              'rom':str(pack_rom),'states':states,'validated':True}
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    (ROOT/'build/test-pack/current.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--force',action='store_true')
    parser.add_argument('--rom',type=Path,help='Optional separate experimental ROM.')
    parser.add_argument('--set',choices=SETS,help='Generate only this set (default: all sets).')
    args=parser.parse_args()
    try:
        for name in ([args.set] if args.set else SETS):
            manifest=create(args.force,name,args.rom)
            print(f"Created {len(manifest['states'])} local test states: {manifest['folder']}")
        if not args.set:create(False,'core',args.rom)  # All-set generation leaves Core selected.
    except (OSError,ValueError) as error:parser.exit(1,f'Test pack failed: {error}\n')
