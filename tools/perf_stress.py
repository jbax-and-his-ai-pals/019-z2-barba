"""Stress, profile and flicker probe for Barba side-view play (Mesen 2, headless).

Drives tests/perf_stress.lua over test-pack checkpoints with an aggressive autopilot, or
overlays the same instrumentation on an existing scenario. Writes build/<tag>-frames.csv,
build/<tag>-cases.txt and (with --profile) build/<tag>-profile.csv.

  python tools/perf_stress.py run --states busy/p2-crowded-floor --phases 3 --profile --tag p2
  python tools/perf_stress.py run --sets busy,world --tag towns
  python tools/perf_stress.py matrix                 # every side-view set, 2-3 phases, profiled
  python tools/perf_stress.py run --sets busy --patch notrail --tag wi-notrail   # in-memory what-if
  python tools/perf_stress.py overlay rebonack carock # profile real boss-fight scenarios
  python tools/perf_stress.py summary --tags "m-*"    # per-scene lag / cycles / flicker table
  python tools/perf_stress.py compare base:wi-base notrail:wi-notrail
  python tools/perf_stress.py profile --tags "m-*" --kind heavy [--case p2-crowded] [--buckets]

Needs the matching test packs: python tools/create_test_pack.py --set <name> (each set is keyed
by the ROM hash). Patches change only the emulator's in-memory PRG ROM, never files.
Cycle costs are estimates (base 6502 timing, branch and page penalties, OAM DMA); they track
measured NMI wall time within about 1%.
"""
from __future__ import annotations
import argparse
import bisect
import collections
import csv
import hashlib
import json
import re
import statistics as st
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from emulator_test import run as run_mesen  # noqa: E402

PROBE = ROOT / 'tests/perf_stress.lua'
BUILD = ROOT / 'build'
SEG_BANK = {
    'BANK0': 0, 'BANK0_OW': 0, 'BANK0_TAIL': 0, 'FIRE_CHECK': 0, 'FIRE_SPELL': 0, 'RAFT_TAIL': 0, 'ITEM_HOLD': 0,
    'BANK1': 1, 'BANK1_SOULS': 1, 'BANK2_CAVE': 2, 'BANK2_SMOKE': 2,
    'BANK3_DLG': 3, 'BANK3_SIGN': 3, 'BANK3_PAD': 3, 'TOWN': 3,
    'PALACE_ROAR': 4, 'BANK4_SPK': 4, 'BANK4_SPK2': 4, 'BANK4_SPK3': 4, 'BANK4_SPK4': 4,
    'BANK5': 5, 'ENDING_FIRE': 5,
    'BANK6': 6, 'BANK6_HAZE': 6, 'BANK6_OAM': 6, 'PALACE_SHAKE': 6, 'LAIR_HUD_SHAKE': 6, 'BANK6_CLOUD': 6,
    'BANK6_PAD': 6, 'LAUGH_DELAY': 6, 'FALL_ROAR': 6, 'SAMPLED_ROAR': 6, 'LAUGH_BANK': 6, 'ITEM_ROAR': 6,
    'WALDO_HAT_1': 6, 'LAVA': 7, 'GATEWAY': 7, 'TERRAIN': 7, 'LAG_RET': 7,
}
GROUPS = {
    'm-busy': dict(sets=['busy'], phases=3, frames=360),
    'm-bosses': dict(sets=['bosses'], phases=3, frames=480, seek='right'),
    'm-endgame': dict(sets=['endgame'], phases=3, frames=360),
    'm-movement': dict(sets=['movement'], phases=3, frames=360),
    'm-palaces': dict(sets=['palaces'], phases=2, frames=360),
    'm-world': dict(sets=['world'], phases=3, frames=360),
    'm-core': dict(sets=['core'], phases=2, frames=360),
}


