"""Capture live 256x240 title screen screenshots from all 11 built ROMs vs vanilla for the dashboard."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import struct
import sys
import zlib
from pathlib import Path
from typing import Any

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from build_history import HISTORY_FILE, get_subgame_build_number  # noqa: E402
import emulator_test  # noqa: E402
import subgame_pack  # noqa: E402

ROOT = _TOOLS_DIR.parent
CAP_DIR = ROOT / "build" / "title-captures"
OUT_DIR = ROOT / "web" / "previews" / "titles"
DATA_JS = ROOT / "web" / "title_review_data.js"
LOCAL_DATA_JS = ROOT / "web" / "local_title_review_data.js"


def _extract_build_num(path: Path) -> int | None:
    m = re.search(r"-b(\d+)$", path.stem)
    return int(m.group(1)) if m else None


def _latest_z2_rom() -> tuple[Path, int]:
    play_dir = ROOT / "play"
    matches: list[tuple[int, Path]] = []
    if play_dir.is_dir():
        for p in play_dir.glob("barba-b*.nes"):
            bnum = _extract_build_num(p)
            if bnum is not None:
                matches.append((bnum, p))
    if matches:
        matches.sort(key=lambda item: item[0])
        bnum, path = matches[-1]
        return path, bnum

    for fallback in (play_dir / "barba.nes", ROOT / "build" / "barba.nes"):
        if fallback.is_file():
            bnum = None
            report_path = ROOT / "build" / "build-report.json"
            if report_path.is_file():
                try:
                    bnum = json.loads(report_path.read_text(encoding="utf-8")).get("build_number")
                except (OSError, json.JSONDecodeError):
                    pass
            if bnum is None and HISTORY_FILE.is_file():
                try:
                    conn = sqlite3.connect(HISTORY_FILE)
                    row = conn.execute("SELECT MAX(build_number) FROM builds").fetchone()
                    conn.close()
                    if row and row[0] is not None:
                        bnum = int(row[0])
                except sqlite3.Error:
                    pass
            return fallback, int(bnum or 0)
    raise FileNotFoundError("Missing built Zelda II Barba ROM (play/barba-b*.nes or build/barba.nes)")


def _lookup_subgame_build_by_sha256(history: Path, gid: str, rom_path: Path) -> int | None:
    if not history.is_file() or not rom_path.is_file():
        return None
    digest = hashlib.sha256(rom_path.read_bytes()).hexdigest()
    try:
        conn = sqlite3.connect(history)
        row = conn.execute(
            """
            SELECT build_number FROM subgame_builds
            WHERE game = ? AND output_sha256 = ?
            ORDER BY build_number DESC LIMIT 1
            """,
            (gid, digest),
        ).fetchone()
        conn.close()
        if row and row[0] is not None:
            return int(row[0])
    except sqlite3.Error:
        pass
    return None


def resolve_rom_and_build(gid: str, tag: str) -> tuple[Path, int | None]:
    if tag == "vanilla":
        rom = ROOT / "roms" / f"{gid}.nes"
        if not rom.is_file():
            raise FileNotFoundError(f"Missing vanilla ROM: {rom}")
        return rom, None

    if gid == "z2":
        return _latest_z2_rom()

    candidates: list[Path] = []
    nes_dir = ROOT / "play" / "nes"
    if nes_dir.is_dir():
        for pattern in (f"{gid}-b*.nes", f"{gid}.nes"):
            candidates.extend(p for p in nes_dir.glob(pattern) if p.is_file())
    compat_nes_dir = ROOT / "play" / "compat" / "nes"
    if compat_nes_dir.is_dir():
        for pattern in (f"{gid}-compat-b*.nes", f"{gid}-compat.nes"):
            candidates.extend(p for p in compat_nes_dir.glob(pattern) if p.is_file())
    for fallback in (ROOT / "build" / "subgames" / f"{gid}.nes", ROOT / "build" / f"{gid}_barba.nes"):
        if fallback.is_file():
            candidates.append(fallback)
    if not candidates:
        raise FileNotFoundError(f"Missing built {gid} ROM")

    rom = max(candidates, key=lambda p: p.stat().st_mtime)
    bnum = _extract_build_num(rom)
    if bnum is None:
        bnum = _lookup_subgame_build_by_sha256(HISTORY_FILE, gid, rom)
    if bnum is None:
        bnum = get_subgame_build_number(HISTORY_FILE, gid)
    return rom, bnum


def _inspect_png(path: Path) -> tuple[int, int, int]:
    """Return (width, height, unique_sampled_colors) for an 8-bit PNG."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Invalid PNG header: {path}")
    pos = 8
    w = h = color_type = 0
    plte = b""
    idat = bytearray()
    while pos < len(data):
        ln = struct.unpack(">I", data[pos : pos + 4])[0]
        kind = data[pos + 4 : pos + 8]
        payload = data[pos + 8 : pos + 8 + ln]
        pos += 12 + ln
        if kind == b"IHDR":
            w, h, bit_depth, color_type = struct.unpack(">IIBB", payload[:10])
            if bit_depth != 8:
                raise ValueError(f"Unsupported PNG bit depth {bit_depth} in {path}")
        elif kind == b"PLTE":
            plte = payload
        elif kind == b"IDAT":
            idat.extend(payload)
        elif kind == b"IEND":
            break
    bpp = {2: 3, 6: 4, 3: 1}[color_type]
    raw = zlib.decompress(bytes(idat))
    stride = w * bpp
    recon = bytearray(h * stride)
    for y in range(h):
        ftype = raw[y * (stride + 1)]
        row_in = raw[y * (stride + 1) + 1 : (y + 1) * (stride + 1)]
        row_out = y * stride
        for x in range(stride):
            a = recon[row_out + x - bpp] if x >= bpp else 0
            b = recon[row_out - stride + x] if y > 0 else 0
            c = recon[row_out - stride + x - bpp] if (y > 0 and x >= bpp) else 0
            v = row_in[x]
            if ftype == 1:
                v = (v + a) & 0xFF
            elif ftype == 2:
                v = (v + b) & 0xFF
            elif ftype == 3:
                v = (v + ((a + b) >> 1)) & 0xFF
            elif ftype == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                v = (v + pr) & 0xFF
            recon[row_out + x] = v
    colors: set[bytes] = set()
    for y in range(0, h, 2):
        off = y * stride
        for x in range(0, w, 2):
            if color_type == 3:
                idx = recon[off + x] * 3
                colors.add(plte[idx : idx + 3])
            else:
                colors.add(bytes(recon[off + x * bpp : off + x * bpp + 3]))
    return w, h, len(colors)


