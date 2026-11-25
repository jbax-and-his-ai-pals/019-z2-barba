"""Capture real 60fps-derived NES gameplay scenes from headless Mesen for Barba Enterprise.

Runs a deterministic Lua capture script against both roms/z2.nes (vanilla) and
build/barba.nes (barba), cropping each scene to crisp PNG sprite strips in
web/previews/ (gitignored).
"""
from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

import emulator_test

ROOT = Path(__file__).resolve().parents[1]
CAP_DIR = ROOT / "build" / "fe-captures"
OUT_DIR = ROOT / "web" / "previews"

SCENES = [
    ("title", 256, 128, 16, 20),
    ("grass_walk", 256, 176, 48, 30),
    ("grass_attack", 256, 176, 84, 20),
    ("spell_scales", 256, 176, 48, 20),
    ("spell_wyrmling", 256, 176, 48, 20),
    ("spell_meteor", 256, 176, 48, 20),
    ("spell_inferno", 256, 176, 48, 20),
    ("saria_town", 256, 176, 104, 20),
    ("town_chaos", 256, 176, 64, 20),
    ("crossover_portals", 256, 176, 48, 20),
    ("ironknuckle_rebound", 256, 176, 64, 20),
    ("palace_roar", 256, 176, 48, 20),
    ("boss_meter", 256, 176, 48, 20),
    ("game_over", 256, 176, 64, 15),
]