# ---------------------------------------------------------------------------------------- symbols
class Symbols:
    """(bank, pc) -> Barba label, build.py patch name, or vanilla disassembly label."""

    def __init__(self, out: Path = BUILD):
        self.segs, self.barba, self.vanilla, self.patches, self.label_bank = [], {}, {}, [], {}
        dbg = out / 'barba.dbg'
        segs, syms = {}, []
        for line in dbg.read_text().splitlines():
            kind, _, rest = line.partition('\t')
            f = dict(re.findall(r'(\w+)=("[^"]*"|[^,]*)', rest))
            if kind == 'seg':
                segs[int(f['id'])] = (f['name'].strip('"'), int(f['start'], 16), int(f['size'], 16))
            elif kind == 'sym' and f.get('type') == 'lab' and 'seg' in f:
                syms.append(f)
        for name, start, size in segs.values():
            if name in SEG_BANK and size:
                self.segs.append((SEG_BANK[name], start, start + size, name))
        globals_by_seg = collections.defaultdict(list)
        for f in syms:
            name = f['name'].strip('"')
            seg = segs[int(f['seg'])][0]
            if not name.startswith(('@', '$')):
                globals_by_seg[seg].append((int(f['val'], 16), name))
                if seg in SEG_BANK:
                    self.label_bank[name] = SEG_BANK[seg]
        for v in globals_by_seg.values():
            v.sort()
        out_syms = collections.defaultdict(list)
        for f in syms:
            name = f['name'].strip('"')
            seg = segs[int(f['seg'])][0]
            if seg not in SEG_BANK:
                continue
            val = int(f['val'], 16)
            if name.startswith('@'):
                g = globals_by_seg.get(seg, [])
                i = bisect.bisect_right(g, (val, '￿')) - 1
                name = (g[i][1] if i >= 0 else seg) + name
            out_syms[SEG_BANK[seg]].append((val, name))
        self.barba = {b: sorted(v) for b, v in out_syms.items()}
        lab = re.compile(r'^([A-Za-z_]\w*):')
        ins = re.compile(r';\s*0x[0-9a-fA-F]+\s+\$([0-9A-Fa-f]{4})')
        for bank in range(8):
            path = ROOT / f'.tools/z2disassembly/src/prg{bank}.asm'
            res, pending = {}, []
            if path.exists():
                for line in path.read_text(errors='replace').splitlines():
                    m = lab.match(line)
                    if m:
                        pending.append(m.group(1))
                        continue
                    m = ins.search(line)
                    if m and pending:
                        res[int(m.group(1), 16)] = pending[-1]
                        pending = []
            self.vanilla[bank] = sorted(res.items())
        rep = json.loads((out / 'build-report.json').read_text())
        for p in rep['patches']:
            off = p['offset'] - 16
            if 0 <= off < 8 * 0x4000:
                bank = off // 0x4000
                a = (0xC000 if bank == 7 else 0x8000) + off % 0x4000
                self.patches.append((bank, a, a + p['length'], p['name']))
        self.labels = rep['labels']

    def resolve(self, bank: int, pc: int) -> tuple[str, str]:
        if bank == 0 and pc == 0:
            return '<interrupt entry>', 'platform'
        if bank == 8:
            return f'RAM ${pc & 0xFF00:04X}', 'ram'
        for b, s, e, name in self.segs:
            if b == bank and s <= pc < e:
                v = self.barba.get(bank, [])
                i = bisect.bisect_right(v, (pc, '￿')) - 1
                return (v[i][1] if i >= 0 and v[i][0] >= s else name), 'barba'
        for b, s, e, name in self.patches:
            if b == bank and s <= pc < e:
                return f'patch:{name}', 'patch'
        v = self.vanilla.get(bank, [])
        i = bisect.bisect_right(v, (pc, '￿')) - 1
        return f'v{bank}:{v[i][1] if i >= 0 else "bank"}', 'vanilla'

    def prg(self, label: str, delta: int = 0) -> int:
        """PRG-ROM offset of a Barba label in the combined ROM (fixed bank lives at $3C000)."""
        addr = self.labels[label] + delta
        bank = self.label_bank.get(label, 7 if addr >= 0xC000 else None)
        if bank is None:
            raise KeyError(f'no bank for {label}')
        return 0x3C000 + addr - 0xC000 if bank == 7 else bank * 0x4000 + addr - 0x8000