TITLE_SPECS: list[dict[str, Any]] = [
    {
        "id": "z2",
        "name": "Zelda II: Barba Edition",
        "original": "Zelda II: The Adventure of Link (Nintendo)",
        "summary": "Title screen with Barba on the cliff above the lava lake, THE ADVENTURE OF BARBA banner, and top-right build number.",
        "screens": [
            {
                "id": "title",
                "title": "Title Screen",
                "vanilla_caption": "Vanilla THE ADVENTURE OF LINK title screen",
                "ours_caption": "THE ADVENTURE OF BARBA title screen with build number",
            },
        ],
        "lua": r"""
local mem = emu.memType.nesMemory
local function r(a) return emu.read(a, mem) end
local frame = 0
local hold = 0
emu.addEventCallback(function()
    frame = frame + 1
    if r(0x0736) == 3 and r(0x0726) == 0 and r(0x00FC) == 0x60 then
        hold = hold + 1
    else
        hold = 0
    end
    if hold == 45 or frame == 1100 then
        local pf = assert(io.open(CAP_DIR .. '/' .. PREFIX .. 'title.png', 'wb'))
        pf:write(emu.takeScreenshot()); pf:close()
        emu.stop(0)
    end
end, emu.eventType.endFrame)
""",
    },
    {
        "id": "waldo",
        "name": "Where's Barba?",
        "original": "Where's Waldo? (THQ / Bethesda)",
        "summary": "Postcard title screen with THERE'S BARBA! banner, peeking Barba stamp, and bottom-right build number.",
        "screens": [
            {
                "id": "title",
                "title": "Postcard Title Screen",
                "vanilla_caption": "Vanilla WHERE'S WALDO? postcard title screen",
                "ours_caption": "THERE'S BARBA! postcard title screen with build number",
            },
        ],
        "lua": r"""
local frame = 0
local inp = {}
emu.addEventCallback(function() emu.setInput(inp, 0) end, emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame = frame + 1
    inp = {}
    if (frame >= 180 and frame < 185) or (frame >= 240 and frame < 245) then
        inp = {start = true}
    end
    if frame == 300 then
        local pf = assert(io.open(CAP_DIR .. '/' .. PREFIX .. 'title.png', 'wb'))
        pf:write(emu.takeScreenshot()); pf:close()
        emu.stop(0)
    end
end, emu.eventType.endFrame)
""",
    },
    {
        "id": "feud",
        "name": "Barba's Beef",
        "original": "Family Feud (GameTek)",
        "summary": "Screen 0 credits splash with BARBA'S BEEF™ and top-right build number, followed by Screen 1 oval marquee.",
        "screens": [
            {
                "id": "s0",
                "title": "Screen 0 (Credits & Build Number)",
                "vanilla_caption": "Vanilla FAMILY FEUD credits splash",
                "ours_caption": "BARBA'S BEEF™ credits splash with build number",
            },
            {
                "id": "s1",
                "title": "Screen 1 (Marquee)",
                "vanilla_caption": "Vanilla FAMILY FEUD marquee",
                "ours_caption": "BARBA'S BEEF marquee",
            },
        ],
        "lua": r"""
local mem = emu.memType.nesMemory
local function r(a) return emu.read(a, mem) end
local frame = 0
local s0_done = false
local s1_enter = nil
emu.addEventCallback(function()
    frame = frame + 1
    local scr = r(0x0345)
    if not s0_done and scr == 0x00 and frame == 75 then
        local pf = assert(io.open(CAP_DIR .. '/' .. PREFIX .. 's0.png', 'wb'))
        pf:write(emu.takeScreenshot()); pf:close()
        s0_done = true
    end
    if scr == 0x01 and not s1_enter then
        s1_enter = frame
    end
    if s1_enter and frame == s1_enter + 45 then
        if not s0_done then
            error('Never captured Screen 0 before Screen 1')
        end
        local pf = assert(io.open(CAP_DIR .. '/' .. PREFIX .. 's1.png', 'wb'))
        pf:write(emu.takeScreenshot()); pf:close()
        emu.stop(0)
    end
    if frame > 600 then
        error(string.format('Feud title timeout scr=%02X s0=%s', scr, tostring(s0_done)))
    end
end, emu.eventType.endFrame)
""",
    },
    {
        "id": "dk",
        "name": "Barba Kong",
        "original": "Donkey Kong (Nintendo)",
        "summary": "BARBA KONG title screen with fireball selector cursor and top-right build number.",
        "screens": [
            {
                "id": "title",
                "title": "Title Screen",
                "vanilla_caption": "Vanilla DONKEY KONG title screen",
                "ours_caption": "BARBA KONG title screen with build number",
            },
        ],
        "lua": r"""
local frame = 0
emu.addEventCallback(function()
    frame = frame + 1
    if frame == 60 then
        local pf = assert(io.open(CAP_DIR .. '/' .. PREFIX .. 'title.png', 'wb'))
        pf:write(emu.takeScreenshot()); pf:close()
        emu.stop(0)
    end
end, emu.eventType.endFrame)
""",
    },
    {
        "id": "duck",
        "name": "Villager Hunt (Barba's Hunt)",
        "original": "Duck Hunt (Nintendo)",
        "summary": "BARBA'S HUNT marquee, Octoroks/Moas menu text, and top-right build number.",
        "screens": [
            {
                "id": "title",
                "title": "Title Screen",
                "vanilla_caption": "Vanilla DUCK HUNT title screen",
                "ours_caption": "BARBA'S HUNT title screen with build number",
            },
        ],
        "lua": r"""
local frame = 0
emu.addEventCallback(function()
    frame = frame + 1
    if frame == 60 then
        local pf = assert(io.open(CAP_DIR .. '/' .. PREFIX .. 'title.png', 'wb'))
        pf:write(emu.takeScreenshot()); pf:close()
        emu.stop(0)
    end
end, emu.eventType.endFrame)
""",
    },
    {
        "id": "wheel",
        "name": "Wheel of Barba",
        "original": "Wheel of Fortune (GameTek)",
        "summary": "Screen 1 WHEEL of BARBA credits with bottom-right build number, plus Screen 2 curved BARBA wheel and marquee.",
        "screens": [
            {
                "id": "s1",
                "title": "Screen 1 (Credits & Build Number)",
                "vanilla_caption": "Vanilla WHEEL OF FORTUNE credits screen",
                "ours_caption": "WHEEL of BARBA credits screen with build number",
            },
            {
                "id": "s2",
                "title": "Screen 2 (Big Wheel)",
                "vanilla_caption": "Vanilla WHEEL OF FORTUNE big wheel",
                "ours_caption": "Curved BARBA big wheel and marquee ticker",
            },
        ],
        "lua": r"""
local frame = 0
emu.addEventCallback(function()
    frame = frame + 1
    if frame == 320 then
        local pf = assert(io.open(CAP_DIR .. '/' .. PREFIX .. 's1.png', 'wb'))
        pf:write(emu.takeScreenshot()); pf:close()
    elseif frame == 1000 then
        local pf = assert(io.open(CAP_DIR .. '/' .. PREFIX .. 's2.png', 'wb'))
        pf:write(emu.takeScreenshot()); pf:close()
        emu.stop(0)
    end
end, emu.eventType.endFrame)
""",
    },
    {
        "id": "f13",
        "name": "Friday the 13th: Camp Barba",
        "original": "Friday the 13th (LJN / Atlus)",
        "visibility": "local",
        "archived": True,
        "summary": "Archived post-2.0. CAMP BARBA jagged crimson/gold/white logo with 2x roaring Barba on left, build number top-right.",
        "screens": [
            {
                "id": "title",
                "title": "Title Screen",
                "vanilla_caption": "Vanilla FRIDAY THE 13TH title screen",
                "ours_caption": "CAMP BARBA title screen with left-side Barba and build number",
            },
        ],
        "lua": r"""
local frame = 0
emu.addEventCallback(function()
    frame = frame + 1
    if frame == 420 then
        local pf = assert(io.open(CAP_DIR .. '/' .. PREFIX .. 'title.png', 'wb'))
        pf:write(emu.takeScreenshot()); pf:close()
        emu.stop(0)
    end
end, emu.eventType.endFrame)
""",
    },
    {
        "id": "smb",
        "name": "Super Barba Bros.",
        "original": "Super Mario Bros. (Nintendo)",
        "visibility": "local",
        "archived": True,
        "summary": "Archived post-2.0. SUPER BARBA BROS. beveled title sign, BARBA HUD, Wyrmling on the demo stage, and top-right build number.",
        "screens": [
            {
                "id": "title",
                "title": "Title Screen",
                "vanilla_caption": "Vanilla SUPER MARIO BROS. title screen",
                "ours_caption": "SUPER BARBA BROS. title screen with build number",
            },
        ],
        "lua": r"""
local frame = 0
emu.addEventCallback(function()
    frame = frame + 1
    if frame == 60 then
        local pf = assert(io.open(CAP_DIR .. '/' .. PREFIX .. 'title.png', 'wb'))
        pf:write(emu.takeScreenshot()); pf:close()
        emu.stop(0)
    end
end, emu.eventType.endFrame)
""",
    },
    {
        "id": "mm2",
        "name": "Barba Man 2",
        "original": "Mega Man 2 (Capcom)",
        "visibility": "local",
        "archived": True,
        "summary": "Archived post-2.0. Skyscraper rooftop Barba beneath the unclipped MEGA BARBA II logo and top-right build number.",
        "screens": [
            {
                "id": "title",
                "title": "Title Screen",
                "vanilla_caption": "Vanilla MEGA MAN II title screen",
                "ours_caption": "MEGA BARBA II rooftop title screen with build number",
            },
        ],
        "lua": r"""
local frame = 0
local inp = {}
emu.addEventCallback(function() emu.setInput(inp, 0) end, emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame = frame + 1
    inp = {}
    if frame >= 180 and frame < 185 then inp = {start = true} end
    if frame == 300 then
        local pf = assert(io.open(CAP_DIR .. '/' .. PREFIX .. 'title.png', 'wb'))
        pf:write(emu.takeScreenshot()); pf:close()
        emu.stop(0)
    end
end, emu.eventType.endFrame)
""",
    },
    {
        "id": "zelda",
        "name": "The Legend of Barba",
        "original": "The Legend of Zelda (Nintendo)",
        "visibility": "local",
        "archived": True,
        "summary": "Archived post-2.0. Chiseled THE LEGEND OF BARBA title logo over the Triforce, molten crimson/amber lava waterfall, and top-right build number.",
        "screens": [
            {
                "id": "title",
                "title": "Title Screen",
                "vanilla_caption": "Vanilla THE LEGEND OF ZELDA title screen",
                "ours_caption": "THE LEGEND OF BARBA title screen with lava falls and build number",
            },
        ],
        "lua": r"""
local frame = 0
emu.addEventCallback(function()
    frame = frame + 1
    if frame == 120 then
        local pf = assert(io.open(CAP_DIR .. '/' .. PREFIX .. 'title.png', 'wb'))
        pf:write(emu.takeScreenshot()); pf:close()
        emu.stop(0)
    end
end, emu.eventType.endFrame)
""",
    },
    {
        "id": "mtpo",
        "name": "Barba's Punch-Out!!",
        "original": "Mike Tyson's Punch-Out!! (Nintendo)",
        "visibility": "local",
        "archived": True,
        "summary": "Archived post-2.0. Title2 Z2 Game Over Link silhouette, chunky green LINK and BARBA wallpaper, plus Title1 BARBA'S PUNCH-OUT!! marquee with build number.",
        "screens": [
            {
                "id": "title2",
                "title": "Challenge Portrait Screen",
                "vanilla_caption": "Vanilla MIKE TYSON challenge portrait",
                "ours_caption": "Z2 Game Over Link silhouette portrait & LINK nameplate",
            },
            {
                "id": "title1",
                "title": "Marquee Title Screen",
                "vanilla_caption": "Vanilla MIKE TYSON'S PUNCH-OUT!! marquee",
                "ours_caption": "BARBA'S PUNCH-OUT!! marquee with build number",
            },
        ],
        "lua": r"""
local frame = 0
emu.addEventCallback(function()
    frame = frame + 1
    if frame == 280 then
        local pf = assert(io.open(CAP_DIR .. '/' .. PREFIX .. 'title2.png', 'wb'))
        pf:write(emu.takeScreenshot()); pf:close()
    end
    if frame == 680 then
        local pf = assert(io.open(CAP_DIR .. '/' .. PREFIX .. 'title1.png', 'wb'))
        pf:write(emu.takeScreenshot()); pf:close()
        emu.stop(0)
    end
end, emu.eventType.endFrame)
""",
    },
]