LUA_TEMPLATE = r"""
dofile(TEST_DIR..'/newgame.lua')
local mem = emu.memType.nesMemory
local function r(a) return emu.read(a, mem) end
local function w(a, v) emu.write(a, v, mem) end

local TAG = __TAG__
local CAP_DIR = __CAP_DIR__
local frame = 0
local phase = 'title'
local phaseStart = 0
local captured = 0
local buffers = {}

local function openBuf(name)
    if not buffers[name] then
        buffers[name] = assert(io.open(CAP_DIR..'/'..TAG..'_'..name..'.rgba', 'wb'))
    end
    return buffers[name]
end

local function dumpCrop(name, cx, cy, cw, ch)
    local px = emu.getScreenBuffer()
    local f = openBuf(name)
    local chunks = {}
    for y = cy, cy + ch - 1 do
        local row = {}
        local base = y * 256 + 1
        for x = cx, cx + cw - 1 do
            local c = px[base + x]
            local rr = (c >> 16) & 0xFF
            local gg = (c >> 8) & 0xFF
            local bb = c & 0xFF
            row[#row + 1] = string.char(rr, gg, bb, 255)
        end
        chunks[#chunks + 1] = table.concat(row)
    end
    f:write(table.concat(chunks))
end

local function clearSpells()
    w(0x76F, 0); w(0x74A, 0); w(0x74B, 0)
    w(0x70F, 0); w(0x710, 0)
    w(0xD0, 0); w(0xD9, 0); w(0xDE, 0)
end

local function enterGrass()
    clearSpells()
    w(0x707, 0); w(0x706, 0); w(0x769, 1); w(0x561, 0)
    w(0x568, 0); w(0x56B, 0); w(0x56C, 0); w(0x701, 0)
    w(0x75C, 0); w(0x704, 0); w(0x73D, 0); w(0x726, 1)
    w(0x774, 255); w(0x784, 8); w(0x773, 0xFF)
    w(0x796, 0x14)
    w(0x748, 0xFF); w(0x563, 5); w(0x736, 0)
end

local function enterSariaOverworld()
    clearSpells()
    w(0x707, 0); w(0x706, 0); w(0x769, 1)
    w(0x73, 86); w(0x74, 8); w(0x562, 2)
    w(0x86, 0); w(0x87, 0); w(0x88, 0); w(0x89, 0)
    w(0x736, 2); w(0x726, 1)
end

local function enterSariaRiver()
    clearSpells()
    w(0xB5, 1); w(0x707, 1); w(0x706, 0); w(0x769, 3)
    w(0x56B, 2); w(0x561, 6); w(0x568, 1); w(0x56C, 1)
    w(0x701, 0); w(0x75C, 0); w(0x704, 0)
    w(0x736, 0); w(0x73D, 0); w(0x726, 1); w(0x748, 0x30)
    w(0x774, 255); w(0x784, 8)
end

local function enterRauruTown(page)
    clearSpells()
    w(0xB5, 1); w(0x707, 1); w(0x706, 0); w(0x769, 3)
    w(0x56B, 0); w(0x561, 1); w(0x568, 0); w(0x56C, 0)
    w(0x701, 0); w(0x75C, page); w(0x704, 0)
    w(0x736, 0); w(0x73D, 0); w(0x726, 1); w(0x748, 0x2C)
    w(0x774, 255); w(0x784, 8)
end

local function enterPalaceRoom(room, page)
    clearSpells()
    w(0xB5, 1); w(0x707, 3); w(0x706, 0); w(0x769, 3)
    w(0x56B, 1); w(0x561, room); w(0x568, 0); w(0x56C, 0)
    w(0x701, 0); w(0x75C, page); w(0x704, 0)
    w(0x736, 0); w(0x73D, 0); w(0x726, 1); w(0x748, 0x34)
    w(0x794, 6)
    for flag = 0x78D, 0x792 do w(flag, 0) end
    w(0x774, 255); w(0x784, 8)
end

local function enterGameOverCombat()
    clearSpells()
    w(0x707, 3); w(0x706, 0); w(0x70A, 0); w(0x769, 3)
    w(0x561, 5); w(0x568, 0); w(0x56B, 1); w(0x56C, 0)
    w(0x701, 0); w(0x75C, 0); w(0x704, 0)
    w(0x736, 0); w(0x73D, 0); w(0x726, 1)
    w(0x700, 1); w(0x774, 1); w(0x784, 8)
end

local function prepSpell(learnAddr, spellId)
    w(learnAddr, 1)
    w(0x0749, spellId)
    w(0x074A, 0)
    w(0x0773, 0xFF)
    w(0x0774, 255)
end

emu.addEventCallback(function()
    local dt = frame - phaseStart
    if phase == 'boot' then
        emu.setInput(newGameInput(frame), 0)
    elseif phase == 'grass_walk' then
        if dt < 30 then
            emu.setInput({right = true}, 0)
        elseif dt < 44 then
            emu.setInput({right = true, a = (dt < 38)}, 0)
        elseif dt < 72 then
            emu.setInput({left = true}, 0)
        elseif dt < 86 then
            emu.setInput({down = true}, 0)
        else
            emu.setInput({}, 0)
        end
    elseif phase == 'grass_attack' then
        local jump = (dt >= 90 and dt < 108) or (dt >= 140 and dt < 158) or (dt >= 195 and dt < 213)
        local fire = (dt >= 6 and dt < 10) or (dt >= 22 and dt < 26)
                  or (dt >= 46 and dt < 50) or (dt >= 66 and dt < 70)
                  or (dt >= 100 and dt < 105)
        local down = (dt >= 40 and dt < 84) or (dt >= 146 and dt < 182)
        local up = (dt >= 201 and dt < 237)
        emu.setInput({a = jump, b = fire, down = down, up = up}, 0)
    elseif phase == 'spell_scales' then
        local fire = (dt >= 96 and dt < 100) or (dt >= 118 and dt < 122)
        emu.setInput({select = (dt >= 30 and dt < 34), right = (dt >= 60 and dt < 90), b = fire}, 0)
    elseif phase == 'spell_wyrmling' then
        emu.setInput({select = (dt >= 30 and dt < 34), right = (dt >= 56 and dt < 105), up = (dt >= 60 and dt < 110), left = (dt >= 105 and dt < 140)}, 0)
    elseif phase == 'spell_meteor' then
        local fire = (dt >= 118 and dt < 122)
        emu.setInput({select = (dt >= 30 and dt < 34), right = (dt >= 90 and dt < 115), b = fire}, 0)
    elseif phase == 'spell_inferno' then
        local fire = (dt >= 56 and dt < 60) or (dt >= 76 and dt < 80) or (dt >= 96 and dt < 100) or (dt >= 116 and dt < 120)
        emu.setInput({select = (dt >= 30 and dt < 34), b = fire}, 0)
    elseif phase == 'saria_ow' then
        w(0x86, 0); w(0x87, 0); w(0x88, 0); w(0x89, 0)
        emu.setInput({down = true}, 0)
    elseif phase == 'saria_town' then
        emu.setInput({left = (dt >= 6)}, 0)
    elseif phase == 'saria_river' then
        emu.setInput({right = (dt >= 6 and dt < 540)}, 0)
    elseif phase == 'town_chaos' then
        local fire = (dt >= 12) and (dt % 14 < 4)
        emu.setInput({right = (dt >= 6 and dt < 110), left = (dt >= 110 and dt < 185), b = fire}, 0)
    elseif phase == 'crossover_portals' then
        local up = (dt >= 6 and dt < 40)
        local b = (dt >= 250 and dt < 260)
        emu.setInput({up = up, b = b}, 0)
    elseif phase == 'ironknuckle_rebound' then
        local jump = (dt >= 100 and dt < 120) or (dt >= 154 and dt < 174)
        local down = (dt >= 106 and dt < 140) or (dt >= 160 and dt < 194)
        local fire = (dt >= 110 and dt < 114) or (dt >= 124 and dt < 128) or (dt >= 164 and dt < 168) or (dt >= 178 and dt < 182)
        emu.setInput({right = (dt >= 6 and dt < 96), a = jump, down = down, b = fire}, 0)
    elseif phase == 'palace_roar' then
        local jump = (dt >= 6 and dt < 32)
        emu.setInput({right = (dt >= 6 and dt < 130), a = jump}, 0)
    elseif phase == 'boss_meter' then
        local fire = (dt >= 24) and (dt % 14 < 4)
        local jump = (dt >= 40 and dt < 56) or (dt >= 88 and dt < 104)
        emu.setInput({right = (dt >= 6 and dt < 70), a = jump, b = fire}, 0)
    elseif phase == 'game_over' then
        emu.setInput({right = (r(0x736) == 11 and r(0x774) > 0)}, 0)
    else
        emu.setInput({}, 0)
    end
end, emu.eventType.inputPolled)

local function waitReady(nextPhase)
    if frame >= phaseStart + 28 and r(0x736) == 11 and r(0x726) == 0 then
        phase = nextPhase
        phaseStart = frame
        captured = 0
        return true
    elseif r(0x736) == 5 and frame >= phaseStart + 10 then
        enterGrass()
        phaseStart = frame
        return false
    elseif frame > phaseStart + 180 then
        phase = nextPhase
        phaseStart = frame
        captured = 0
        return true
    end
    return false
end

emu.addEventCallback(function()
    frame = frame + 1
    if phase == 'title' then
        if frame >= 30 and frame % 4 == 0 and captured < 16 then
            dumpCrop('title', 0, 88, 256, 128)
            captured = captured + 1
            if captured >= 16 then phase = 'boot'; captured = 0 end
        end
    elseif phase == 'boot' then
        if frame >= 760 then enterGrass(); phase = 'grass_walk_wait'; phaseStart = frame end
    elseif phase == 'grass_walk_wait' then
        waitReady('grass_walk')
    elseif phase == 'grass_walk' then
        if (frame - phaseStart) % 2 == 0 and captured < 48 then
            dumpCrop('grass_walk', 0, 32, 256, 176)
            captured = captured + 1
            if captured >= 48 then enterGrass(); phase = 'grass_attack_wait'; phaseStart = frame; captured = 0 end
        end
    elseif phase == 'grass_attack_wait' then
        waitReady('grass_attack')
    elseif phase == 'grass_attack' then
        if (frame - phaseStart) % 3 == 0 and captured < 84 then
            dumpCrop('grass_attack', 0, 32, 256, 176)
            captured = captured + 1
            if captured >= 84 then enterGrass(); phase = 'spell_scales_wait'; phaseStart = frame; captured = 0 end
        end
    elseif phase == 'spell_scales_wait' then
        if waitReady('spell_scales') then prepSpell(0x077B, 0) end
    elseif phase == 'spell_scales' then
        if (frame - phaseStart) % 3 == 0 and captured < 48 then
            dumpCrop('spell_scales', 0, 32, 256, 176)
            captured = captured + 1
            if captured >= 48 then enterGrass(); phase = 'spell_wyrmling_wait'; phaseStart = frame; captured = 0 end
        end
    elseif phase == 'spell_wyrmling_wait' then
        if waitReady('spell_wyrmling') then prepSpell(0x077E, 3) end
    elseif phase == 'spell_wyrmling' then
        if (frame - phaseStart) % 3 == 0 and captured < 48 then
            dumpCrop('spell_wyrmling', 0, 32, 256, 176)
            captured = captured + 1
            if captured >= 48 then enterGrass(); phase = 'spell_meteor_wait'; phaseStart = frame; captured = 0 end
        end
    elseif phase == 'spell_meteor_wait' then
        if waitReady('spell_meteor') then prepSpell(0x0782, 7) end
    elseif phase == 'spell_meteor' then
        if (frame - phaseStart) % 3 == 0 and captured < 48 then
            dumpCrop('spell_meteor', 0, 32, 256, 176)
            captured = captured + 1
            if captured >= 48 then enterGrass(); phase = 'spell_inferno_wait'; phaseStart = frame; captured = 0 end
        end
    elseif phase == 'spell_inferno_wait' then
        if waitReady('spell_inferno') then prepSpell(0x077F, 4) end
    elseif phase == 'spell_inferno' then
        if (frame - phaseStart) % 3 == 0 and captured < 48 then
            dumpCrop('spell_inferno', 0, 32, 256, 176)
            captured = captured + 1
            if captured >= 48 then enterSariaOverworld(); phase = 'saria_ow_wait'; phaseStart = frame; captured = 0 end
        end
    elseif phase == 'saria_ow_wait' then
        if frame >= phaseStart + 12 and r(0x736) == 5 then
            phase = 'saria_ow'; phaseStart = frame; captured = 0
        elseif frame > phaseStart + 120 then
            phase = 'saria_ow'; phaseStart = frame; captured = 0
        end
    elseif phase == 'saria_ow' then
        if r(0x736) ~= 5 then
            phase = 'saria_town_wait'; phaseStart = frame
        elseif (frame - phaseStart) % 3 == 0 and captured < 16 then
            dumpCrop('saria_town', 0, 64, 256, 176)
            captured = captured + 1
        end
    elseif phase == 'saria_town_wait' then
        if r(0x736) == 11 and r(0x726) == 0 and frame >= phaseStart + 6 then
            phase = 'saria_town'; phaseStart = frame
        elseif frame > phaseStart + 180 then
            phase = 'saria_town'; phaseStart = frame
        end
    elseif phase == 'saria_town' then
        if r(0x736) == 11 and (frame - phaseStart) % 3 == 0 and captured < 40 then
            dumpCrop('saria_town', 0, 64, 256, 176)
            captured = captured + 1
            if captured >= 40 then
                enterSariaRiver()
                phase = 'saria_river_wait'; phaseStart = frame
            end
        end
    elseif phase == 'saria_river_wait' then
        if r(0x736) == 11 and r(0x726) == 0 and frame >= phaseStart + 28 then
            phase = 'saria_river'; phaseStart = frame
        elseif frame > phaseStart + 180 then
            phase = 'saria_river'; phaseStart = frame
        end
    elseif phase == 'saria_river' then
        local dt = frame - phaseStart
        if r(0x736) == 11 and dt % 8 == 0 and captured < 104 then
            dumpCrop('saria_town', 0, 64, 256, 176)
            captured = captured + 1
            if captured >= 104 then
                enterRauruTown(1)
                phase = 'town_chaos_wait'; phaseStart = frame; captured = 0
            end
        end
    elseif phase == 'town_chaos_wait' then
        waitReady('town_chaos')
    elseif phase == 'town_chaos' then
        if (frame - phaseStart) % 3 == 0 and captured < 64 then
            dumpCrop('town_chaos', 0, 32, 256, 176)
            captured = captured + 1
            if captured >= 64 then
                enterRauruTown(1)
                phase = 'crossover_portals_wait'; phaseStart = frame; captured = 0
            end
        end
    elseif phase == 'crossover_portals_wait' then
        if waitReady('crossover_portals') then
            w(0x3B, 1); w(0x4D, 40); w(0x70, 0)
        end
    elseif phase == 'crossover_portals' then
        local dt = frame - phaseStart
        if dt >= 240 and dt % 2 == 0 and captured < 48 then
            dumpCrop('crossover_portals', 0, 32, 256, 176)
            captured = captured + 1
            if captured >= 48 then
                enterPalaceRoom(5, 0)
                phase = 'ironknuckle_rebound_wait'; phaseStart = frame; captured = 0
            end
        end
    elseif phase == 'ironknuckle_rebound_wait' then
        waitReady('ironknuckle_rebound')
    elseif phase == 'ironknuckle_rebound' then
        local dt = frame - phaseStart
        if dt >= 36 and dt % 3 == 0 and captured < 64 then
            dumpCrop('ironknuckle_rebound', 0, 32, 256, 176)
            captured = captured + 1
            if captured >= 64 then
                enterPalaceRoom(0x0D, 3)
                phase = 'palace_roar_wait'; phaseStart = frame; captured = 0
            end
        end
    elseif phase == 'palace_roar_wait' then
        if waitReady('palace_roar') then
            w(0x3B, 3); w(0x4D, 112); w(0x29, 144); w(0x57D, 0); w(0x479, 0)
        end
    elseif phase == 'palace_roar' then
        if (frame - phaseStart) % 3 == 0 and captured < 48 then
            dumpCrop('palace_roar', 0, 32, 256, 176)
            captured = captured + 1
            if captured >= 48 then
                enterPalaceRoom(0x0D, 1)
                phase = 'boss_meter_wait'; phaseStart = frame; captured = 0
            end
        end
    elseif phase == 'boss_meter_wait' then
        waitReady('boss_meter')
    elseif phase == 'boss_meter' then
        if (frame - phaseStart) % 3 == 0 and captured < 48 then
            dumpCrop('boss_meter', 0, 32, 256, 176)
            captured = captured + 1
            if captured >= 48 then
                enterGameOverCombat()
                phase = 'gameover_wait'; phaseStart = frame; captured = 0
            end
        end
    elseif phase == 'gameover_wait' then
        if r(0x736) == 11 and r(0x726) == 0 and frame >= phaseStart + 28 then
            phase = 'game_over'; phaseStart = frame; captured = 0
        elseif frame > phaseStart + 180 then
            phase = 'game_over'; phaseStart = frame; captured = 0
        end
    elseif phase == 'game_over' then
        if (frame - phaseStart) % 6 == 0 and captured < 64 then
            dumpCrop('game_over', 0, 32, 256, 176)
            captured = captured + 1
            if captured >= 64 then
                for _, f in pairs(buffers) do f:close() end
                stopScenario(0)
            end
        end
    end
end, emu.eventType.endFrame)
"""