# ---------------------------------------------------------------------------------------- patches
def find(rom: bytes, start: int, pattern: bytes, limit: int = 0x80) -> int:
    i = rom.find(pattern, start, start + limit)
    if i < 0:
        raise SystemExit(f'pattern {pattern.hex()} not found near ${start:05X}; update the preset')
    return i


def patch_preset(name: str, sym: Symbols, rom_path: Path) -> list[list[int]]:
    """In-memory what-if patches located by labels and byte patterns (no files change)."""
    prg = rom_path.read_bytes()[16:]
    trail = sym.prg('DrawEncounterTrailSprites6')
    hop = sym.prg('DrawDownstabTailHop6')
    presets = {
        'base': [],
        'notrail': [[trail, 0x60]],                                      # no side-view tail sprites
        'trail2': [[find(prg, trail, bytes([0xC0, 0x04, 0xD0])) + 1, 0x02]],  # torso pieces only
        'noclouds': [[sym.prg('DrawPalaceClouds6'), 0x60]],            # no sprite clouds
        'smokeon': [[find(prg, hop, bytes([0xC9, 0x51, 0xD0])) + 2, 0xEA, 0xEA]],  # pre-#330 smoke hop
        'nogov': [[sym.prg('BarbaLoadOk'), 0x38, 0x60]],               # fire governor always allows
    }
    out = []
    for part in name.split('+'):
        if part not in presets:
            raise SystemExit(f'unknown patch {part}; choose from {", ".join(presets)}')
        out += presets[part]
    return out


