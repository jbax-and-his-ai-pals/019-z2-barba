"""The shared .tools emulator directory must remain read-only."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import emulator_test


class EmulatorIsolationTests(unittest.TestCase):
    def test_runner_writes_only_under_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shared = root / '.tools/mesen'
            shared.mkdir(parents=True)
            (shared / 'Mesen.exe').write_bytes(b'fake emulator')
            (shared / 'MesenCore.dll').write_bytes(b'fake core')
            (shared / 'settings.json').write_text('untouched')
            scenario = root / 'probe.lua'
            scenario.write_text('-- fixture')
            before = {p.name: p.read_bytes() for p in shared.iterdir()}
            with patch.object(emulator_test, 'ROOT', root), patch.object(
                emulator_test.subprocess, 'run',
                return_value=SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
            ) as run:
                self.assertEqual(emulator_test.run(scenario, root / 'fixture.nes'), 0)
            self.assertEqual(Path(run.call_args.args[0][0]), root / 'build/mesen/Mesen.exe')
            self.assertEqual(before, {p.name: p.read_bytes() for p in shared.iterdir()})
            self.assertTrue((root / 'build/mesen/settings.json').is_file())
            self.assertFalse((shared / 'Saves').exists())


if __name__ == '__main__':
    unittest.main()
