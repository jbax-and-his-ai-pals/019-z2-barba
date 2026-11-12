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
    ('combat','Palace 1 combat corridor','Fight normal enemies. Health is below full so beams do not mask melee hits.'),
    ('spells','All spells and techniques','Safe castle with all eight spells, up/down thrust, full meters and level 4 attack. Inferno is selected; Shift casts it. Reload F3 to refill.'),
    ('lava-ledge','Palace 6 lava ledge','Walk right off the ledge and into the lava; stop, jump and return.'),
    ('lava-surface','Standing on palace lava','Already on lava. Test moving, jumping and standing still.'),
    ('barba','Palace 6 boss encounter','Test the playable dragon against the original Palace 6 boss. Ice Barba is not implemented.'),
    ('raft','Sea crossing','Observe the dragon crossing on the original raft route; no free-flight cheat.')
]
RECIPE_FILES=['tools/state_scenarios.lua','tests/newgame.lua','tests/state_pack.lua']


def recipe_hash() -> str:
    return hashlib.sha256(b''.join((ROOT/p).read_bytes() for p in RECIPE_FILES)).hexdigest()


def create(force: bool=False) -> dict:
    rom=ROOT/'build/barba.nes'
    if not rom.exists():raise ValueError('Build the alpha first: python tools/build.py')
    digest=hashlib.sha256(rom.read_bytes()).hexdigest()
    folder=ROOT/'build/test-pack'/digest[:12]
    manifest_path=folder/'manifest.json'
    if manifest_path.exists() and not force:
        manifest=json.loads(manifest_path.read_text())
        if (manifest.get('rom_sha256')==digest and manifest.get('recipe_sha256')==recipe_hash() and manifest.get('validated')
                and (folder/'barba-test.nes').exists()
                and hashlib.sha256((folder/'barba-test.nes').read_bytes()).hexdigest()==digest
                and all((folder/s['file']).exists() and hashlib.sha256((folder/s['file']).read_bytes()).hexdigest()==s['sha256']
                        for s in manifest.get('states',[]))
                and len(manifest.get('states',[]))==len(SCENES)):
            (ROOT/'build/test-pack/current.json').write_text(json.dumps(manifest,indent=2)+'\n')
            return manifest
    folder.mkdir(parents=True,exist_ok=True)
    pack_rom=folder/'barba-test.nes'
    shutil.copyfile(rom,pack_rom)
    # The generated runner is local and ignored; the reusable scenario contains no game data.
    scenario=ROOT/'build/generate-test-states.lua'
    prefix='PACK_DIR='+json.dumps(folder.as_posix())+'\n'
    scenario.write_text(prefix+(ROOT/'tools/state_scenarios.lua').read_text())
    if run(scenario,pack_rom,60):raise ValueError('State generation failed; see build/*-error.txt')
    states=[]
    for slot,(key,title,instructions) in enumerate(SCENES,1):
        path=folder/(key+'.mss')
        data=path.read_bytes()
        if not data.startswith(b'MSS'):raise ValueError(f'Invalid Mesen state: {key}')
        states.append({'slot':slot,'id':key,'name':title,'instructions':instructions,
                       'file':path.name,'sha256':hashlib.sha256(data).hexdigest()})
    validation=ROOT/'build/validate-test-states.lua'
    validation.write_text(prefix+(ROOT/'tests/state_pack.lua').read_text())
    if run(validation,pack_rom,60):raise ValueError('State reload validation failed; see validation.txt in the pack folder')
    manifest={'rom_sha256':digest,'recipe_sha256':recipe_hash(),'emulator':'Mesen 2.1.1','folder':str(folder),
              'rom':str(pack_rom),'states':states,'validated':True}
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    (ROOT/'build/test-pack/current.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--force',action='store_true')
    args=parser.parse_args()
    try:
        manifest=create(args.force)
        print(f"Created {len(manifest['states'])} local test states: {manifest['folder']}")
    except (OSError,ValueError) as error:parser.exit(1,f'Test pack failed: {error}\n')