# ---------------------------------------------------------------------------------------- running
def lua_value(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        return json.dumps(v)
    if isinstance(v, dict):
        return '{' + ','.join(f'{f"[{k}]" if isinstance(k, int) else k}={lua_value(x)}' for k, x in v.items()) + '}'
    if isinstance(v, (list, tuple)):
        return '{' + ','.join(lua_value(x) for x in v) + '}'
    raise TypeError(v)


def pack_dir(rom: Path) -> Path:
    return BUILD / 'test-pack' / hashlib.sha256(rom.read_bytes()).hexdigest()[:12]


def launch(tag: str, cases: list[dict], profile: bool, rom: Path, patches=None, extra: str = '') -> int:
    pack = pack_dir(rom)
    missing = [c['state'] for c in cases if not (pack / (c['state'] + '.mss')).exists()]
    if missing:
        raise SystemExit(f'missing states in {pack}: {missing}. Run tools/create_test_pack.py --set <name>.')
    prefix = (f'PK_PACK = {json.dumps(pack.as_posix())}\nPK_TAG = {json.dumps(tag)}\n'
              f'PK_PROFILE = {lua_value(profile)}\nPK_CASES = {lua_value(cases)}\n')
    if patches:
        prefix += f'PK_PATCHES = {lua_value(patches)}\n'
    scenario = BUILD / f'perf_stress_{tag}.lua'
    scenario.write_text(prefix + extra + PROBE.read_text())
    frames = sum(c.get('frames', 300) + 40 for c in cases)
    t0 = time.time()
    code = run_mesen(scenario, rom, timeout=int(60 + frames / 40))
    print(f'{tag}: {len(cases)} cases, {frames} frames, {time.time() - t0:.1f}s, exit {code}')
    out = BUILD / f'{tag}-cases.txt'
    if out.exists():
        print(out.read_text())
    return code


def states_for(rom: Path, sets: list[str]) -> list[str]:
    pack = pack_dir(rom)
    return [f'{s}/{p.stem}' for s in sets for p in sorted((pack / s).glob('*.mss'))]


def make_cases(states, phases, frames, pattern, cadence, seek=None):
    cases = []
    for s in states:
        for p in range(phases):
            c = {'state': s, 'phase': p, 'frames': frames, 'pattern': pattern, 'cadence': cadence}
            if seek or s.startswith('bosses/'):
                c['seek'] = seek or 'right'
            if pattern == 'ow':
                c['gate'] = 'ow'
            cases.append(c)
    return cases


def cmd_run(a):
    states = a.states.split(',') if a.states else states_for(a.rom, a.sets.split(','))
    patches = patch_preset(a.patch, Symbols(), a.rom) if a.patch else None
    return launch(a.tag, make_cases(states, a.phases, a.frames, a.pattern, a.cadence), a.profile, a.rom, patches)


def cmd_matrix(a):
    code = 0
    for tag in (a.groups.split(',') if a.groups else GROUPS):
        g = GROUPS[tag]
        cases = make_cases(states_for(a.rom, g['sets']), g['phases'], g['frames'], 'fight', 6, g.get('seek'))
        code |= launch(tag, cases, True, a.rom)
    return code


def cmd_overlay(a):
    probe = PROBE.read_text()
    for name in a.tests:
        tag = ('ovf-' if a.fire else 'ov-') + name
        # --fire N: press B every N frames after PK_SKIP, on top of the scenario's own inputs.
        fire = ('local _setInput=emu.setInput\nemu.setInput=function(b,p)\n'
                f'  if b and frame and frame>PK_SKIP then b.b=(frame%{a.fire})<2 end\n'
                '  return _setInput(b,p)\nend\n') if a.fire else ''
        src = (f'PK_OVERLAY=true\nPK_TAG={json.dumps(tag)}\nPK_PROFILE={lua_value(a.profile)}\nPK_SKIP={a.skip}\n'
               f'PK_CASES={{}}\nPK_PACK=""\n' + probe + '\n' + fire + f"dofile(TEST_DIR..'/{name}.lua')\n"
               'local _stop=stopScenario\nstopScenario=function(c) PK_FLUSH(true); return _stop(c) end\n')
        scen = BUILD / f'perf_stress_{tag}.lua'
        scen.write_text(src)
        code = run_mesen(scen, a.rom, timeout=600)
        out = BUILD / f'{tag}-overlay.txt'
        print(name, 'exit', code)
        print(out.read_text() if out.exists() else '(no overlay output)')
    return 0


# ---------------------------------------------------------------------------------------- analysis
def frame_rows(tag_glob: str):
    rows = collections.defaultdict(list)
    for f in sorted(BUILD.glob(f'{tag_glob}-frames.csv')):
        for r in csv.DictReader(open(f)):
            if r['gate'] == '1':
                rows[r['case'].split('#')[0]].append(r)
    return rows


def scene_stats(rs):
    n = len(rs)
    walls = sorted(int(r['wall']) for r in rs if int(r['wall']) > 0) or [0]
    ex = sum(int(r.get('excess', 0)) for r in rs)
    exn = sum(int(r.get('excessNoB', 0)) for r in rs)
    return dict(
        frames=n, lag=sum(int(r['lag']) for r in rs), avg=int(st.mean(w for w in walls if w < 40000) if walls else 0),
        p95=walls[int(len(walls) * .95)], peak=walls[-1], over27=sum(1 for w in walls if w > 27000),
        drop=100 * sum(1 for r in rs if int(r['dropEntries']) > 0) / max(1, n),
        dlines=st.mean(int(r['dropLines']) for r in rs), maxline=max(int(r['maxLine']) for r in rs),
        barba=100 * sum(1 for r in rs if int(r['dropBarba']) > 0) / max(1, n),
        etog=sum(int(r['togEnemy']) for r in rs) / max(1, n) * 60,
        bshare=(1 - exn / ex) * 100 if ex else 0, hud=sum(int(r['hudBad']) for r in rs),
        shots=st.mean(int(r['shotsN']) + int(r['shotsX']) for r in rs),
        enemies=st.mean(int(r['enemies']) for r in rs))


HEAD = (f'{"scene":30s} {"frames":>6s} {"lag":>4s} {"avg":>6s} {"p95":>6s} {"peak":>6s} {">27k":>5s} | '
        f'{"drop%":>5s} {"ln/f":>5s} {"maxL":>4s} {"Barba%":>6s} {"Etog/s":>6s} {"Bshare":>6s} | {"shots":>5s} {"enem":>4s} {"hud":>3s}')


def fmt(scene, s):
    return (f'{scene:30s} {s["frames"]:6d} {s["lag"]:4d} {s["avg"]:6d} {s["p95"]:6d} {s["peak"]:6d} {s["over27"]:5d} | '
            f'{s["drop"]:5.0f} {s["dlines"]:5.1f} {s["maxline"]:4d} {s["barba"]:6.0f} {s["etog"]:6.1f} {s["bshare"]:6.0f} | '
            f'{s["shots"]:5.2f} {s["enemies"]:4.1f} {s["hud"]:3d}')


def cmd_summary(a):
    rows = frame_rows(a.tags)
    stats = {k: scene_stats(v) for k, v in rows.items() if len(v) >= 50}
    print(HEAD)
    for k, s in sorted(stats.items(), key=lambda kv: (-kv[1]['lag'], -kv[1]['p95'])):
        print(fmt(k, s))


def cmd_compare(a):
    sets = []
    for spec in a.variants:
        name, _, tag = spec.partition(':')
        sets.append((name, frame_rows(tag or name)))
    print(f'{"variant":12s} ' + HEAD)
    for scene in sets[0][1]:
        for name, rows in sets:
            if scene in rows and len(rows[scene]) >= 50:
                print(f'{name:12s} ' + fmt(scene, scene_stats(rows[scene])))
        print()


BUCKETS = [
    ('bank switching', r'SwapPRG|FarCall|Gateway|NativeReturn|SwapToBank|LagNmi|RoarRestoreBank'),
    ('OAM shadow copy + priority', r'CopyOamShadow6|CopySceneOam6|PrioritizeRoomOam6|ShoutOamPriority6|FinishSceneOam6|'
     r'FinishBossOam6|SariaTip|ShakeLavaOam6|LavaShakeOffset6|CheckP6|DrawDownstabTailHop6|NmiRng6'),
    ('sprite clouds', r'DrawPalaceClouds6|IsSpriteCloudRoom6|ComputeHalfCamx6'),
    ('tail (trail)', r'Trail|Torso|EncounterPlayerTrail|Downstab'),
    ('body render + head geometry', r'BarbaDisplay|BarbaGeometry|BarbaCeiling|TerrainBatch|Tall|BarbaStomp|DeathTrail'),
    ('fire', r'BarbaProjectiles|Extra|BarbaBlock|BarbaStepSlotY|BarbaLoadOk|BarbaEmit|BarbaPlace|BarbaVolley|BarbaAdvance|'
     r'BarbaBurst|BarbaFireSpell|Shield|BarbaEnemyFire|BarbaNativeBlocks|Inferno|Meteor|BarbaBreathSfx|BarbaCancel|BarbaArm|DarkLinkFire'),
    ('town chaos', r'Town|Combo|Scorch|Shout|Sign|Villager|Ash|Panic|Smoke|Chimney'),
    ('scenery CHR / IRQ setup', r'IrqSetup6|NmiVblankSetup6|SceneryChr|CastleFlame|Grass|Wind|Water|Haze|Foliage|'
     r'SetupEncounterScenery6|VblankHudReset6|ArmStage|SetDeltaLine|AdvanceCloudDrift|Souls|IrqHandler|Sprite-0'),
    ('sampled audio', r'Roar|Laugh|Dac|Dmc|Sample'),
]
PHASES = {0: 'pre', 1: 'clear', 2: 'mode', 3: 'post'}


def cmd_profile(a):
    sym = Symbols()
    frames = collections.Counter()
    for f in BUILD.glob(f'{a.tags}-frames.csv'):
        for r in csv.DictReader(open(f)):
            if r['gate'] == '1' and int(r['nmis']) > 0 and (a.kind != 'heavy' or int(r['wall']) >= 25000):
                frames[r['case']] += 1
    agg, cats, seen, cache = collections.Counter(), {}, set(), {}
    for f in BUILD.glob(f'{a.tags}-profile.csv'):
        for r in csv.DictReader(open(f)):
            if r['kind'] != a.kind or (a.case and a.case not in r['case']):
                continue
            seen.add(r['case'])
            key = (int(r['bank']), int(r['pc']))
            if key not in cache:
                lab, c = sym.resolve(*key)
                cache[key] = (lab if a.local else lab.split('@')[0], c)
            lab, c = cache[key]
            ctx = int(r['ctx'])
            if ctx % 10 == 2:
                lab = '[IRQ] ' + lab
            elif a.phases:
                lab = f'[{PHASES.get(ctx // 10, "?")}] {lab}'
            if a.buckets:
                if c == 'vanilla':
                    lab = 'vanilla Zelda II code'
                elif c == 'patch' and not re.search(BUCKETS[0][1], lab):
                    lab = 'patched vanilla (OAM clear, offscreen mask, NMI)'
                else:
                    lab = next((n for n, rx in BUCKETS if re.search(rx, lab)), 'other Barba')
            agg[lab] += int(r['cycles'])
            cats[lab] = c
    n = sum(frames[c] for c in seen)
    tot = sum(agg.values())
    print(f'tags={a.tags} kind={a.kind} cases={len(seen)} frames={n} cycles/frame={tot / max(1, n):.0f}')
    for k, v in agg.most_common(a.top):
        print(f'{k[:70]:70s} {v / max(1, n):8.0f} {100 * v / max(1, tot):6.2f}%  {cats[k]}')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    r.add_argument('--tag', default='stress')
    r.add_argument('--sets', default='busy')
    r.add_argument('--states')
    r.add_argument('--phases', type=int, default=3)
    r.add_argument('--frames', type=int, default=360)
    r.add_argument('--pattern', default='fight', choices=('fight', 'stand', 'meteor', 'idle', 'ow'))
    r.add_argument('--cadence', type=int, default=6, help='frames between B presses (6 = densest volleys)')
    r.add_argument('--profile', action='store_true')
    r.add_argument('--patch', help='what-if preset(s), joined with +: notrail, trail2, noclouds, smokeon, nogov')
    m = sub.add_parser('matrix')
    m.add_argument('--groups', help='comma list of ' + ','.join(GROUPS))
    o = sub.add_parser('overlay')
    o.add_argument('tests', nargs='+')
    o.add_argument('--skip', type=int, default=1100, help='frames before measurement starts')
    o.add_argument('--profile', action='store_true')
    o.add_argument('--fire', type=int, default=0, help='also press B every N frames (max-fire stress)')
    s = sub.add_parser('summary')
    s.add_argument('--tags', default='m-*')
    c = sub.add_parser('compare')
    c.add_argument('variants', nargs='+', help='name:tag pairs, e.g. base:wi-base notrail:wi-notrail')
    p = sub.add_parser('profile')
    p.add_argument('--tags', default='m-*')
    p.add_argument('--kind', default='heavy', choices=('win', 'heavy'))
    p.add_argument('--case')
    p.add_argument('--top', type=int, default=40)
    p.add_argument('--local', action='store_true', help='keep @local labels')
    p.add_argument('--phases', action='store_true', help='split by NMI phase (pre/clear/mode/post)')
    p.add_argument('--buckets', action='store_true', help='group into subsystems')
    for x in (r, m, o):
        x.add_argument('--rom', type=Path, default=BUILD / 'barba.nes')
    a = ap.parse_args()
    return {'run': cmd_run, 'matrix': cmd_matrix, 'overlay': cmd_overlay, 'summary': cmd_summary,
            'compare': cmd_compare, 'profile': cmd_profile}[a.cmd](a) or 0


if __name__ == '__main__':
    raise SystemExit(main())