SPECS_BY_ID = {spec["id"]: spec for spec in TITLE_SPECS}


def capture_game(spec: dict[str, Any], tag: str, force: bool = False) -> int | None:
    gid = spec["id"]
    out_files = [f"{gid}_{tag}_{scr['id']}.png" for scr in spec["screens"]]
    if not force and tag == "vanilla" and all((OUT_DIR / f).is_file() for f in out_files):
        return None

    rom_path, bnum = resolve_rom_and_build(gid, tag)
    CAP_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    prefix_name = f"{gid}_{tag}_"
    lua_path = ROOT / "build" / f"capture_title_{gid}_{tag}.lua"
    header = (
        f"TAG = {json.dumps(tag)}\n"
        f"CAP_DIR = {json.dumps(CAP_DIR.as_posix())}\n"
        f"PREFIX = {json.dumps(prefix_name)}\n"
    )
    lua_path.write_text(header + spec["lua"], encoding="utf-8")
    bstr = f" (Build #{bnum})" if bnum is not None else ""
    print(f"[{gid}:{tag}] Capturing {rom_path.relative_to(ROOT)}{bstr} ...")
    rc = emulator_test.run(lua_path, rom_path, timeout=45)
    if rc != 0:
        raise RuntimeError(f"Title capture failed for {gid}:{tag} ({rom_path}) with exit code {rc}")

    for fname in out_files:
        src = CAP_DIR / fname
        if not src.is_file():
            raise FileNotFoundError(f"Expected screenshot was not created: {src}")
        w, h, n_colors = _inspect_png(src)
        if (w, h) != (256, 240):
            raise ValueError(f"Expected 256x240 screenshot for {fname}, got {w}x{h}")
        if n_colors < 2:
            raise ValueError(f"Blank/flat title screenshot for {fname}: only {n_colors} color(s)")
        shutil.copy2(src, OUT_DIR / fname)
        print(f"  -> { (OUT_DIR / fname).relative_to(ROOT) } ({w}x{h}, {n_colors}c)")
    return bnum