def write_png_from_frames(raw_path: Path, out_png: Path, w: int, h: int, n_frames: int) -> None:
    data = raw_path.read_bytes()
    frame_bytes = w * h * 4
    if len(data) < frame_bytes * n_frames:
        raise ValueError(f"{raw_path} too short: {len(data)} < {frame_bytes * n_frames}")
    strip_w = w * n_frames
    rows = bytearray()
    row_bytes = w * 4
    for y in range(h):
        rows.append(0)
        for f in range(n_frames):
            off = f * frame_bytes + y * row_bytes
            rows.extend(data[off : off + row_bytes])

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    out_png.parent.mkdir(parents=True, exist_ok=True)
    out_png.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", strip_w, h, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows), 6))
        + chunk(b"IEND", b"")
    )


def run_capture(tag: str, rom: Path) -> None:
    CAP_DIR.mkdir(parents=True, exist_ok=True)
    lua_path = ROOT / "build" / f"fe_capture_{tag}.lua"
    script = LUA_TEMPLATE.replace("__TAG__", json.dumps(tag)).replace("__CAP_DIR__", json.dumps(CAP_DIR.as_posix()))
    lua_path.write_text(script, encoding="utf-8")
    rc = emulator_test.run(lua_path, rom, timeout=90)
    if rc != 0:
        raise SystemExit(f"Capture failed for {tag} ({rom}) with exit code {rc}")
    for name, w, h, n_frames, _fps in SCENES:
        raw_path = CAP_DIR / f"{tag}_{name}.rgba"
        out_png = OUT_DIR / f"cap_{tag}_{name}.png"
        write_png_from_frames(raw_path, out_png, w, h, n_frames)
        print(f"Wrote {out_png} ({w}x{h} x {n_frames} frames)")


def main() -> None:
    run_capture("vanilla", ROOT / "roms" / "z2.nes")
    run_capture("barba", ROOT / "build" / "barba.nes")


if __name__ == "__main__":
    main()
