"""Install validated scenario states in an isolated human-test Mesen profile."""
from __future__ import annotations
import json
import shutil
from pathlib import Path
from create_test_pack import ROOT, create


def prepare() -> dict:
    manifest=create()
    folder=Path(manifest['folder'])
    slots=folder/'slots'
    slots.mkdir(exist_ok=True)
    # Slot files are disposable copies; generated masters are kept separately.
    for scene in manifest['states']:
        shutil.copyfile(folder/scene['file'],slots/f"barba-test_{scene['slot']}.mss")
    player=ROOT/'.tools/mesen-scenarios/Mesen.exe'
    player.parent.mkdir(parents=True,exist_ok=True)
    if not player.exists():shutil.copyfile(ROOT/'.tools/mesen/Mesen.exe',player)
    settings=player.parent/'settings.json'
    # Never read or rewrite the live normal-play profile. Mesen may be saving it.
    config=json.loads(settings.read_text(encoding='utf-8-sig')) if settings.exists() else {}
    nes=config.setdefault('Nes',{})
    nes['AutoConfigureInput']=False
    port=nes.setdefault('Port1',{})
    port['Type']='NesController'
    if not port.get('Mapping1',{}).get('A'):
        port['Mapping1']={'A':67,'B':69,'Start':6,'Select':116,
                          'Up':24,'Down':26,'Left':23,'Right':25}
        port['Mapping2']={'A':0x100E,'B':0x100D,'Start':0x1005,'Select':0x1006,
                          'Up':0x1001,'Down':0x1002,'Left':0x1003,'Right':0x1004}
    preferences=config.setdefault('Preferences',{})
    preferences.update({'SingleInstance':False,'AutoLoadPatches':False,
                        'OverrideSaveDataFolder':True,'SaveDataFolder':str(folder/'play-saves'),
                        'OverrideSaveStateFolder':True,'SaveStateFolder':str(slots)})
    # Reserve one F-key per test checkpoint, clearing conflicting default bindings (e.g. F8=Auto, F9=MaxSpeed).
    shortcuts=preferences.setdefault('ShortcutKeys',[])
    reserved=set(range(90,90+len(manifest['states'])))
    for entry in shortcuts:
        for key_field in ('KeyCombination','KeyCombination2'):
            combo=entry.get(key_field)
            if combo and combo.get('Key1') in reserved and not combo.get('Key2') and not combo.get('Key3'):
                combo['Key1']=0
    for slot in range(1,len(manifest['states'])+1):
        name=f'LoadStateSlot{slot}'
        shortcuts[:]=[s for s in shortcuts if s.get('Shortcut')!=name]
        shortcuts.append({'Shortcut':name,'KeyCombination':{'Key1':89+slot,'Key2':0,'Key3':0}})
    config.setdefault('Debug',{}).setdefault('ScriptWindow',{})['AllowIoOsAccess']=False
    settings.write_text(json.dumps(config,indent=2)+'\n')
    print(f"Test profile ready: {player}\nF1-F{len(manifest['states'])} load the checkpoints.")
    return manifest


if __name__=='__main__':prepare()
