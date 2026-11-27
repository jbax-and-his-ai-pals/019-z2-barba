"""Generate on-the-fly Mesen save states at every active portal door in build/portal-manifest.json."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from emulator_test import run
from subgame_pack import ROOT, install_pack_profile

ROM_PATH = ROOT / 'build/barba.nes'
MANIFEST_PATH = ROOT / 'build/portal-manifest.json'
PACK_DIR = ROOT / 'build/portal-doors-pack'
PROFILE_DIR = ROOT / 'build/mesen-scenarios/portal-doors'


def _lua_slots(slots: list[dict]) -> str:
    entries = []
    for s in slots:
        d = s['door']
        x_mid = (d['x_lo'] + d['x_hi']) // 2
        entries.append(
            f"  {{ slot = {s['slot']}, id = {json.dumps(s['id'])}, "
            f"town = {d['town_id']}, room = {d['room']}, page = {d['page']}, x = {x_mid} }}"
        )
    return 'PORTAL_SLOTS = {\n' + ',\n'.join(entries) + '\n}\n'


def create(force: bool = False) -> dict:
    if not ROM_PATH.is_file() or not MANIFEST_PATH.is_file():
        raise SystemExit('Missing build/barba.nes or build/portal-manifest.json. Run python tools/build.py first.')

    portal_manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
    slots = portal_manifest['slots']
    digest = hashlib.sha256(ROM_PATH.read_bytes()).hexdigest()
    pack_manifest_path = PACK_DIR / 'manifest.json'

    if pack_manifest_path.exists() and not force:
        existing = json.loads(pack_manifest_path.read_text(encoding='utf-8'))
        if existing.get('rom_sha256') == digest and all(
            (PACK_DIR / f"portal-{s['id']}.mss").exists() for s in slots
        ):
            return existing

    PACK_DIR.mkdir(parents=True, exist_ok=True)
    scenario = ROOT / 'build/generate-portal-door-states.lua'
    prefix = (
        f'PACK_DIR = {json.dumps(PACK_DIR.as_posix())}\n'
        f'TEST_DIR = {json.dumps((ROOT / "tests").as_posix())}\n'
        + _lua_slots(slots)
    )
    scenario.write_text(
        prefix + (ROOT / 'tools/scenarios/portal_door_scenarios.lua').read_text(encoding='utf-8'),
        encoding='utf-8',
    )
    if run(scenario, ROM_PATH, 120):
        raise SystemExit('Portal door state generation failed; see build/generate-portal-door-states-error.txt')

    states = []
    for fkey, s in enumerate(slots, 1):
        mss = PACK_DIR / f"portal-{s['id']}.mss"
        if not mss.is_file() or not mss.read_bytes().startswith(b'MSS'):
            raise SystemExit(f'Missing or invalid state: {mss}')
        d = s['door']
        states.append({
            'slot': fkey,
            'id': f"portal-{s['id']}",
            'name': f"{d['town_name']} -> {s['name']}",
            'instructions': f"Standing at {d['town_name']} portal door (room ${d['room']:02X}, page {d['page']}). Press Up to enter {s['name']}.",
            'file': mss.name,
        })

    manifest = {'rom_sha256': digest, 'folder': str(PACK_DIR), 'rom': str(ROM_PATH), 'states': states}
    pack_manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


def prepare(force: bool = False) -> tuple[Path, dict]:
    manifest = create(force=force)
    player = install_pack_profile(PROFILE_DIR, ROM_PATH, manifest)
    return player, manifest


def main() -> None:
    import subprocess
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    player, manifest = prepare(force=args.force)
    for s in manifest['states']:
        print(f"F{s['slot']}: {s['name']} -> {s['instructions']}")
    if not args.prepare_only:
        subprocess.Popen([str(player), str(ROM_PATH)], cwd=str(PROFILE_DIR))


if __name__ == '__main__':
    main()