def _existing_build_numbers() -> dict[str, int | None]:
    """Read previously recorded build numbers from local/public title_review_data.js."""
    found: dict[str, int | None] = {}
    prefix = "window.TITLE_REVIEW_DATA = "
    for path in (DATA_JS, LOCAL_DATA_JS):
        if not path.is_file():
            continue
        try:
            raw = path.read_text(encoding="utf-8").strip()
            if raw.startswith(prefix) and raw.endswith(";"):
                payload = json.loads(raw[len(prefix) : -1])
                for g in payload.get("games", []):
                    if isinstance(g, dict) and "id" in g and g.get("build_number") is not None:
                        found[g["id"]] = g.get("build_number")
        except (OSError, json.JSONDecodeError):
            pass
    return found


def build_catalog(
    allow_fallback: bool = False,
    captured_builds: dict[str, int | None] | None = None,
    prefer_existing: bool = False,
) -> dict[str, Any]:
    existing_builds = _existing_build_numbers() if (allow_fallback or prefer_existing) else {}
    games_payload: list[dict[str, Any]] = []
    for spec in TITLE_SPECS:
        gid = spec["id"]
        if captured_builds is not None and gid in captured_builds:
            bnum = captured_builds[gid]
        elif prefer_existing and existing_builds.get(gid) is not None:
            bnum = existing_builds[gid]
        else:
            try:
                _rom_path, bnum = resolve_rom_and_build(gid, "modded")
            except FileNotFoundError:
                if not allow_fallback:
                    raise
                bnum = existing_builds.get(gid)
                if bnum is None and HISTORY_FILE.is_file():
                    if gid == "z2":
                        try:
                            conn = sqlite3.connect(HISTORY_FILE)
                            row = conn.execute("SELECT MAX(build_number) FROM builds").fetchone()
                            conn.close()
                            if row and row[0] is not None:
                                bnum = int(row[0])
                        except sqlite3.Error:
                            pass
                    else:
                        bnum = get_subgame_build_number(HISTORY_FILE, gid)

        screens_payload = []
        for scr in spec["screens"]:
            sid = scr["id"]
            scr_entry: dict[str, Any] = {
                "id": sid,
                "title": scr["title"],
                "vanilla": {
                    "label": "Vanilla",
                    "img": f"previews/titles/{gid}_vanilla_{sid}.png",
                    "caption": scr["vanilla_caption"],
                },
                "ours": {
                    "label": f"Build #{bnum}" if bnum else "Our Version",
                    "img": f"previews/titles/{gid}_modded_{sid}.png",
                    "caption": scr["ours_caption"],
                },
            }
            if scr.get("visibility", "public") == "local":
                scr_entry["visibility"] = "local"
            screens_payload.append(scr_entry)

        g_entry: dict[str, Any] = {
            "id": gid,
            "name": spec["name"],
            "original": spec["original"],
            "build_number": bnum,
            "status_label": f"Build #{bnum}" if bnum else "Built ROM",
            "summary": spec["summary"],
            "screens": screens_payload,
        }
        g_vis = spec.get("visibility", "public")
        all_screens_local = bool(screens_payload) and all(
            s.get("visibility") == "local" for s in screens_payload
        )
        if g_vis == "local" or all_screens_local:
            g_entry["visibility"] = "local"
        if spec.get("archived"):
            g_entry["archived"] = True
        games_payload.append(g_entry)
    return {"version": 2, "games": games_payload}


