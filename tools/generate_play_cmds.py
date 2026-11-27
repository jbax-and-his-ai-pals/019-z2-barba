"""Generate and validate Windows .cmd launchers in play/, play/cmd/, and play/compat/cmd/."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (game_id, display_name, has_mmc3_compat, custom_pack_script_or_None)
SUBGAMES: tuple[tuple[str, str, bool, str | None], ...] = (
    ('dk', 'Donkey Kong', True, None),
    ('duck', 'Duck Hunt', True, None),
    ('feud', 'Family Feud', True, 'create_feud_pack.py'),
    ('waldo', 'Wheres Barba', True, 'create_waldo_pack.py'),
    ('wheel', 'Wheel of Fortune', False, None),
)

# (filename, python_script_under_tools)
EXTRA_PYTHON_CMDS: tuple[tuple[str, str], ...] = (
    ('Test Arcade Doors.cmd', 'create_portal_door_pack.py'),
    ('Test Wheres Barba in Z2.cmd', 'create_waldo_z2_pack.py'),
)

# (filename, checkpoint_set_or_None)
Z2_TEST_CMDS: tuple[tuple[str, str | None], ...] = (
    ('Test Core.cmd', None),
    ('Test All Spells.cmd', 'spells'),
    ('Test Bosses.cmd', 'bosses'),
    ('Test Busy Areas.cmd', 'busy'),
    ('Test Edge Scenarios.cmd', 'edges'),
    ('Test Endgame.cmd', 'endgame'),
    ('Test Fireballs.cmd', 'fireballs'),
    ('Test Gem Celebration.cmd', 'gem'),
    ('Test Key Items.cmd', 'items'),
    ('Test NG+.cmd', 'ngplus'),
    ('Test Palaces.cmd', 'palaces'),
    ('Test Saria Quicksand.cmd', 'saria'),
    ('Test Towns and World.cmd', 'world'),
    ('Test Tricky Movement.cmd', 'movement'),
)

_TOOL_REF_RE = re.compile(r'"%~dp0((?:\.\.\\)+)(tools\\[^"]+)"')


def _ps_cmd(rel_tools: str, args: str) -> str:
    return (
        '@echo off\r\n'
        f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0{rel_tools}" {args}\r\n'
        'if errorlevel 1 pause\r\n'
    )


def _py_cmd(rel_tools: str, args: str = '') -> str:
    suffix = f' {args}' if args else ''
    return (
        '@echo off\r\n'
        f'python "%~dp0{rel_tools}"{suffix}\r\n'
        'if errorlevel 1 pause\r\n'
    )


def expected_cmds(root: Path = ROOT) -> dict[Path, str]:
    """Return mapping of expected .cmd paths (under play/) to exact file contents."""
    play = root / 'play'
    cmd_dir = play / 'cmd'
    compat_cmd_dir = play / 'compat' / 'cmd'
    out: dict[Path, str] = {
        play / 'Play Barba.cmd': (
            '@echo off\r\n'
            'powershell.exe -NoProfile -File "%~dp0..\\tools\\launch.ps1"\r\n'
            'if errorlevel 1 pause\r\n'
        ),
    }

    for game_id, name, has_mmc3, pack_script in SUBGAMES:
        out[cmd_dir / f'Play {name}.cmd'] = _ps_cmd(
            r'..\..\tools\launch_subgame.ps1',
            f'-Game {game_id}',
        )
        if pack_script is not None:
            out[cmd_dir / f'Test {name}.cmd'] = _py_cmd(rf'..\..\tools\{pack_script}')
        else:
            out[cmd_dir / f'Test {name}.cmd'] = _py_cmd(
                r'..\..\tools\create_subgame_pack.py',
                f'--game {game_id}',
            )

        if has_mmc3:
            out[compat_cmd_dir / f'Play {name}.cmd'] = _ps_cmd(
                r'..\..\..\tools\launch_subgame.ps1',
                f'-Game {game_id} -Mapper mmc3',
            )
            if pack_script is not None:
                out[compat_cmd_dir / f'Test {name}.cmd'] = _py_cmd(
                    rf'..\..\..\tools\{pack_script}',
                    '--mmc3',
                )
            else:
                out[compat_cmd_dir / f'Test {name}.cmd'] = _py_cmd(
                    r'..\..\..\tools\create_subgame_pack.py',
                    f'--game {game_id} --mmc3',
                )

    for filename, script in EXTRA_PYTHON_CMDS:
        out[cmd_dir / filename] = _py_cmd(rf'..\..\tools\{script}')

    for filename, checkpoint_set in Z2_TEST_CMDS:
        args = f'-TestPack -CheckpointSet {checkpoint_set}' if checkpoint_set else '-TestPack'
        out[cmd_dir / filename] = _ps_cmd(r'..\..\tools\launch.ps1', args)

    return out


def validate_cmds(root: Path = ROOT) -> list[str]:
    """Return a list of validation errors (empty when all .cmd files are valid and up-to-date)."""
    errors: list[str] = []
    expected = expected_cmds(root)
    play = root / 'play'
    actual = {p for p in play.rglob('*.cmd')} if play.is_dir() else set()

    for missing in sorted(set(expected) - actual):
        errors.append(f'Missing launcher: {missing.relative_to(root)}')
    for extra in sorted(actual - set(expected)):
        errors.append(f'Unexpected launcher: {extra.relative_to(root)}')

    for path, want in sorted(expected.items()):
        if path in actual:
            got = path.read_bytes().decode('utf-8')
            if got != want:
                errors.append(f'Out-of-date launcher: {path.relative_to(root)}')
            match = _TOOL_REF_RE.search(got)
            if not match:
                errors.append(f'No tool path found in {path.relative_to(root)}')
            else:
                target = (path.parent / match.group(1) / match.group(2).replace('\\', '/')).resolve()
                if not target.is_file():
                    errors.append(f'Broken target in {path.relative_to(root)}: {target}')

    return errors


def write_cmds(root: Path = ROOT) -> list[Path]:
    """Write all expected .cmd launchers and return written paths."""
    written: list[Path] = []
    for path, content in sorted(expected_cmds(root).items()):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode('utf-8'))
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Validate existing .cmd files without writing.')
    args = parser.parse_args()

    if args.check:
        errors = validate_cmds(ROOT)
        if errors:
            for err in errors:
                print(err, file=sys.stderr)
            return 1
        print(f'All {len(expected_cmds(ROOT))} .cmd launchers OK.')
        return 0

    written = write_cmds(ROOT)
    errors = validate_cmds(ROOT)
    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1
    print(f'Generated and verified {len(written)} .cmd launchers.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
