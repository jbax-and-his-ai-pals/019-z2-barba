"""ROM-free checks for checkpoint routing, loadouts and Lua synchronization."""
import sys
import tempfile
import json
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import create_test_pack as pack
import prepare_test_player as player

class CheckpointSets(unittest.TestCase):
    def test_set_sizes_and_unique_ids(self):
        self.assertEqual(pack.SETS,['core','items','palaces','endgame','bosses','world','gem','busy','movement','edges'])
        for scenes in pack.RECIPES['sets'].values():
            self.assertTrue(1<=len(scenes)<=10)
            self.assertEqual(len({s['id'] for s in scenes}),len(scenes))
            for s in scenes:self.assertIn(s['profile'],pack.RECIPES['profiles'])

    def test_repaired_feature_recipes(self):
        sets=pack.RECIPES['sets']
        end={s['id']:s for s in sets['endgame']}
        movement={s['id']:s for s in sets['movement']}
        self.assertEqual(end['dark-link']['room'],54)
        self.assertNotEqual(end['gp-tunnel']['room'],54)
        self.assertEqual((movement['p1-low-ceiling']['world'],movement['p1-low-ceiling']['room']),(3,3))
        for scene in [end['gp-elevator'],movement['p1-shaft']]:
            self.assertEqual(scene['feature'],'elevator')
            self.assertEqual(scene['page'],0)
            self.assertEqual(scene['position'],{'x':112,'y':160})
        self.assertEqual(movement['p6-drop-shaft']['feature'],'pit')
        self.assertIn('tests/checkpoint_features.lua',pack.RECIPE_FILES)
        for name in ['endgame','movement']:
            scenes=sets[name]
            locations={(s['world'],s['room'],s['page'],tuple(s.get('position',{}).values())) for s in scenes}
            self.assertEqual(len(locations),len(scenes))

    def test_core_stays_in_existing_order(self):
        ids=[s[0] for s in pack.SCENES]
        self.assertEqual(ids,['castle','combat','spells','lava-ledge','lava-surface','barba','raft','town','boss-door','great-palace'])
        for path in ['tools/state_scenarios.lua','tests/state_pack.lua']:
            source=(pack.ROOT/path).read_text()
            for name in ids:self.assertIn("'"+name+"'",source)
        self.assertEqual(pack.scene_prefix('core'),'')

    def test_progression_and_palace_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'build').mkdir()
            # Deliberately invalid ninth entries make level-8 overreads detectable.
            rom=bytearray(16+0x4000)
            for stat in range(3):
                for level in range(1,8):rom[16+0x1658+stat*8+level]=level
            (root/'build/barba.nes').write_bytes(rom)
            with patch.object(pack,'ROOT',root):
                for scenes in pack.RECIPES['sets'].values():
                    for scene in scenes:
                        writes,expected=pack.checkpoint_writes(scene)
                        p=pack.RECIPES['profiles'][scene['profile']]
                        self.assertEqual(writes[0x794],6-p['placed'])
                        self.assertEqual(sum(expected[a] for a in range(0x78D,0x793)),p['placed'])
                        self.assertEqual(writes[0x793],0)
                        self.assertEqual(writes[0x700],3)
                        self.assertEqual(writes[0x773],p['magic']*32-1)
                        self.assertEqual(writes[0x774],p['hearts']*32-1)
                        self.assertNotEqual(p['levels'],[8,8,8])
                        self.assertEqual(writes[0x770],min([l for l in p['levels'] if l<8]))
                        if scene['world']>=3:
                            self.assertEqual(writes[0x56C],{1:0,2:1,3:2,4:0,5:0,6:1,7:2}[scene['number']])

    def test_lua_serializer_preserves_integer_ram_keys(self):
        self.assertEqual(pack.lua_value({0x777:2,'id':'test'}),'{[1911]=2,["id"]="test"}')
        self.assertEqual(pack.lua_value('line1\nline2'),'"line1\\nline2"')

    def test_launcher_uses_only_worktree_build_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'.tools/mesen/Mesen.exe'
            source.parent.mkdir(parents=True);source.write_bytes(b'portable emulator')
            folder=root/'build/test-pack/test/endgame';folder.mkdir(parents=True)
            (folder/'only.mss').write_bytes(b'MSS fixture')
            slots=folder/'slots';slots.mkdir();(slots/'barba-test_10.mss').write_bytes(b'old')
            profile=root/'build/mesen-scenarios/endgame';profile.mkdir(parents=True)
            (profile/'settings.json').write_text(json.dumps({'Preferences':{'ShortcutKeys':[
                {'Shortcut':'LoadStateSlot10','KeyCombination':{'Key1':99}},
                {'Shortcut':'MaxSpeed','KeyCombination':{'Key1':98}}]}}))
            manifest={'folder':str(folder),'states':[{'slot':1,'file':'only.mss'}]}
            with patch.object(player,'ROOT',root),patch.object(player,'create',return_value=manifest) as create:
                player.prepare('endgame');create.assert_called_once_with(set_name='endgame')
            self.assertFalse((source.parent.parent/'mesen-scenarios').exists())
            self.assertFalse((slots/'barba-test_10.mss').exists())
            self.assertEqual((slots/'barba-test_1.mss').read_bytes(),b'MSS fixture')
            config=json.loads((profile/'settings.json').read_text())
            shortcuts=config['Preferences']['ShortcutKeys']
            self.assertNotIn('LoadStateSlot10',[s['Shortcut'] for s in shortcuts])
            self.assertEqual(next(s for s in shortcuts if s['Shortcut']=='MaxSpeed')['KeyCombination']['Key1'],0)

    def test_bad_set_rejected_before_emulator(self):
        with self.assertRaises(ValueError):pack.create(set_name='../other')

if __name__=='__main__':unittest.main()