def title_catalog_payload(
    include_local: bool = True, catalog_override: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Filter a Title Screens catalog by visibility ('public' vs 'local')."""
    base = (
        build_catalog(allow_fallback=True, prefer_existing=True)
        if catalog_override is None
        else catalog_override
    )
    games_out: list[dict[str, Any]] = []
    for g in base.get("games", []):
        g_vis = g.get("visibility", "public")
        if not include_local and g_vis == "local":
            continue
        screens_out: list[dict[str, Any]] = []
        for scr in g.get("screens", []):
            scr_vis = scr.get("visibility", "public")
            if not include_local and scr_vis == "local":
                continue
            scr_copy = dict(scr)
            if scr_vis != "local":
                scr_copy.pop("visibility", None)
            screens_out.append(scr_copy)
        if not include_local and not screens_out:
            continue
        g_copy = dict(g)
        g_copy["screens"] = screens_out
        if g_vis != "local" and not (
            include_local and screens_out and all(s.get("visibility") == "local" for s in screens_out)
        ):
            g_copy.pop("visibility", None)
        elif include_local and g_vis == "local":
            g_copy["visibility"] = "local"
        games_out.append(g_copy)
    return {"version": base.get("version", 2), "games": games_out}


def write_title_review_data_js(
    out_dir: Path | None = None,
    flavor: str = "all",
    catalog_override: dict[str, Any] | None = None,
) -> list[Path]:
    if flavor not in ("public", "local", "all"):
        raise ValueError(f"Unknown flavor: {flavor}")
    target_dir = DATA_JS.parent if out_dir is None else out_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    base = (
        build_catalog(allow_fallback=True, prefer_existing=True)
        if catalog_override is None
        else catalog_override
    )

    if flavor in ("public", "all"):
        pub_path = target_dir / DATA_JS.name
        pub_payload = title_catalog_payload(include_local=False, catalog_override=base)
        pub_path.write_text(
            "window.TITLE_REVIEW_DATA = " + json.dumps(pub_payload, indent=2) + ";\n",
            encoding="utf-8",
        )
        print(f"Wrote {pub_path} ({len(pub_payload['games'])} games)")
        written.append(pub_path)

    if flavor in ("local", "all"):
        loc_path = target_dir / LOCAL_DATA_JS.name
        loc_payload = title_catalog_payload(include_local=True, catalog_override=base)
        loc_path.write_text(
            "window.TITLE_REVIEW_DATA = " + json.dumps(loc_payload, indent=2) + ";\n",
            encoding="utf-8",
        )
        print(f"Wrote {loc_path} ({len(loc_payload['games'])} games)")
        written.append(loc_path)

    return written


def prune_stale_pngs(catalog: dict[str, Any]) -> None:
    expected = set()
    for g in catalog["games"]:
        for scr in g["screens"]:
            expected.add(Path(scr["vanilla"]["img"]).name)
            expected.add(Path(scr["ours"]["img"]).name)
    if OUT_DIR.is_dir():
        for p in OUT_DIR.glob("*.png"):
            if p.name not in expected:
                p.unlink()
                print(f"  Removed stale title preview: {p.relative_to(ROOT)}")


def generate_all(
    games: list[str] | None = None,
    tag: str = "both",
    capture_vanilla: bool = False,
    write_data_only: bool = False,
) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = [SPECS_BY_ID[g] for g in games] if games else TITLE_SPECS

    captured_builds: dict[str, int | None] = {}
    if not write_data_only:
        tags = ["vanilla", "modded"] if tag == "both" else [tag]
        for spec in targets:
            for t in tags:
                force = capture_vanilla if t == "vanilla" else True
                bnum = capture_game(spec, t, force=force)
                if t == "modded":
                    captured_builds[spec["id"]] = bnum

    catalog = build_catalog(
        allow_fallback=write_data_only,
        captured_builds=captured_builds if not write_data_only else None,
        prefer_existing=True,
    )
    if games is None and not write_data_only:
        prune_stale_pngs(catalog)

    write_title_review_data_js(catalog_override=catalog)
    return catalog


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--game",
        action="append",
        choices=[s["id"] for s in TITLE_SPECS],
        help="Game(s) to capture (defaults to all 11)",
    )
    parser.add_argument("--tag", choices=["vanilla", "modded", "both"], default="both")
    parser.add_argument("--capture-vanilla", action="store_true", help="Force re-capturing vanilla PNGs from roms/*.nes")
    parser.add_argument("--write-data-only", action="store_true", help="Only regenerate web/title_review_data.js")
    args = parser.parse_args()
    generate_all(
        games=args.game,
        tag=args.tag,
        capture_vanilla=args.capture_vanilla,
        write_data_only=args.write_data_only,
    )


if __name__ == "__main__":
    main()
