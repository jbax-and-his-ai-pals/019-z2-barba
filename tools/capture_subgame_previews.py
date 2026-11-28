"""Capture real 60fps-derived NES gameplay scenes from headless Mesen for all 10 subgames.

Runs deterministic Lua capture scripts against both roms/<game>.nes (vanilla) and
play/nes/<game>-b*.nes (modded), packing frames into compact 2D-grid PNGs
in web/previews/subgames/ and writing web/subgames_data.js.
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import zlib
from pathlib import Path
from typing import Any

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import emulator_test  # noqa: E402
import subgame_pack  # noqa: E402

ROOT = _TOOLS_DIR.parent
CAP_DIR = ROOT / "build" / "subgame-captures"
OUT_DIR = ROOT / "web" / "previews" / "subgames"
DATA_JS = ROOT / "web" / "subgames_data.js"
LOCAL_DATA_JS = ROOT / "web" / "local_subgames_data.js"

# Common RGBA capture helper prepended to every game Lua script.
LUA_COMMON = r"""
local mem = emu.memType.nesMemory
local oam = emu.memType.nesSpriteRam
local ppu = emu.memType.nesPpuDebug
local function r(a) return emu.read(a, mem) end
local function w(a, v) emu.write(a, v, mem) end
local function rPpu(a) return emu.read(a, ppu) end

local buffers = {}
local counts = {}
local closed = false

local function openBuf(name)
    if not buffers[name] then
        buffers[name] = assert(io.open(CAP_DIR .. '/' .. TAG .. '_' .. name .. '.rgba', 'wb'))
        counts[name] = 0
    end
    return buffers[name]
end

local function dumpCrop(name, cx, cy, cw, ch)
    if closed then return end
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
    counts[name] = counts[name] + 1
end

local function closeAll()
    if closed then return end
    closed = true
    for _, f in pairs(buffers) do
        f:close()
    end
    buffers = {}
end
"""

# ---------------------------------------------------------------------------
# Per-game Lua capture scripts (run identically on vanilla & modded ROMs)
# ---------------------------------------------------------------------------

WALDO_LUA = LUA_COMMON + r"""
local frame = 0
local stage = 'title'
local sf = 0
local phaseF = 0
local settleF = 0
local owF = 0
local moonF = 0
local jumpToSubway = false
local jumpToSlots = false
local inp = {}
local waitFrames = 0
local aTimer = 0
local slotPhase = 'wait_hand'

emu.addMemoryCallback(function()
    if jumpToSubway then
        jumpToSubway = false
        if TAG == 'modded' then
            w(0x7F00, 0)
            w(0x7F02, 0)
            w(0x7F90, 0)
        end
        w(0x0601, 5)
        w(0x0603, 0)
        emu.setState({['cpu.pc'] = 0xE185})
    elseif jumpToSlots then
        jumpToSlots = false
        if TAG == 'modded' then
            w(0x7F00, 0)
            w(0x7F02, 0)
            w(0x7F90, 0)
        end
        w(0x0601, 6)
        w(0x0603, 0)
        emu.setState({['cpu.pc'] = 0xE1A0})
    end
end, emu.callbackType.exec, 0x8000, 0xFFFF)

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame = frame + 1
    inp = {}

    if stage == 'title' then
        if frame == 180 or frame == 240 then
            inp = {start = true}
        end
        if frame >= 255 and (frame % 3 == 0) and (counts.title or 0) < 48 then
            dumpCrop('title', 0, 8, 256, 224)
            if counts.title >= 48 then
                stage = 'wait_skill'
                phaseF = 0
                settleF = 0
            end
        end

    elseif stage == 'wait_skill' then
        phaseF = phaseF + 1
        if phaseF <= 2 then
            inp = {start = true}
        end
        if phaseF > 10 and r(0x0703) == 154 and r(0x0700) == 108 then
            settleF = settleF + 1
            if settleF >= 10 then
                stage = 'cap_skill'
                phaseF = 0
            end
        elseif phaseF > 400 then
            error('Timed out waiting for Skill Select')
        end

    elseif stage == 'cap_skill' then
        phaseF = phaseF + 1
        if (phaseF % 2 == 0) and (counts.skill_select or 0) < 32 then
            dumpCrop('skill_select', 0, 8, 256, 224)
            if counts.skill_select >= 32 then
                stage = 'wait_ticket'
                phaseF = 0
                settleF = 0
            end
        end

    elseif stage == 'wait_ticket' then
        phaseF = phaseF + 1
        if phaseF <= 2 then
            inp = {start = true}
        end
        if phaseF > 6 and r(0x0700) >= 0xF0 then
            settleF = settleF + 1
            if settleF >= 25 then
                stage = 'cap_ticket'
                phaseF = 0
            end
        elseif phaseF > 300 then
            error('Timed out waiting for Ticket screen')
        end

    elseif stage == 'cap_ticket' then
        phaseF = phaseF + 1
        if (phaseF % 2 == 0) and (counts.moon_ticket or 0) < 24 then
            dumpCrop('moon_ticket', 0, 8, 256, 224)
            if counts.moon_ticket >= 24 then
                stage = 'overworld'
                owF = 0
            end
        end

    elseif stage == 'overworld' then
        owF = owF + 1
        if owF <= 2 then
            inp = {start = true}
        end
        if owF >= 500 and (owF % 3 == 0) and (counts.overworld_map or 0) < 40 then
            dumpCrop('overworld_map', 0, 8, 256, 224)
        end
        if (counts.overworld_map or 0) >= 40 and r(0x0700) == 31 and r(0x0701) == 0x80 and r(0x0703) == 0 then
            stage = 'wait_train'
            phaseF = 0
        elseif owF > 1200 then
            error('Timed out waiting for Train Station')
        end

    elseif stage == 'wait_train' then
        phaseF = phaseF + 1
        if phaseF >= 35 then
            stage = 'cap_train'
            phaseF = 0
        end

    elseif stage == 'cap_train' then
        phaseF = phaseF + 1
        if (phaseF % 2 == 0) and (counts.train_station or 0) < 48 then
            dumpCrop('train_station', 0, 8, 256, 224)
            if counts.train_station >= 48 then
                jumpToSubway = true
                stage = 'wait_subway'
                sf = 0
                settleF = 0
            end
        end

    elseif stage == 'wait_subway' then
        sf = sf + 1
        if sf > 540 and r(0x0705) == 0x78 and r(0x0709) == 0x79 and r(0x00) == 0x88 and r(0x01) == 0x1E then
            settleF = settleF + 1
            if settleF >= 15 then
                stage = 'cap_subway'
                phaseF = 0
            end
        elseif sf > 900 then
            error('Timed out waiting for Subway level')
        end

    elseif stage == 'cap_subway' then
        phaseF = phaseF + 1
        if (phaseF % 3 == 0) and (counts.subway or 0) < 24 then
            dumpCrop('subway', 0, 8, 256, 224)
            if counts.subway >= 24 then
                jumpToSlots = true
                stage = 'wait_slots'
                sf = 0
            end
        end

    elseif stage == 'wait_slots' then
        sf = sf + 1
        if sf == 740 then
            stage = 'slots'
            sf = 0
            slotPhase = 'wait_hand'
        end

    elseif stage == 'slots' then
        sf = sf + 1
        if aTimer > 0 then
            aTimer = aTimer - 1
            inp.a = (aTimer > 0)
        end
        if sf >= 216 and (sf % 4 == 0) and (counts.slots or 0) < 96 then
            dumpCrop('slots', 0, 8, 256, 224)
        end
        local hx = r(0x703)
        if sf == 5 then
            aTimer = 4
            slotPhase = 'wait_hand'
        elseif slotPhase == 'wait_hand' and hx == 172 then
            waitFrames = 40
            slotPhase = 'r3_delay'
        elseif slotPhase == 'r3_delay' then
            waitFrames = waitFrames - 1
            if waitFrames <= 0 then slotPhase = 'r3_aim' end
        elseif slotPhase == 'r3_aim' and r(0x238) == 1 then
            aTimer = 4
            waitFrames = 20
            slotPhase = 'r3_settle'
        elseif slotPhase == 'r3_settle' then
            waitFrames = waitFrames - 1
            if waitFrames <= 0 then slotPhase = 'move_r2' end
        elseif slotPhase == 'move_r2' then
            if hx > 112 then inp.left = true else slotPhase = 'r2_aim' end
        elseif slotPhase == 'r2_aim' and r(0x228) == 1 then
            aTimer = 4
            waitFrames = 20
            slotPhase = 'r2_settle'
        elseif slotPhase == 'r2_settle' then
            waitFrames = waitFrames - 1
            if waitFrames <= 0 then slotPhase = 'move_r1' end
        elseif slotPhase == 'move_r1' then
            if hx > 48 then inp.left = true else slotPhase = 'r1_aim' end
        elseif slotPhase == 'r1_aim' and r(0x218) == 1 then
            aTimer = 4
            slotPhase = 'wait_moon'
        elseif slotPhase == 'wait_moon' then
            if (counts.slots or 0) >= 96 and r(0x0601) == 0x08 and r(0x04) == 0xF8 and r(0x0700) >= 0xF0 and r(0x07E0) < 0xE0 then
                slotPhase = 'cap_moon'
                moonF = 0
            elseif sf > 2600 then
                error('Timed out waiting for Moon jump')
            end
        elseif slotPhase == 'cap_moon' then
            moonF = moonF + 1
            if ((moonF - 1) % 5 == 0) and (counts.moon_ending or 0) < 100 then
                dumpCrop('moon_ending', 0, 8, 256, 224)
                if counts.moon_ending >= 100 then
                    closeAll()
                    emu.stop(0)
                end
            end
        end
    end
end, emu.eventType.endFrame)
"""

F13_LUA = LUA_COMMON + r"""
local frame = 0
local phase = 'boot'
local phaseStart = 0
local inp = {}
local extState = nil
local wantSave = false
local wantLoad = nil

emu.addMemoryCallback(function()
    if wantSave then
        wantSave = false
        extState = emu.createSavestate()
        phase = 'enter_cabin'
        phaseStart = frame
    elseif wantLoad then
        local nextPhase = wantLoad
        wantLoad = nil
        assert(emu.loadSavestate(extState), 'load extState failed')
        phase = nextPhase
        phaseStart = frame
    end
end, emu.callbackType.exec, 0x8000, 0xFFFF)

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame = frame + 1
    local dt = frame - phaseStart
    inp = {}

    if phase == 'boot' then
        if (frame >= 380 and frame < 385) or (frame >= 460 and frame < 465) then
            inp = {start = true}
        elseif frame >= 502 and frame < 538 and (frame % 2 == 0) and (counts.camp_map or 0) < 18 then
            dumpCrop('camp_map', 0, 8, 256, 224)
        elseif frame >= 540 and frame < 546 then
            inp = {start = true}
        elseif frame >= 548 and frame < 560 and (frame % 2 == 0) and (counts.camp_map or 0) < 24 then
            dumpCrop('camp_map', 0, 8, 256, 224)
        elseif frame == 970 then
            wantSave = true
            phase = 'saving_ext'
        end

    elseif phase == 'enter_cabin' then
        if r(0x38) == 2 and r(0x37) == 2 then
            phase = 'cabin_inside'
            phaseStart = frame
        else
            inp = (dt < 20) and {up = true} or {right = true, up = ((dt % 12) < 6)}
            if dt > 700 then error('Timed out entering cabin') end
        end

    elseif phase == 'cabin_inside' then
        if dt >= 25 and (dt % 2 == 0) and (counts.cabin_inside or 0) < 24 then
            dumpCrop('cabin_inside', 0, 8, 256, 224)
            if counts.cabin_inside >= 24 then
                wantLoad = 'exterior_volley'
                phase = 'loading_ext'
            end
        end

    elseif phase == 'exterior_volley' then
        if dt < 16 then
            inp = {down = true}
        elseif dt < 44 then
            inp = {right = true, b = ((dt % 12) < 3)}
        else
            inp = {right = true, b = ((dt % 16) < 4)}
        end
        if dt >= 2 and (dt % 2 == 0) and (counts.exterior_volley or 0) < 48 then
            dumpCrop('exterior_volley', 0, 8, 256, 224)
            if counts.exterior_volley >= 48 then
                wantLoad = (TAG == 'modded') and 'trigger_coven' or 'walk_south'
                phase = 'loading_ext'
            end
        end

    elseif phase == 'trigger_coven' then
        w(0x0507, 4) -- Debbie
        w(0x0420, 0) -- grounded
        w(0x0528, 0x20)
        if dt >= 8 then
            w(0x38, 1); w(0xC5, 8); w(0xC9, 0x0B); w(0x45, 1); w(0x44, 0x20)
        end
        if r(0x7C60) ~= 0 then
            phase = 'coven_cutscene'
            phaseStart = frame
        elseif dt > 120 then
            error(string.format('Timed out triggering coven ($0507=%02X $38=%02X $C5=%02X $C9=%02X $45=%02X $44=%02X)',
                r(0x0507), r(0x38), r(0xC5), r(0xC9), r(0x45), r(0x44)))
        end

    elseif phase == 'walk_south' then
        w(0x0507, 4) -- Debbie for deterministic south/north forest path & cliff coven
        w(0x0528, 0x20)
        if r(0x45) == 0x01 and r(0x44) >= 0xE0 then
            inp = ((dt % 10) < 7) and {down = true} or {right = true}
        else
            inp = {right = true}
        end
        if TAG == 'vanilla' then
            if r(0x45) == 0x03 or dt >= 700 then
                phase = 'forest_walk'
                phaseStart = frame
            end
        elseif dt >= 790 and r(0x45) == 0x00 and r(0x4E) == 0x01 then
            phase = 'walk_north'
            phaseStart = frame
        elseif dt > 2400 then
            error(string.format('Timed out reaching south road ($45=%02X $44=%02X $4E=%02X)', r(0x45), r(0x44), r(0x4E)))
        end

    elseif phase == 'walk_north' then
        w(0x0507, 4)
        w(0x0528, 0x20)
        if (r(0x45) == 0x03 and r(0x44) >= 0xD0) or (r(0x45) == 0x04 and r(0x44) <= 0x20) then
            inp = ((dt % 10) < 7) and {up = true} or {right = true}
        else
            inp = {right = true}
        end
        if r(0x38) == 0x01 then
            phase = 'forest_walk'
            phaseStart = frame
        elseif dt > 2400 then
            error(string.format('Timed out entering north forest ($38=%02X $45=%02X $44=%02X $4E=%02X)', r(0x38), r(0x45), r(0x44), r(0x4E)))
        end

    elseif phase == 'forest_walk' then
        w(0x0528, 0x20)
        inp = {right = true}
            if TAG == 'modded' then
                if r(0x7C60) ~= 0 then
                    phase = 'coven_cutscene'
                    phaseStart = frame
                elseif dt > 1400 then
                    error(string.format('Timed out waiting for coven trigger ($0507=%02X $38=%02X $C5=%02X $C9=%02X $45=%02X $44=%02X $4E=%02X)',
                        r(0x0507), r(0x38), r(0xC5), r(0xC9), r(0x45), r(0x44), r(0x4E)))
                end
            else
            if dt >= 200 and (dt % 4 == 0) and (counts.forest_coven or 0) < 48 then
                dumpCrop('forest_coven', 0, 8, 256, 224)
                if counts.forest_coven >= 48 then
                    closeAll()
                    emu.stop(0)
                end
            end
        end

    elseif phase == 'coven_cutscene' then
        if dt > 250 and dt < 620 then
            inp = {b = true, a = (dt % 35 == 0)}
        end
        -- Capture 4-Barba coven dialogue + Debbie cliff levitation & drop (dt 340..628)
        if dt >= 340 and (dt % 6 == 0) and (counts.forest_coven or 0) < 48 then
            dumpCrop('forest_coven', 0, 8, 256, 224)
            if counts.forest_coven >= 48 then
                closeAll()
                emu.stop(0)
            end
        end
    end
end, emu.eventType.endFrame)
"""

FEUD_LUA = LUA_COMMON + r"""
local ALL_MAIN = {
    [0]={'HORSE HEAD','HELMET HEAD','REBONACK','CAROCK','GOOMA','BARBA','THUNDER BIRD','DARK LINK'},
    [1]={'CANDLE','GLOVE','RAFT','BOOTS','FLUTE','CROSS','HAMMER','MAGIC KEY'},
    [2]={'SHIELD','JUMP','LIFE','FAIRY','FIRE','REFLECT','SPELL','THUNDER'},
    [3]={'SWORD','DOWN STAB','UP STAB','BEAM','FIREBALL','THUNDER'},
    [4]={'PARAPA PALACE','MIDORO PALACE','ISLAND PALACE','MAZE PALACE','OCEAN PALACE','THREE-EYE ROCK','GREAT PALACE'},
    [5]={'RAURU','RUTO','SARIA','MIDO','NABOORU','DARUNIA','NEW KASUTO','OLD KASUTO'},
    [6]={'200','500','1000','2000','3000','5000','8000'},
    [7]={'100','300','700','1200','2200','3500','6000'},
    [8]={'50','150','400','800','1500','2500','4000'},
    [9]={'STALFOS','IRON KNUCKLE','BOT','BIT','BUBBLE','RA'},
    [10]={'IRON KNUCKLE','STALFOS','GORIYA','DOOM KNOCKER','MAU','BUBBLE'},
    [11]={'WIZZROBE','MAGO','IRON KNUCKLE','STALFOS','BUBBLE','MOA'},
    [12]={'FOKKA','FOKKERU','BUBBLE','BOT','THUNDER BIRD','DARK LINK'},
    [13]={'DARIA','TEKTITE','OCTOROK','GORIYA','BUBBLE'},
    [14]={'GRASS','SWAMP','DESERT','FOREST','GRAVEYARD','LAVA'},
    [15]={'HEALER','ERROR','SAGE','BAGU','KNIGHT','CHIMNEY'},
    [16]={'RAFT','BOOTS','FAIRY SPELL','BRIDGE'},
    [17]={'P-BAG','RED MAGIC JAR','BLUE MAGIC JAR','KEY'},
    [18]={'FAIRY','LIFE SPELL','TOWN LADY','LEVEL UP','RED MAGIC JAR'},
    [19]={'THUNDER BIRD','DARK LINK','OLD MAN'},
    [20]={'CAVE','WATER','DESERT','SWAMP','TOWN'},
    [21]={'DEATH MOUNTAIN','CAVE','RAURU','MAZE ISLAND','OLD KASUTO'},
    [22]={'ATTACK','MAGIC','LIFE'},
    [23]={'LINK','ZELDA','BARBA','ERROR','GANON','BAGU','IMPA'},
    [24]={'ROAD','BRIDGE','CAVE','TOWN','PALACE','RIVER'},
    [25]={'COURAGE','POWER','WISDOM'},
    [26]={'SHIELD','JUMP','LIFE','FAIRY'},
    [27]={'FIRE','REFLECT','SPELL','THUNDER'},
    [28]={'FAIRY','FOKKA','THUNDER BIRD','FOKKERU','ACHE','MOA'},
    [29]={'HEAL','LEARN SPELL','MAGIC','TALK','QUEST'},
    [30]={'P-BAG','KILL ENEMIES','PALACE CRYSTAL','BOSS'},
    [31]={'IRON KNUCKLE','STALFOS','REBONACK','FOKKA','DOOM KNOCKER'},
    [32]={'ROCK','TREE','SPECTACLE ROCK'},
    [33]={'GELDARM','LEEVER','MOBLIN','OCTOROK','BOT'},
    [34]={'THUNDER','FAIRY','SPELL','LIFE'},
}
local FM_ANS1 = {
    [0]='SCALES', [1]='200', [2]='ORANGE', [3]='TROPHY', [4]='LIFE',
    [5]='MOBLIN', [6]='WEST HYRULE', [7]='DOLL', [8]='RED', [9]='LAVA',
    [10]='LIFE', [11]='BARBA', [12]='GANON', [13]='ROCK', [14]='SPELL',
    [15]='PARAPA PALACE', [16]='NABOORU', [17]='8', [18]='SIGNS', [19]='ERROR',
    [20]='FORWARD', [21]='BARBA', [22]='BARBA', [23]='RED', [24]='LIFE',
    [25]='TEKTITE', [26]='PIT',
}

local f = 0
local inp = {}
local submit_cool = 0
local scrEnter = {}
local phase = 'main'
local stageState = nil
local wantSave = false
local wantLoad = false
local fmStart = nil
local fmSubmitted = false
local loseEnter = nil

local function submitText(txt)
    for i = 1, #txt do w(0x0360 + i - 1, string.byte(txt, i)) end
    w(0x0360 + #txt, 0); w(0x035F, #txt); w(0x0347, 8); w(0x0348, 7); submit_cool = 12
end

emu.addMemoryCallback(function()
    if wantSave then
        wantSave = false
        stageState = emu.createSavestate()
        phase = 'go_fast_money'
    elseif wantLoad then
        wantLoad = false
        assert(emu.loadSavestate(stageState), 'load stageState failed')
        submit_cool = 0
        phase = 'go_lose'
    end
end, emu.callbackType.exec, 0xCA77, 0xCA77)

emu.addEventCallback(function() emu.setInput(inp, 0) end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    f = f + 1
    inp = {}

    local scr = r(0x0345)
    local mode = r(0x04D3)
    local kbd = r(0x035E)
    local fms = r(0x04E2)
    local q = r(0x0317)

    if phase == 'saving' or phase == 'loading' then
        return
    end

    if submit_cool > 0 then
        submit_cool = submit_cool - 1
        if submit_cool >= 8 and submit_cool <= 10 then inp = {a = true} end
        return
    end

    if phase == 'main' then
        if scr == 0x01 then
            if f >= 230 and (counts.title or 0) < 24 then
                if f % 2 == 0 then dumpCrop('title', 0, 8, 256, 224) end
            elseif f % 20 == 0 then
                inp = {start = true}
            end
            return
        end

        if f <= 520 then
            if f % 40 == 0 then inp = {start = true} end
            return
        end

        if scr == 0x05 then
            if f % 14 < 2 then inp = {a = true} end
            return
        end

        if scr == 0x06 and mode == 1 then
            if not scrEnter.overview then scrEnter.overview = f end
            if f >= scrEnter.overview + 25 and (counts.overview or 0) < 32 then
                if f % 2 == 0 then dumpCrop('overview', 0, 8, 256, 224) end
            elseif (counts.overview or 0) >= 32 and f % 20 == 0 then
                inp = {a = true}
            end
            return
        end

        if scr == 0x09 and mode == 2 then
            if not scrEnter.faceoff then scrEnter.faceoff = f end
            if f >= scrEnter.faceoff + 45 and (counts.faceoff or 0) < 32 then
                if f % 2 == 0 then dumpCrop('faceoff', 0, 8, 256, 224) end
            elseif (counts.faceoff or 0) >= 32 then
                if kbd == 0 and f % 12 == 0 then inp = {a = true}
                elseif kbd == 1 then
                    if TAG == 'modded' then
                        submitText((ALL_MAIN[q] and ALL_MAIN[q][1]) or 'BARBA')
                    else
                        -- On vanilla, submit 'ZZZZ' (wrong answer) so CPU buzzes & moves to stage screen
                        submitText('ZZZZ')
                    end
                end
            end
            return
        end

        if scr == 0x0D and mode == 0 and fms == 0 then
            if not scrEnter.stage_barba then scrEnter.stage_barba = f end
            if f >= scrEnter.stage_barba + 30 and (counts.stage_barba or 0) < 32 then
                if f % 2 == 0 then dumpCrop('stage_barba', 0, 8, 256, 224) end
            elseif (counts.stage_barba or 0) >= 32 then
                if kbd == 1 then
                    submitText('ZZZZ')
                elseif f % 16 == 0 then
                    inp = {a = true}
                end
            end
            return
        end

        if scr == 0x0E and mode == 0 then
            if not scrEnter.stage_z2 then scrEnter.stage_z2 = f end
            if f >= scrEnter.stage_z2 + 30 and (counts.stage_z2 or 0) < 32 then
                if f % 2 == 0 then dumpCrop('stage_z2', 0, 8, 256, 224) end
            elseif (counts.stage_z2 or 0) >= 32 then
                -- If vanilla reached 0x0E before 0x0D (because CPU won faceoff), capture stage_barba fallback
                if (counts.stage_barba or 0) < 32 then
                    if f % 2 == 0 then dumpCrop('stage_barba', 0, 8, 256, 224) end
                end
                if (counts.stage_barba or 0) >= 32 and (counts.stage_z2 or 0) >= 32 then
                    wantSave = true
                    phase = 'saving'
                end
            end
            return
        end

    elseif phase == 'go_fast_money' then
        if mode == 3 and scr == 0x03 then
            if not fmStart and kbd == 1 then fmStart = f end
            if fmStart then
                if f >= fmStart + 10 then
                    if (counts.fast_money or 0) == 14 and not fmSubmitted and kbd == 1 then
                        fmSubmitted = true
                        submitText(TAG == 'modded' and (FM_ANS1[r(0x031B)] or 'BARBA') or 'APPLE')
                        return
                    end
                    if (f - fmStart) % 4 == 0 and (counts.fast_money or 0) < 32 then
                        dumpCrop('fast_money', 0, 8, 256, 224)
                    end
                    if (counts.fast_money or 0) >= 32 then
                        wantLoad = true
                        phase = 'loading'
                    end
                end
            elseif f % 20 == 0 then
                inp = {a = true}
            end
            return
        elseif fms == 1 and scr ~= 0x03 then
            if f % 20 == 0 then inp = {a = true} end
            return
        else
            w(0x04C3, 0x2C); w(0x04C4, 0x01); w(0x04C5, 0); w(0x04C6, 0)
            if kbd == 1 then submitText('ZZZZ') elseif f % 16 == 0 then inp = {a = true} end
            return
        end

    elseif phase == 'go_lose' then
        if scr == 0x0F or scr == 0x10 or scr == 0x11 then
            if not loseEnter then loseEnter = f end
            if f >= loseEnter + 35 and (f - loseEnter) % 2 == 0 and (counts.lose_excuse or 0) < 16 then
                dumpCrop('lose_excuse', 0, 8, 256, 224)
            end
            if (counts.lose_excuse or 0) >= 16 then
                closeAll()
                emu.stop(0)
            end
            return
        else
            w(0x04C3, 0); w(0x04C4, 0); w(0x04C5, 0x2C); w(0x04C6, 0x01)
            if kbd == 1 then submitText('ZZZZ') elseif f % 16 == 0 then inp = {a = true} end
            return
        end
    end

    if f % 20 == 0 then inp = {a = true} end
    if f >= 36000 then error(string.format('Feud capture timed out phase=%s scr=%02X mode=%02X fms=%02X', phase, scr, mode, fms)) end
end, emu.eventType.endFrame)
"""

DK_LUA = LUA_COMMON + r"""
local frame = 0
local phase = 'title'
local phaseStart = 0
local inp = {}

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

local function jumpStage(stageId)
    w(0x00A0, 0)
    w(0x009F, 0)
    w(0x0053, stageId)
    w(0x0043, 0x76)
    w(0x004E, 0)
    w(0x004F, 0)
    w(0x009A, 0)
end

emu.addEventCallback(function()
    frame = frame + 1
    local dt = frame - phaseStart
    inp = {}

    if phase == 'title' then
        if frame >= 30 and (frame % 2 == 0) and (counts.title or 0) < 24 then
            dumpCrop('title', 0, 8, 256, 224)
            if counts.title >= 24 then
                phase = 'press_start'
                phaseStart = frame
            end
        end

    elseif phase == 'press_start' then
        if dt < 6 then
            inp = {start = true}
        else
            phase = 'wait_25m'
            phaseStart = frame
        end

    elseif phase == 'wait_25m' then
        if r(0x004E) == 0 and r(0x004F) == 1 then
            phase = 'stage_25m'
            phaseStart = frame
        elseif dt > 600 then
            error('Timed out waiting for 25m start')
        end

    elseif phase == 'stage_25m' then
        if dt >= 70 and dt < 150 then
            inp = {right = (dt < 110), a = (dt >= 90 and dt < 96)}
            if (dt % 2 == 0) and (counts.stage_25m or 0) < 40 then
                dumpCrop('stage_25m', 0, 8, 256, 224)
            end
        elseif dt == 150 then
            w(0x00A0, 1)
            w(0x009F, 1)
            w(0x003F, 0x80)
            phase = 'fury_25m'
            phaseStart = frame
        end

    elseif phase == 'fury_25m' then
        inp = {right = ((dt % 40) < 20), left = ((dt % 40) >= 20)}
        if dt >= 8 and (dt % 2 == 0) and (counts.fury_25m or 0) < 40 then
            dumpCrop('fury_25m', 0, 8, 256, 224)
            if counts.fury_25m >= 40 then
                jumpStage(3)
                phase = 'stage_75m'
                phaseStart = frame
            end
        end

    elseif phase == 'stage_75m' then
        if dt >= 90 and (dt % 2 == 0) and (counts.stage_75m or 0) < 32 then
            dumpCrop('stage_75m', 0, 8, 256, 224)
            if counts.stage_75m >= 32 then
                jumpStage(4)
                phase = 'stage_100m'
                phaseStart = frame
            end
        end

    elseif phase == 'stage_100m' then
        if dt >= 90 and (dt % 2 == 0) and (counts.stage_100m or 0) < 32 then
            dumpCrop('stage_100m', 0, 8, 256, 224)
            if counts.stage_100m >= 32 then
                closeAll()
                emu.stop(0)
            end
        end
    end
end, emu.eventType.endFrame)
"""

SMB_LUA = LUA_COMMON + r"""
local mmc3Sel = 0
local chrBanks = {[0]=0, [1]=0, [2]=0, [3]=0}
if TAG == 'modded' then
    emu.addMemoryCallback(function(_, v) mmc3Sel = v & 0x07 end, emu.callbackType.write, 0x8000)
    emu.addMemoryCallback(function(_, v)
        if mmc3Sel <= 3 then chrBanks[mmc3Sel] = v end
    end, emu.callbackType.write, 0x8001)
end

local frame = 0
local phase = 'title'
local pStart = 0
local inp = {}
local castleActive = false
local lastCastlePos = -1
local castleStuck = 0
local sawBotOnscreen = false
local stompedBot = false
local wyrmCapStart = nil
local fairyCapStart = nil
local sawCaptive = false

local function setPhase(p)
    phase = p
    pStart = frame
    castleActive = false
end

local function placePowerupOnPlayer(kind)
    w(0x0014, 1)
    w(0x001B, 0x2E)
    w(0x0039, kind)
    w(0x0023, 0x06)
    w(0x0073, r(0x006D))
    w(0x008C, r(0x0086))
    w(0x00BB, 0x01)
    w(0x00D4, r(0x00CE))
    w(0x03D6, 0x00)
    w(0x06C3, 0x00)
end

local function spawnBot(slot, wx)
    w(0x000F + slot, 1)
    w(0x0016 + slot, 0x06)
    w(0x001E + slot, 0x00)
    w(0x006E + slot, math.floor(wx / 256))
    w(0x0087 + slot, wx % 256)
    w(0x00B6 + slot, 1)
    w(0x00CF + slot, 0xB0)
    w(0x0046 + slot, 2)
    w(0x0058 + slot, 0xF8)
    w(0x03C5 + slot, 0)
    w(0x03D1 + slot, 0)
end

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame = frame + 1
    local elapsed = frame - pStart
    inp = {}

    if phase == 'title' then
        if frame >= 60 and ((frame - 60) % 3 == 0) and (counts.title or 0) < 64 then
            dumpCrop('title', 0, 8, 256, 224)
            if counts.title >= 64 then setPhase('press_start') end
        end

    elseif phase == 'press_start' then
        if elapsed < 4 then inp = {start = true} end
        if r(0x0770) == 1 and r(0x0772) == 3 and elapsed > 20 then
            sawBotOnscreen = false
            stompedBot = false
            wyrmCapStart = nil
            setPhase('w1_wyrmling')
        elseif elapsed > 240 then
            error('Timed out starting W1-1')
        end

    elseif phase == 'w1_wyrmling' then
        local camX = r(0x071A) * 256 + r(0x071C)
        local plrX = r(0x006D) * 256 + r(0x0086)
        local botSlot, botX = nil, nil
        for s = 0, 4 do
            if r(0x000F + s) ~= 0 and r(0x0016 + s) == 0x06 then
                botSlot = s
                botX = r(0x006E + s) * 256 + r(0x0087 + s)
                break
            end
        end
        if botX and (botX - camX) <= 232 then
            sawBotOnscreen = true
            if not wyrmCapStart then wyrmCapStart = frame end
        elseif elapsed >= 130 and not wyrmCapStart then
            wyrmCapStart = frame
        end
        if not stompedBot then
            inp.right = true
            if botX then
                local dist = botX - plrX
                if dist >= 14 and dist <= 44 then inp.a = true end
                if plrX > botX + 12 or r(0x001E + botSlot) >= 0x20 then stompedBot = true end
            end
        end
        if wyrmCapStart then
            assert(r(0x000E) == 0x08, string.format('Player hurt/dead in w1_wyrmling ($0E=%02X)', r(0x000E)))
            if ((frame - wyrmCapStart) % 2 == 0) and (counts.w1_wyrmling or 0) < 60 then
                dumpCrop('w1_wyrmling', 0, 8, 256, 224)
                if counts.w1_wyrmling >= 60 then
                    assert(sawBotOnscreen, 'No Goomba/Bot appeared onscreen during w1_wyrmling')
                    setPhase('collect_mushroom')
                end
            end
        end

    elseif phase == 'collect_mushroom' then
        if elapsed == 1 then
            placePowerupOnPlayer(0)
        elseif r(0x0756) == 0 then
            w(0x0073, r(0x006D)); w(0x008C, r(0x0086)); w(0x00BB, 1); w(0x00D4, r(0x00CE))
        end
        local ready = (r(0x0756) == 1 and r(0x000E) == 0x08 and elapsed > 80)
        if TAG == 'modded' then ready = ready and (r(0x7C00) == 0 and chrBanks[0] == 2) end
        if ready then
            local plrX = r(0x006D) * 256 + r(0x0086)
            for s = 0, 4 do
                if r(0x000F + s) ~= 0 then
                    local ex = r(0x006E + s) * 256 + r(0x0087 + s)
                    if math.abs(ex - plrX) < 64 then w(0x000F + s, 0) end
                end
            end
            setPhase('super_barba')
        elseif elapsed > 240 then
            error('Timed out Mushroom')
        end

    elseif phase == 'super_barba' then
        inp = {right = (elapsed < 40), a = (elapsed >= 20 and elapsed < 36)}
        if (elapsed % 2 == 0) and (counts.super_barba or 0) < 36 then
            dumpCrop('super_barba', 0, 8, 256, 224)
            if counts.super_barba >= 36 then setPhase('collect_flower') end
        end

    elseif phase == 'collect_flower' then
        if elapsed == 1 then
            placePowerupOnPlayer(1)
        elseif r(0x0756) < 2 then
            w(0x0073, r(0x006D)); w(0x008C, r(0x0086)); w(0x00BB, 1); w(0x00D4, r(0x00CE))
        end
        local ready = (r(0x0756) == 2 and r(0x000E) == 0x08 and elapsed > 30)
        if TAG == 'modded' then ready = ready and (chrBanks[0] == 12) end
        if ready then
            if TAG == 'modded' then w(0x7C00, 0); w(0x7C05, 0) end
            setPhase('inferno_barba')
        elseif elapsed > 180 then
            error('Timed out Flower')
        end

    elseif phase == 'inferno_barba' then
        if elapsed == 1 then
            for s = 0, 4 do w(0x000F + s, 0) end
            w(0x0024, 0); w(0x0025, 0)
        end
        if elapsed <= 22 then
            inp.left = true
        elseif elapsed >= 23 and elapsed <= 25 then
            inp.right = true
        elseif elapsed == 26 then
            local pipeX = 448
            local plrX = r(0x006D) * 256 + r(0x0086)
            if plrX < pipeX then
                spawnBot(0, math.min(plrX + 68, pipeX - 36))
                spawnBot(1, math.min(plrX + 96, pipeX - 16))
            else
                spawnBot(0, plrX + 76)
                spawnBot(1, plrX + 108)
            end
        end
        if (elapsed >= 32 and elapsed <= 35) or (elapsed >= 50 and elapsed <= 53)
            or (elapsed >= 72 and elapsed <= 75) or (elapsed >= 94 and elapsed <= 97) then
            inp.b = true
        end
        if elapsed >= 28 and ((elapsed - 28) % 2 == 0) and (counts.inferno_barba or 0) < 48 then
            assert(r(0x0756) == 2, string.format('Inferno Barba lost Fire form ($0756=%d)', r(0x0756)))
            dumpCrop('inferno_barba', 0, 8, 256, 224)
            if counts.inferno_barba >= 48 then setPhase('z2_enemies') end
        end

    elseif phase == 'z2_enemies' then
        if elapsed <= 4 then
            w(0x0024, 0); w(0x0025, 0)
            local baseX = r(0x006D) * 256 + r(0x0086)
            local function setX(slot, dx)
                local wx = baseX + dx
                w(0x006E + slot, math.floor(wx / 256))
                w(0x0087 + slot, wx % 256)
            end
            w(0x000F, 1); w(0x0016, 0x00); w(0x001E, 0); setX(0, 24);  w(0x00B6, 1); w(0x00CF, 0xB0); w(0x0046, 2); w(0x03C5, 1)
            w(0x0010, 1); w(0x0017, 0x01); w(0x001F, 0); setX(1, 48);  w(0x00B7, 1); w(0x00D0, 0xB0); w(0x0047, 2); w(0x03C6, 2)
            w(0x0011, 1); w(0x0018, 0x11); w(0x0020, 0); setX(2, 74);  w(0x00B8, 1); w(0x00D1, 0x70); w(0x0048, 2); w(0x03C7, 1)
            w(0x0012, 1); w(0x0019, 0x0D); w(0x0021, 0); setX(3, 100); w(0x00B9, 1); w(0x00D2, 0xB0); w(0x005B, 0x80); w(0x03C8, 1)
            w(0x0013, 1); w(0x001A, 0x12); w(0x0022, 0); setX(4, 126); w(0x00BA, 1); w(0x00D3, 0x90); w(0x004A, 2); w(0x03C9, 2)
        elseif elapsed >= 8 and (elapsed % 2 == 0) and (counts.z2_enemies or 0) < 36 then
            dumpCrop('z2_enemies', 0, 8, 256, 224)
            if counts.z2_enemies >= 36 then
                w(0x075F, 0x00); w(0x075C, 0x03); w(0x0760, 0x00)
                w(0x0750, 0x60); w(0x074E, 0x03); w(0x07A0, 0x01)
                w(0x0772, 0x00); w(0x0770, 0x01)
                setPhase('castle_run')
            end
        end

    elseif phase == 'castle_run' then
        local inCastle = (r(0x0772) == 3 and elapsed > 20)
        if TAG == 'modded' then inCastle = inCastle and (chrBanks[1] == 18) end
        if inCastle then
            if not castleActive then
                castleActive = true
                pStart = frame
                elapsed = 0
            end
            w(0x079E, 0x10)
            if r(0x00CE) > 0xC4 then w(0x00CE, 0x70); w(0x009F, 0x00) end
            local curPos = r(0x006D) * 256 + r(0x0086)
            if curPos <= lastCastlePos + 1 then
                castleStuck = castleStuck + 1
                if castleStuck == 15 then
                    w(0x00CE, 0x88); w(0x009F, 0x00)
                elseif castleStuck == 30 then
                    w(0x00CE, 0x68); w(0x009F, 0x00)
                elseif castleStuck >= 45 then
                    local nx = r(0x0086) + 32
                    if nx >= 256 then
                        w(0x006D, r(0x006D) + 1)
                        nx = nx - 256
                    end
                    w(0x0086, nx); w(0x00CE, 0x88); w(0x009F, 0x00)
                    lastCastlePos = r(0x006D) * 256 + r(0x0086)
                    castleStuck = 0
                end
            else
                lastCastlePos = curPos; castleStuck = 0
            end
            inp = {right = true, b = true}
            if (elapsed % 28) < 12 then inp.a = true end
            local foundBowser = false
            for s = 0, 4 do
                if r(0x000F + s) ~= 0 and r(0x0016 + s) == 0x2D then foundBowser = true break end
            end
            if foundBowser and r(0x071A) >= 0x07 then
                if TAG == 'modded' then w(0x7C00, 0) end
                setPhase('castle_boss')
            elseif elapsed > 3000 then
                error('Timed out reaching Bowser/Link bridge')
            end
        elseif elapsed > 240 then
            error('Timed out entering 1-4')
        end

    elseif phase == 'castle_boss' then
        w(0x0756, 0x02); w(0x0754, 0x00); w(0x0714, 0x00)
        if r(0x00CE) > 0xC4 then w(0x00CE, 0x80); w(0x009F, 0x00) end
        if elapsed < 60 then
            w(0x079E, 0x10)
            if r(0x006D) < 8 or r(0x0086) < 0x18 then inp.right = true end
        else
            w(0x079E, 0x00)
            if r(0x0483) <= 1 then w(0x0483, 2) end
            if r(0x006D) < 8 or r(0x0086) < 0x18 then inp.right = true end
            if elapsed >= 64 then
                if (elapsed % 20) < 4 then inp.b = true end
                if (elapsed % 44) < 10 then inp.a = true end
                if ((elapsed - 64) % 2 == 0) and (counts.castle_boss or 0) < 48 then
                    dumpCrop('castle_boss', 0, 8, 256, 224)
                    if counts.castle_boss >= 48 then
                        setPhase('grab_axe')
                    end
                end
            end
        end

    elseif phase == 'grab_axe' then
        w(0x0756, 0x02); w(0x0754, 0x00)
        if r(0x0770) == 2 then
            w(0x079E, 0x00)
            fairyCapStart = nil
            sawCaptive = false
            setPhase('caged_fairy')
        else
            w(0x079E, 0x10)
            inp = {right = true}
            if r(0x00CE) > 0xB8 then w(0x00CE, 0x80); w(0x009F, 0x00) end
            if (elapsed % 28) < 10 then inp.a = true end
            if elapsed > 480 then
                error(string.format('Timed out grabbing Axe ($0770=%02X pg=%d x=%02X)', r(0x0770), r(0x006D), r(0x0086)))
            end
        end

    elseif phase == 'caged_fairy' then
        w(0x079E, 0x00)
        local camX = r(0x071A) * 256 + r(0x071C)
        for s = 0, 5 do
            if r(0x000F + s) ~= 0 and r(0x0016 + s) == 0x35 then
                local cx = r(0x006E + s) * 256 + r(0x0087 + s)
                if (cx - camX) <= 236 then
                    sawCaptive = true
                    break
                end
            end
        end
        if not fairyCapStart then
            if sawCaptive or r(0x0772) >= 2 then
                fairyCapStart = frame
            elseif elapsed > 600 then
                error(string.format('Timed out waiting for Toad/Caged Fairy ($0772=%02X)', r(0x0772)))
            end
        end
        if fairyCapStart and ((frame - fairyCapStart) % 3 == 0) and (counts.caged_fairy or 0) < 56 then
            dumpCrop('caged_fairy', 0, 8, 256, 224)
            if counts.caged_fairy >= 56 then
                assert(sawCaptive, 'Toad/Caged Fairy ($35) never appeared onscreen')
                closeAll()
                emu.stop(0)
            end
        end
    end
end, emu.eventType.endFrame)
"""

DUCK_LUA = LUA_COMMON + r"""
local VH_CURSOR_X = 0x0620
local VH_CURSOR_Y = 0x0621
local VH_CUR_R1   = 0x062C
local VH_SCENE_IDX = 0x0636

local zapperPull = false
local zapperHit = false
if TAG == 'vanilla' then
    emu.addMemoryCallback(function()
        local pc = emu.getState()['cpu.pc']
        if pc == 0xD229 and zapperHit then
            return 0x00
        end
        return (zapperPull and 0x10 or 0x00) | 0x08
    end, emu.callbackType.read, 0x4017)
end

local frame = 0
local phase = 'title'
local phaseStart = 0
local inp = {}
local shotFired = false
local fireRetryAt = 0
local biomeCapStart = nil

local function advanceRound()
    w(0x00AA, 0x0A); w(0x00AB, 0x06); w(0x00BB, 0x0A); w(0x00BC, 0x00)
    w(0x0300, 0x00); w(0x0350, 0x00); w(0x00A9, 0x01); w(0x002B, 0x00)
    w(0x0025, 0x04)
end

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame = frame + 1
    local dt = frame - phaseStart
    inp = {}
    zapperPull = false

    if phase == 'title' then
        if frame >= 36 and (frame % 2 == 0) and (counts.title or 0) < 24 then
            dumpCrop('title', 0, 8, 256, 224)
            if counts.title >= 24 then
                phase = 'start_game_a'
                phaseStart = frame
            end
        end

    elseif phase == 'start_game_a' then
        if r(0x0024) == 0x00 then
            phase = 'intro'
            phaseStart = frame
        elseif (dt % 20) < 8 then
            inp = (TAG == 'modded') and {a = true} or {start = true}
        elseif dt > 180 then
            error(string.format('Timed out starting Game A ($24=%02X $25=%02X)', r(0x0024), r(0x0025)))
        end

    elseif phase == 'intro' then
        if dt >= 15 and (dt % 5 == 0) and (counts.barba_intro or 0) < 90 then
            dumpCrop('barba_intro', 0, 8, 256, 224)
        end
        if r(0x0025) == 0x03 and r(0x0300) ~= 0 and r(0x0301) == 0x03 then
            while (counts.barba_intro or 0) < 90 do
                dumpCrop('barba_intro', 0, 8, 256, 224)
            end
            shotFired = false
            fireRetryAt = 0
            phase = 'game_a_forest'
            phaseStart = frame
        elseif dt > 800 then
            error('Timed out waiting for intro end')
        end

    elseif phase == 'game_a_forest' then
        local tx, ty = r(0x0303), r(0x0302)
        if TAG == 'modded' then
            if r(0x0301) == 0x03 and dt >= 12 then
                local cx, cy = r(VH_CURSOR_X), r(VH_CURSOR_Y)
                inp.right = (cx < tx - 3)
                inp.left  = (cx > tx + 3)
                inp.down  = (cy < ty - 3)
                inp.up    = (cy > ty + 3)
                if (not shotFired or dt >= fireRetryAt) and dt >= 36 and math.abs(cx - tx) <= 8 and math.abs(cy - ty) <= 8 and ty <= 136 then
                    inp.a = true
                    shotFired = true
                    fireRetryAt = dt + 14
                end
            end
        else
            if dt >= 42 and dt <= 44 then
                zapperPull = true
                zapperHit = true
            elseif dt > 44 and dt <= 75 then
                zapperHit = true
            else
                zapperHit = false
            end
        end
        if dt >= 6 and (dt % 3 == 0) and (counts.game_a_forest or 0) < 48 then
            dumpCrop('game_a_forest', 0, 8, 256, 224)
            if counts.game_a_forest >= 48 then
                zapperHit = false
                phase = 'wait_catch'
                phaseStart = frame
            end
        elseif dt > 400 then
            error('Timed out in game_a_forest')
        end

    elseif phase == 'wait_catch' then
        zapperHit = false
        local dp = r(0x03A5)
        if r(0x03A0) ~= 0 and (dp == 0x14 or dp == 0x15) and r(0x03A2) <= 0xB0 then
            phase = 'cap_catch'
            phaseStart = frame
        elseif dt > 240 then
            error(string.format('Timed out waiting for catch ($03A0=%02X pose=$%02X $0301=%02X)', r(0x03A0), dp, r(0x0301)))
        end

    elseif phase == 'cap_catch' then
        if (dt % 2 == 0) and (counts.barba_catch or 0) < 36 then
            dumpCrop('barba_catch', 0, 8, 256, 224)
            if counts.barba_catch >= 36 then
                phase = 'wait_second_target'
                phaseStart = frame
            end
        end

    elseif phase == 'wait_second_target' then
        if dt > 10 and r(0x0025) == 0x03 and r(0x0300) ~= 0 and r(0x0301) == 0x03 and r(0x00B9) ~= 0 then
            phase = 'miss_for_laugh'
            phaseStart = frame
        elseif dt > 300 then
            error('Timed out waiting for second target')
        end

    elseif phase == 'miss_for_laugh' then
        if r(0x00B9) ~= 0 and r(0x00BA) > 0 then
            if TAG == 'modded' then
                local tx = r(0x0303)
                w(VH_CURSOR_X, (tx < 128) and 224 or 16)
                w(VH_CURSOR_Y, 40)
                if (dt % 12) == 4 then inp = {b = true} end
            else
                zapperHit = false
                local m = dt % 16
                if m >= 2 and m <= 4 then zapperPull = true end
            end
        end
        local dp = r(0x03A5)
        if r(0x03A0) ~= 0 and (dp == 0x16 or dp == 0x17) and r(0x03A2) <= 0xB0 then
            phase = 'cap_laugh'
            phaseStart = frame
        elseif dt > 480 then
            error(string.format('Timed out waiting for laugh ($03A0=%02X pose=$%02X ammo=%d)', r(0x03A0), dp, r(0x00BA)))
        end

    elseif phase == 'cap_laugh' then
        if TAG == 'modded' and dt == 5 then
            assert(r(VH_CUR_R1) == 16, string.format('Expected Villainous Link bank 16, got %d', r(VH_CUR_R1)))
        end
        if (dt % 3 == 0) and (counts.link_laugh or 0) < 42 then
            dumpCrop('link_laugh', 0, 8, 256, 224)
            if counts.link_laugh >= 42 then
                advanceRound()
                biomeCapStart = nil
                phase = 'round2'
                phaseStart = frame
            end
        end

    elseif phase == 'round2' or phase == 'round3' or phase == 'round4' then
        local targetCount = (phase == 'round2') and 54 or ((phase == 'round3') and 108 or 162)
        if not biomeCapStart then
            if dt > 30 and r(0x0025) == 0x03 and r(0x0300) ~= 0 and r(0x0301) == 0x03 and r(0x0302) <= 136 then
                if TAG == 'modded' then
                    local expectedScene = (phase == 'round2') and 1 or ((phase == 'round3') and 2 or 0)
                    assert(r(VH_SCENE_IDX) == expectedScene,
                        string.format('%s expected scene %d, got %d', phase, expectedScene, r(VH_SCENE_IDX)))
                end
                biomeCapStart = frame
            elseif dt > 900 then
                error('Timed out in ' .. phase)
            end
        end
        if biomeCapStart then
            if ((frame - biomeCapStart) % 4 == 0) and (counts.biomes or 0) < targetCount then
                dumpCrop('biomes', 0, 8, 256, 224)
                if counts.biomes >= targetCount then
                    if phase == 'round2' then
                        advanceRound()
                        biomeCapStart = nil
                        phase = 'round3'
                        phaseStart = frame
                    elseif phase == 'round3' then
                        advanceRound()
                        biomeCapStart = nil
                        phase = 'round4'
                        phaseStart = frame
                    else
                        phase = 'game_c_reset'
                        phaseStart = frame
                        w(0x2000, 0x00)
                        w(0x2001, 0x00)
                        emu.reset()
                    end
                end
            end
        end

    elseif phase == 'game_c_reset' then
        zapperHit = false
        if TAG == 'modded' then
            if dt >= 65 and dt <= 68 then
                inp = {down = true}
            elseif dt >= 75 and dt <= 78 then
                inp = {down = true}
            elseif dt >= 84 and dt <= 88 then
                inp = {a = true}
            end
        else
            if dt >= 90 and dt <= 98 then
                inp = {select = true}
            elseif dt >= 110 and dt <= 118 then
                inp = {select = true}
            elseif dt >= 130 and r(0x0024) ~= 0x00 and (dt % 20) < 8 then
                inp = {start = true}
            end
        end
        if r(0x0024) == 0x00 and r(0x0025) == 0x0B and r(0x0300) ~= 0 and r(0x0301) == 0x03 and r(0x0302) <= 136 then
            if (dt % 2 == 0) and (counts.game_c or 0) < 36 then
                dumpCrop('game_c', 0, 8, 256, 224)
                if counts.game_c >= 36 then
                    closeAll()
                    emu.stop(0)
                end
            end
        elseif dt > 700 then
            error(string.format('Timed out entering Game C ($24=%02X $25=%02X $0300=%02X $0301=%02X $05FE=%02X)',
                r(0x0024), r(0x0025), r(0x0300), r(0x0301), r(0x05FE)))
        end
    end
end, emu.eventType.endFrame)
"""

MM2_LUA = LUA_COMMON + r"""
local frame = 0
local phase = 'title'
local phaseStart = 0
local triggerWilyReveal = false
local stageSelSettled = false
local inp = {}

emu.addMemoryCallback(function()
    if triggerWilyReveal then
        triggerWilyReveal = false
        if TAG == 'modded' then
            w(0x8000, 0x06); w(0x8001, 26)
            w(0x8000, 0x07); w(0x8001, 27)
        else
            -- Vanilla MMC1 PRG switch to Bank 13 ($0D) at $8000-$BFFF
            w(0x8000, 0x80)
            local bank = 0x0D
            for i = 0, 4 do
                w(0xE000, (bank >> i) & 1)
            end
        end
        w(0x002A, 0x08)
        emu.setState({['cpu.pc'] = 0x9678})
    end
end, emu.callbackType.exec, 0x8000, 0xFFFF)

local function nametableHas(seq)
    for addr = 0x2000, 0x23BF - #seq + 1 do
        local ok = true
        for i = 1, #seq do
            if rPpu(addr + i - 1) ~= seq[i] then ok = false break end
        end
        if ok then return true end
    end
    return false
end

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame = frame + 1
    local dt = frame - phaseStart
    inp = {}

    if phase == 'title' then
        -- Skip 200X intro at frame 45 to land on the skyscraper rooftop title screen
        if frame >= 45 and frame < 49 then inp = {start = true} end
        if frame >= 120 and (frame % 2 == 0) and (counts.title or 0) < 24 then
            dumpCrop('title', 0, 8, 256, 224)
            if counts.title >= 24 then
                phase = 'to_stagesel'
                phaseStart = frame
            end
        end

    elseif phase == 'to_stagesel' then
        if (counts.stage_select or 0) == 0 and not stageSelSettled then
            if (frame % 16) < 4 then inp = {start = true} end
        end
        local onStageSel = (TAG == 'modded')
            and (nametableHas({0x05, 0x16, 0x09, 0x0C}) and nametableHas({0x0C, 0x09, 0x0E, 0x0B}))
            or  (nametableHas({0x17, 0x09, 0x0C, 0x19})) -- "WILY" text or stage select on vanilla
        if onStageSel or (TAG == 'vanilla' and dt > 120 and r(0x002A) ~= 0) then
            if not stageSelSettled then
                stageSelSettled = true
                phaseStart = frame
            elseif dt >= 16 then
                if (dt % 2 == 0) and (counts.stage_select or 0) < 24 then
                    dumpCrop('stage_select', 0, 8, 256, 224)
                    if counts.stage_select >= 24 then
                        phase = 'select_boss'
                        phaseStart = frame
                    end
                end
            end
        elseif dt > 420 then
            error('Timed out waiting for Stage Select')
        end

    elseif phase == 'select_boss' then
        if dt >= 4 and dt < 8 then inp = {right = true}
        elseif dt >= 12 and dt < 16 then inp = {start = true}
        elseif dt >= 24 then
            phase = 'boss_intro'
            phaseStart = frame
        end

    elseif phase == 'boss_intro' then
        if dt >= 10 and (dt % 3 == 0) and (counts.boss_intro or 0) < 32 then
            dumpCrop('boss_intro', 0, 8, 256, 224)
        elseif (counts.boss_intro or 0) >= 32 and dt >= 180 then
            phase = 'gameplay'
            phaseStart = frame
        end

    elseif phase == 'gameplay' then
        if dt >= 20 and dt <= 60 then
            inp = {right = true, b = ((dt % 12) < 4)}
        elseif dt > 60 and dt <= 116 then
            inp = {right = (dt < 85), a = (dt >= 70 and dt < 84), b = ((dt % 12) < 4)}
        end
        if dt >= 24 and (dt % 2 == 0) and (counts.gameplay or 0) < 48 then
            dumpCrop('gameplay', 0, 8, 256, 224)
            if counts.gameplay >= 48 then
                triggerWilyReveal = true
                phase = 'wily_reveal'
                phaseStart = frame
            end
        end

    elseif phase == 'wily_reveal' then
        if dt >= 130 and (dt % 2 == 0) and (counts.wily_reveal or 0) < 40 then
            dumpCrop('wily_reveal', 0, 8, 256, 224)
            if counts.wily_reveal >= 40 then
                closeAll()
                emu.stop(0)
            end
        end
    end
end, emu.eventType.endFrame)
"""

WHEEL_LUA = LUA_COMMON + r"""
local frame = 0
local phase = 'title_s1'
local phaseStart = 0
local savedMenu = false
local inp = {}
local prizeIdx = 0
local prizeStep = 0

local function startPrizeSetup()
    if phase == 'prize_setup' and prizeStep == 0 then
        prizeStep = 1
        w(0x00BF, 0x02)
        w(0x00CB, prizeIdx)
        w(0x00CA, prizeIdx)
        w(0x00AD, 0x10)
        w(0x0062, 0x00)
        w(0x0505, 0x00)
        w(0x000E, 0x16)
        w(0x000F, 0xC2)
        w(0x01FF, 0xC4)
        w(0x01FE, 0xEF)
        emu.setState({['cpu.sp'] = 0xFD, ['cpu.pc'] = 0xC4B3})
    end
end

emu.addMemoryCallback(startPrizeSetup, emu.callbackType.exec, 0x927A)
emu.addMemoryCallback(startPrizeSetup, emu.callbackType.exec, 0xC216)

emu.addMemoryCallback(function()
    if phase == 'prize_setup' and prizeStep == 1 then
        prizeStep = 2
        w(0x01FF, 0xC4)
        w(0x01FE, 0xEF)
        emu.setState({['cpu.sp'] = 0xFD, ['cpu.pc'] = 0xC536})
    elseif phase == 'prize_setup' and prizeStep == 2 then
        prizeStep = 3
        w(0x01FF, 0xC4)
        w(0x01FE, 0xEF)
        emu.setState({['cpu.sp'] = 0xFD, ['cpu.x'] = 0x80, ['cpu.y'] = 0xA0, ['cpu.pc'] = 0x87C1})
    elseif phase == 'prize_setup' and prizeStep == 3 then
        prizeStep = 4
        w(0x01FF, 0xC4)
        w(0x01FE, 0xEF)
        emu.setState({['cpu.sp'] = 0xFD, ['cpu.x'] = 0x00, ['cpu.pc'] = 0x89C8})
    elseif phase == 'prize_setup' and prizeStep == 4 then
        prizeStep = 5
        w(0x01FF, 0xC4)
        w(0x01FE, 0xEF)
        emu.setState({['cpu.sp'] = 0xFD, ['cpu.pc'] = 0xE130})
    elseif phase == 'prize_setup' and prizeStep == 5 then
        prizeStep = 6
        phase = 'prize_wait'
        phaseStart = frame
        emu.setState({['cpu.pc'] = 0xC2E9})
    end
end, emu.callbackType.exec, 0xC4F0)

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame = frame + 1
    local dt = frame - phaseStart
    inp = {}

    local nmi = r(0x000E) + r(0x000F) * 256
    local s52 = r(0x0052)

    if phase == 'title_s1' then
        if frame >= 15 and (frame % 3 == 0) and (counts.title or 0) < 64 then
            dumpCrop('title', 0, 8, 256, 224)
            if counts.title >= 64 then
                phase = 'nav_to_board'
                phaseStart = frame
            end
        end

    elseif phase == 'nav_to_board' then
        if nmi ~= 0xB67C and nmi ~= 0xC216 and nmi ~= 0x917C then
            if frame >= 700 and (frame % 30) < 2 then inp = {start = true} end
        elseif nmi == 0xB67C then
            if s52 == 0x00 and not savedMenu then
                if dt >= 25 then
                    if (frame % 2 == 0) and (counts.menu or 0) < 24 then
                        dumpCrop('menu', 0, 8, 256, 224)
                        if counts.menu >= 24 then savedMenu = true end
                    end
                end
            elseif s52 == 0x00 or s52 == 0x01 or s52 == 0x02 then
                if (frame % 30) < 2 then inp = {a = true} end
            elseif s52 == 0x03 or s52 == 0x04 or s52 == 0x05 then
                local step = math.floor(frame / 16) % 4
                if (frame % 16) < 2 then
                    if step == 0 or step == 2 then inp = {a = true} else inp = {left = true} end
                end
            end
        elseif nmi == 0x917C then
            phase = 'board'
            phaseStart = frame
        end

    elseif phase == 'board' then
        if dt >= 30 and (dt % 2 == 0) and (counts.board or 0) < 32 then
            dumpCrop('board', 0, 8, 256, 224)
            if counts.board >= 32 then
                w(0x009D, 0x12)
                w(0x00AC, 0x00)
                w(0x00B3, 0xA0)
                w(0x00B4, 0x09)
                w(0x00B0, 0x05)
                phase = 'barba_walk'
                phaseStart = frame
            end
        end

    elseif phase == 'barba_walk' then
        if dt >= 2 and (dt % 2 == 0) and (counts.barba_walk or 0) < 32 then
            dumpCrop('barba_walk', 0, 8, 256, 224)
            if counts.barba_walk >= 32 then
                prizeIdx = 0
                prizeStep = 0
                phase = 'prize_setup'
                phaseStart = frame
            end
        end

    elseif phase == 'prize_wait' then
        if dt == 12 then
            dumpCrop('prize_' .. prizeIdx, 0, 8, 256, 224)
            prizeIdx = prizeIdx + 1
            if prizeIdx < 6 then
                prizeStep = 0
                phase = 'prize_setup'
                phaseStart = frame
            else
                closeAll()
                emu.stop(0)
            end
        end
    end

    if frame > 4500 then error('Wheel capture timeout') end
end, emu.eventType.endFrame)
"""

ZELDA_LUA = LUA_COMMON + r"""
local frame = 0
local phase = 'title'
local phaseStart = 0
local inp = {}

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame = frame + 1
    local dt = frame - phaseStart
    inp = {}

    if TAG == 'modded' and frame == 1 then
        for i = 0, 7 do w(0x7FF0 + i, 0x11 * (i + 1)) end
    end

    if phase == 'title' then
        if frame >= 100 and (frame % 3 == 0) and (counts.title or 0) < 32 then
            dumpCrop('title', 0, 8, 256, 224)
            if counts.title >= 32 then
                phase = 'to_fileselect'
                phaseStart = frame
            end
        end

    elseif phase == 'to_fileselect' then
        if dt >= 10 and dt < 15 then inp = {start = true} end
        if r(0x12) == 0x01 and dt > 40 then
            if (dt % 2 == 0) and (counts.file_select or 0) < 24 then
                dumpCrop('file_select', 0, 8, 256, 224)
                if counts.file_select >= 24 then
                    phase = 'register_select'
                    phaseStart = frame
                end
            end
        elseif dt > 180 then
            error('Timed out entering File Select')
        end

    elseif phase == 'register_select' then
        if dt > 180 then error('Timed out entering Register Name') end
        if r(0x12) == 0x01 then
            if r(0x16) ~= 0x03 then
                if (dt % 12) == 2 then inp = {select = true} end
            else
                if (dt % 12) == 6 then inp = {start = true} end
            end
        else
            phase = 'register_name'
            phaseStart = frame
        end

    elseif phase == 'register_name' then
        if dt > 180 then error('Timed out exiting Register Name') end
        if r(0x12) ~= 0x01 then
            if r(0x13) >= 0x04 then
                if dt < 80 then
                    if dt == 65 then inp = {a = true} end
                elseif r(0x16) ~= 0x03 then
                    if (dt % 12) == 2 then inp = {select = true} end
                else
                    if (dt % 12) == 6 then inp = {start = true} end
                end
            end
        else
            phase = 'start_game'
            phaseStart = frame
        end

    elseif phase == 'start_game' then
        if r(0x12) == 0x01 and dt >= 30 and (dt % 16) == 2 then
            inp = {start = true}
        end
        local owReady = (r(0x12) == 0x05 and dt > 60)
        if TAG == 'modded' then owReady = owReady and (r(0x7FEA) >= 2 and r(0x7FEC) == 0) end
        if owReady then
            w(0x0657, 1) -- Wooden Sword / Barba Breath
            phase = 'overworld_start'
            phaseStart = frame
        elseif dt > 420 then
            error('Timed out starting Overworld')
        end

    elseif phase == 'overworld_start' then
        if dt < 20 then
            inp = {right = true, a = ((dt % 12) < 4)}
        elseif dt < 42 then
            inp = {left = true, a = ((dt % 12) < 4)}
        elseif dt < 66 then
            inp = {right = true, a = ((dt % 12) < 4)}
        else
            inp = {right = true}
        end
        if dt >= 4 and (dt % 2 == 0) and (counts.overworld_start or 0) < 40 then
            dumpCrop('overworld_start', 0, 8, 256, 224)
            if counts.overworld_start >= 40 then
                phase = 'to_burn_bush'
                phaseStart = frame
            end
        end

    elseif phase == 'to_burn_bush' then
        if dt > 340 then
            error(string.format('Timed out walking to Screen $78 bush ($EB=%02X X=%02X Y=%02X)', r(0xEB), r(0x70), r(0x84)))
        elseif r(0xEB) == 0x77 then
            inp = {right = true}
        elseif r(0xEB) == 0x78 then
            local lx, ly = r(0x70), r(0x84)
            if lx < 0x3E then inp = {right = true}
            elseif lx > 0x42 then inp = {left = true}
            elseif ly > 0x94 then inp = {up = true}
            elseif ly < 0x88 then inp = {down = true}
            elseif r(0x98) ~= 0x04 then inp = {down = true}
            else
                phase = 'burn_bush'
                phaseStart = frame
            end
        end

    elseif phase == 'burn_bush' then
        if dt >= 6 and dt < 12 then inp = {a = true}
        elseif dt >= 48 and dt < 54 then inp = {a = true} end
        if (dt % 2 == 0) and (counts.burn_bush or 0) < 48 then
            dumpCrop('burn_bush', 0, 8, 256, 224)
            if counts.burn_bush >= 48 then
                closeAll()
                emu.stop(0)
            end
        end
    end
end, emu.eventType.endFrame)
"""

MTPO_LUA = LUA_COMMON + r"""
local frame = 0
local phase = 'to_title'
local phaseStart = 0
local inp = {}
local titleFrames = 0
local tapeFrames = 0
local fightFrames = 0
local fightStarted = false

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

local function hasNonBlankScreen()
    local px = emu.getScreenBuffer()
    local first = px[256 * 80 + 128]
    for y = 40, 180, 16 do
        if px[256 * y + 80] ~= first or px[256 * y + 176] ~= first then
            return true
        end
    end
    return false
end

emu.addEventCallback(function()
    frame = frame + 1
    local dt = frame - phaseStart
    inp = {}

    if TAG == 'modded' and frame == 1 then
        for i = 0, 7 do w(0x7FF0 + i, 0x37 + i * 17) end
    end

    if phase == 'to_title' then
        -- Wait ~250 frames for intro screen, then press Start to reach Title2
        if frame >= 250 then
            if (dt % 45) < 4 and titleFrames == 0 then inp.start = true end
            local ppu11 = r(0x11)
            local onTitle = false
            if TAG == 'modded' then
                onTitle = (r(0x7F81) == 1 and (ppu11 & 0x18) == 0x18)
            else
                onTitle = (frame >= 310 and (ppu11 & 0x18) == 0x18 and hasNonBlankScreen())
            end
            if onTitle then
                titleFrames = titleFrames + 1
                if titleFrames >= 25 and (titleFrames % 2 == 0) and (counts.title or 0) < 24 then
                    dumpCrop('title', 0, 8, 256, 224)
                    if counts.title >= 24 then
                        phase = 'to_tape'
                        phaseStart = frame
                    end
                end
            elseif frame > 700 then
                error('Timed out waiting for Title2')
            end
        end

    elseif phase == 'to_tape' then
        if tapeFrames == 0 and (dt % 40) < 4 then inp.start = true end
        local ppu11 = r(0x11)
        local onTape = false
        if TAG == 'modded' then
            onTape = (r(0x7F81) == 3 and (ppu11 & 0x18) == 0x18)
        else
            onTape = (dt >= 95 and (ppu11 & 0x18) == 0x18 and r(0x1D) ~= 0 and hasNonBlankScreen())
        end
        if onTape then
            tapeFrames = tapeFrames + 1
            if tapeFrames >= 25 and (tapeFrames % 2 == 0) and (counts.tape or 0) < 24 then
                dumpCrop('tape', 0, 8, 256, 224)
                if counts.tape >= 24 then
                    phase = 'to_fight'
                    phaseStart = frame
                end
            end
        elseif dt > 600 then
            error('Timed out waiting for Tale of the Tape')
        end

    elseif phase == 'to_fight' then
        if (dt % 40) < 4 then inp.start = true end
        local ppu11 = r(0x11)
        if r(0x1D) == 0 and (ppu11 & 0x18) == 0x18 and dt > 40 then
            phase = 'fight'
            phaseStart = frame
        elseif dt > 900 then
            error('Timed out waiting for Fight mode')
        end

    elseif phase == 'fight' then
        local m51 = r(0x51)
        if not fightStarted and (m51 == 0x00 or (TAG == 'modded' and r(0x048D) == 0x16)) then
            fightStarted = true
        end
        if fightStarted then
            fightFrames = fightFrames + 1
            if fightFrames >= 25 and fightFrames <= 45 then
                inp = {a = true, up = true}
            elseif fightFrames > 50 and fightFrames <= 66 then
                inp = {left = true}
            elseif fightFrames > 70 and fightFrames <= 90 then
                inp = {b = true}
            end
            if fightFrames >= 12 and (fightFrames % 2 == 0) and (counts.fight or 0) < 48 then
                dumpCrop('fight', 0, 8, 256, 224)
                if counts.fight >= 48 then
                    closeAll()
                    emu.stop(0)
                end
            end
        elseif dt > 1300 then
            error('Timed out waiting for active fight ($51=0)')
        end
    end
end, emu.eventType.endFrame)
"""

# ---------------------------------------------------------------------------
# Subgame showcase catalog metadata & scene specs
# ---------------------------------------------------------------------------

SUBGAMES: list[dict[str, Any]] = [
    {
        "id": "waldo",
        "tab_label": "Where's Waldo?",
        "name": "Where's Barba?",
        "original": "Where's Waldo? (THQ / Bethesda)",
        "summary": "Replaces Waldo with Barba across the postcard title, Skill Select Wyrmling cursor, Lava ticket, Overworld Map, fleeing/shouting crowds, The Subway (Barba, Link & Flame), and the Rocket Slots Moon ending.",
        "lua": WALDO_LUA,
        "scenes": [
            ("title", "Postcard Title Screen", "Replaces the Where's Waldo? postcard stamp and title banner with There's Barba!.", 256, 224, 48, 10, "Where's Waldo? Title", "There's Barba! Postcard"),
            ("skill_select", "Skill Select (Wyrmling Cursor)", "Swaps the magnifying cursor on Skill Select with an animated 16x16 Wyrmling.", 256, 224, 32, 12, "Vanilla Skill Select", "Animated Wyrmling Cursor"),
            ("moon_ticket", "One Ticket to the Lava", "Peeking Barba head above the Moon/Lava rocket ticket before Stage 1.", 256, 224, 24, 12, "Vanilla Moon Ticket", "One Ticket to the Lava"),
            ("overworld_map", "Overworld Map Walk", "48x48 full-body Barba walking across the overworld map between stages.", 256, 224, 40, 15, "Vanilla Waldo Map Walk", "Full-Body Walking Barba"),
            ("train_station", "Fleeing & Shouting Crowds", "Crowd bystanders flee from hidden 16x16 Barba with panic shouts (BARBA!, RUN!, HELP!).", 256, 224, 48, 15, "Static Vanilla Crowd", "Panic Shouts & Fleeing Crowd"),
            ("subway", "The Subway", "Replaces Waldo, Odlaw, and the Glasses in the Subway maze with Barba, Link, and a Barba Flame.", 256, 224, 24, 12, "Waldo, Odlaw & Glasses", "Barba, Link & Barba Flame"),
            ("slots", "Rocket Slots Jackpot", "Spinning Rocket Slots reels locking onto three Barba portraits for the jackpot.", 256, 224, 96, 15, "Vanilla Waldo Rocket Slots", "3-Barba Rocket Slots Jackpot"),
            ("moon_ending", "Moon Ending Celebration", "Space-helmeted Barba leaps from the rocket onto the Moon, lands, and unleashes a screen-shaking roar.", 256, 224, 100, 12, "Vanilla Waldo Moon Ending", "Barba Moon Jump, Landing & Roar"),
        ],
    },
    {
        "id": "feud",
        "tab_label": "Family Feud",
        "name": "Barba's Beef",
        "original": "Family Feud (GameTek)",
        "summary": "Barba variants square off against Zelda II bosses, enemies, and townsfolk across randomized stage lineups, Face-Offs, ordinal FIRST-FIFTH FEUD floor banners, and Z2 trivia.",
        "lua": FEUD_LUA,
        "scenes": [
            ("title", "Title Screen", "Barba's Beef marquee replacing the vanilla Family Feud title screen.", 256, 224, 24, 12, "Vanilla Family Feud", "Barba's Beef Marquee"),
            ("overview", "Stage Overview & Ordinal Banner", "All 10 randomized Barba & Zelda II contestants on stage with the FIRST FEUD stage-floor banner.", 256, 224, 32, 15, "Vanilla Family Overview", "Barba vs Z2 + FIRST FEUD"),
            ("faceoff", "Face-Off Podium", "Head-to-head buzzer podium pitting randomized Barba vs Zelda II contestants on Z2 survey questions.", 256, 224, 32, 15, "Vanilla Face-Off", "Barba vs Z2 Face-Off"),
            ("stage_barba", "Barba Family Podium", "Barba team podium with animated idle roars and head-wiggles during main rounds.", 256, 224, 32, 15, "Vanilla Left Family", "Barba Family Podium"),
            ("stage_z2", "Zelda II Opposing Podium", "Opposing Zelda II cast podium featuring full-height bosses, knights, and villagers.", 256, 224, 32, 15, "Vanilla Right Family", "Zelda II Opposing Cast"),
            ("fast_money", "Fast Money Final Round", "Blue-background Fast Money final round with Zelda II survey questions and Barba's portrait on the clock.", 256, 224, 32, 10, "Vanilla Fast Money", "Z2 Fast Money & Barba"),
            ("lose_excuse", "Lose Excuse Screen", "End-of-game lose screen replacing vanilla's family obligations / tax considerations excuses with custom Zelda II reasons and opposing family names.", 256, 224, 16, 10, "Vanilla Lose Excuse", "Zelda II Lose Excuse"),
        ],
    },
    {
        "id": "dk",
        "tab_label": "Donkey Kong",
        "name": "Barba Kong",
        "original": "Donkey Kong (Nintendo)",
        "summary": "Lil' Barba climbs construction girders to rescue Princess Zelda from Big Bad Link, wielding Flame Fury dragon breath against Z2 Bits, Bubbles, Bombs, and Shields.",
        "lua": DK_LUA,
        "scenes": [
            ("title", "Title Screen", "Barba Kong title screen with animated fireball selector cursor.", 256, 224, 24, 12, "Vanilla Donkey Kong", "Barba Kong + Fireball Cursor"),
            ("stage_25m", "25m Girders (Big Bad Link & Zelda)", "Lil' Barba at the base of 25m while Big Bad Link hurls hazards and Princess Zelda waits above.", 256, 224, 40, 15, "Vanilla 25m (Mario & DK)", "Lil' Barba, Big Bad Link & Zelda"),
            ("fury_25m", "Flame Fury Breath", "Hammer pickup transformed into alternating straight-forward and cone firebreath.", 256, 224, 40, 15, "Vanilla Hammer Swing", "Flame Fury Firebreath"),
            ("stage_75m", "75m Elevators & Z2 Bombs", "Elevator stage upgraded with Zelda II Shields and falling Bombs.", 256, 224, 32, 15, "Vanilla 75m Springs", "Z2 Shields & Bombs"),
            ("stage_100m", "100m Rivets & Z2 Bubbles", "Final rivets stage with Big Bad Link and hovering Zelda II Bubbles.", 256, 224, 32, 15, "Vanilla 100m Fireballs", "Big Bad Link & Z2 Bubbles"),
        ],
    },
    {
        "id": "duck",
        "tab_label": "Duck Hunt",
        "name": "Villager Hunt (Barba's Hunt)",
        "original": "Duck Hunt (Nintendo)",
        "summary": "Zelda II forest, grass, and desert biomes replace the meadow while flying villagers, Octoroks, and Moas take flight—plus smooth D-pad fireball bursts, Barba P-Bag catches, and Villainous Link laughs.",
        "lua": DUCK_LUA,
        "scenes": [
            ("title", "Villager Hunt Title Screen", "Custom Villager Hunt title banner and game selection menu.", 256, 224, 24, 12, "Vanilla Duck Hunt", "Villager Hunt Banner"),
            ("barba_intro", "Barba Forest Intro & Downstab", "Full-body Barba trots across the Z2 forest clearing, sniffs, roars, and leaps down behind the bushes with the Z2 downstab pose.", 256, 224, 90, 12, "Vanilla Dog Sniff & Jump", "Barba Intro & Z2 Downstab"),
            ("game_a_forest", "Forest Clearing & Fireball Burst", "A flying Great Palace Fokka soars past Z2 forest trunks while the D-pad smoothly tracks it and fires a fireball burst, compared against a vanilla Zapper shot.", 256, 224, 48, 20, "Vanilla Meadow & Zapper Shot", "Smooth Aim & Fireball Burst (Fokka)"),
            ("barba_catch", "Hit Catch: Barba & P-Bag", "Scoring a hit brings out Barba popping up behind the bushes holding a Zelda II P-Bag in place of the vanilla dog holding a duck.", 256, 224, 36, 15, "Vanilla Dog Holding Duck", "Barba Holding Z2 P-Bag"),
            ("link_laugh", "Miss Laugh: Villainous Link", "Missing all shots lets the target escape and brings out Villainous Link popping up behind the bushes to laugh.", 256, 224, 42, 18, "Vanilla Dog Laugh", "Villainous Link Laugh"),
            ("biomes", "Biome Cycle: Grass, Desert & Forest", "Round progression cycles through Zelda II Overworld Grass (Round 2), Desert (Round 3), and Forest (Round 4) scenery.", 256, 224, 162, 15, "Repeated Vanilla Meadow (R2-R4)", "Z2 Grass, Desert & Forest Cycle"),
            ("game_c", "Game C: Octoroks, Moas & Plates", "Clay shooting replaced with flying Zelda II Octoroks, Moas, and Palace Plates.", 256, 224, 36, 15, "Vanilla Clay Pigeons", "Octoroks, Moas & Palace Plates"),
        ],
    },
    {
        "id": "wheel",
        "tab_label": "Wheel of Fortune",
        "name": "Wheel of Barba",
        "original": "Wheel of Fortune (GameTek)",
        "summary": "Updates Screen 1 credits to BARBA EDITION and HYRULE PALACE STUDIOS, plus the setup board and main puzzle stage starring full-body Barba against Dark Link across Zelda II trivia puzzles.",
        "lua": WHEEL_LUA,
        "scenes": [
            ("title", "Title Credits Screen", "Updates the Screen 1 logo to WHEEL OF BARBA and rewrites the credits to HYRULE PALACE STUDIOS, A UNIT OF PALACE VI DRAGON, and 1990 BARBA VS DARK LINK.", 256, 224, 64, 15, "Vanilla Wheel of Fortune Credits", "WHEEL OF BARBA Credits"),
            ("menu", "Game Setup Menu", "Setup board themed to WHEEL OF BARBA EDITION.", 256, 224, 24, 12, "Vanilla Setup Menu", "WHEEL OF BARBA EDITION"),
            ("board", "Main Puzzle Board (Barba & Dark Link)", "Main board with full-body Barba host, DARK LINK contestant, and custom Zelda II puzzles.", 256, 224, 32, 15, "Vanilla Board & Vanna", "Barba, Dark Link & Z2 Puzzle"),
            ("barba_walk", "Barba Unveiling Letters", "Full-body Barba striding briskly across the puzzle stage to turn letters.", 256, 224, 32, 15, "Vanilla Hostess Walk", "Full-Body Barba Walk"),
            ("prize_0", "Bonus Prize 1: Palace 6 Crystal", "Replaces Emerald Necklace with a faceted, glowing Palace 6 Crystal on a Palace VI pedestal.", 256, 224, 1, 1, "Emerald Necklace", "PALACE 6 CRYSTAL"),
            ("prize_1", "Bonus Prize 2: East Hyrule Cruise", "Replaces Caribbean Cruise with the Crossing Raft sailing across East Hyrule waves.", 256, 224, 1, 1, "Caribbean Cruise", "EAST HYRULE CRUISE"),
            ("prize_2", "Bonus Prize 3: Hyrule Item Hoard", "Replaces Beach House with a two-tier showcase of real Zelda II items (P-Bag, Candle, Hammer, Boots, Flute, Cross, Key, Elixir).", 256, 224, 1, 1, "Beach House", "HYRULE ITEM HOARD"),
            ("prize_3", "Bonus Prize 4: April in Rauru", "Replaces April in Paris by swapping the Eiffel Tower and Paris script for a Rauru Town house and Paris-matched Rauru script.", 256, 224, 1, 1, "April in Paris", "APRIL IN RAURU"),
            ("prize_4", "Bonus Prize 5: This Cool Boulder", "Replaces Concorde to London with a 2x Zelda II overworld boulder on a velvet showcase pedestal.", 256, 224, 1, 1, "Concorde to London", "THIS COOL BOULDER"),
            ("prize_5", "Bonus Prize 6: Piece of Palace 4", "Replaces Bentley with a broken-off chunk of Maze Island Palace 4 stone and pillar.", 256, 224, 1, 1, "Bentley", "PIECE OF PALACE 4"),
        ],
    },
    {
        "id": "f13",
        "tab_label": "Friday the 13th",
        "name": "Friday the 13th: Camp Barba",
        "original": "Friday the 13th (LJN / Atlus)",
        "visibility": "local",
        "archived": True,
        "summary": "Archived post-2.0. Starring full-body 24x48 Barba on Crystal Lake paths with 5-shot Zelda II fireball volleys, BARBA Camp Map & HUD portraits, and King's Quest-style Forest Coven endings.",
        "lua": F13_LUA,
        "scenes": [
            ("camp_map", "Crystal Lake Camp Map", "Camp map counselor roster featuring BARBA and a custom dragon portrait.", 256, 224, 24, 12, "Vanilla Camp Map", "BARBA Roster & Portrait"),
            ("exterior_volley", "Camp Path & 5-Shot Fireball Volley", "24x48 Barba with trailing tail crouching and breathing 5-shot Z2 fireball volleys on the camp road.", 256, 224, 48, 15, "Vanilla Counselor & Rocks", "24x48 Barba + Fireball Volley"),
            ("cabin_inside", "Cabin Interior & HUD Portrait", "First-person Crystal Lake cabin exploration with Barba's updated HUD portrait and sprite.", 256, 224, 24, 12, "Vanilla Cabin HUD", "Barba Cabin HUD Portrait"),
            ("forest_coven", "Forest Coven Ending (Debbie)", "Walking deep into the north forest triggers a custom multi-Barba coven cutscene and cliff levitation.", 256, 224, 48, 15, "Vanilla Dark Forest Walk", "Forest Coven & Cliff Levitation", {"visibility": "local"}),
        ],
    },
    {
        "id": "smb",
        "tab_label": "Super Mario Bros.",
        "name": "Super Barba Bros.",
        "original": "Super Mario Bros. (Nintendo)",
        "visibility": "local",
        "archived": True,
        "summary": "Archived post-2.0. Replaces Mario with Wyrmling, 16x32 Super Barba, and flame-crowned Inferno Barba across MMC3 animated enemies (Bots, Stalfos, Ironknuckles, Geldarms) and Castle 1-4 Villainous Link.",
        "lua": SMB_LUA,
        "scenes": [
            ("title", "Title Screen", "Replaces SUPER MARIO BROS. on the beveled title sign with SUPER BARBA BROS., updates HUD to BARBA, and swaps Mario on the demo stage for the tiny Wyrmling.", 256, 224, 64, 12, "MARIO Title Screen", "SUPER BARBA BROS. & Wyrmling"),
            ("w1_wyrmling", "World 1-1: Wyrmling vs Bot", "Small Wyrmling Barba confronting a Zelda II Bot slime in World 1-1.", 256, 224, 60, 15, "Small Mario & Goomba", "Wyrmling & Z2 Bot"),
            ("super_barba", "Super Barba (Full Body)", "Mushroom power-up transforms Wyrmling into full-body 16x32 Super Barba.", 256, 224, 36, 15, "Super Mario", "16x32 Super Barba"),
            ("inferno_barba", "Inferno Barba (Fireball Breath)", "Fire Flower crowns Barba in flame, breathing rolling dragon fireballs to roast approaching Z2 Bots.", 256, 224, 48, 15, "Fire Mario & Fireballs", "Inferno Barba Fireball Breath"),
            ("z2_enemies", "Zelda II Enemy Roster", "Stalfos, Red Ironknuckle, Wizzrobe, Geldarm, and Bubble replacing classic Mushroom Kingdom foes.", 256, 224, 36, 15, "Vanilla Enemy Roster", "Z2 Stalfos, Ironknuckle & More"),
            ("castle_boss", "Castle 1-4: Villainous Link", "Bridge showdown against Villainous Link firing horizontal sword beams and throwing lit bombs beneath the shimmering Triforce Axe.", 256, 224, 48, 15, "Vanilla Bowser", "Villainous Link (Beams & Bombs)"),
            ("caged_fairy", "Castle 1-4 Rescue: Caged Fairy", "Touching the Triforce Axe collapses the bridge and frees the flapping Caged Fairy in place of Mushroom Retainer Toad.", 256, 224, 56, 12, "Vanilla Toad Rescue", "Caged Fairy Rescue"),
        ],
    },
    {
        "id": "mm2",
        "tab_label": "Mega Man 2",
        "name": "Barba Man 2",
        "original": "Mega Man 2 (Capcom)",
        "visibility": "local",
        "archived": True,
        "summary": "Archived post-2.0. Upgrades MEGA MAN II to unclipped MEGA BARBA II with rooftop Barba, Villainous Link on Stage Select and Wily's saucer, and Fireball Buster gameplay.",
        "lua": MM2_LUA,
        "scenes": [
            ("title", "MEGA BARBA II Title Screen", "Left-facing Zelda II overworld Barba standing atop the skyscraper beneath the unclipped MEGA BARBA II logo.", 256, 224, 24, 12, "Vanilla MEGA MAN II", "Rooftop Barba + MEGA BARBA II"),
            ("stage_select", "Stage Select (EVIL LINK)", "Center Stage Select portrait and nameplate swapped from Dr. Wily to Villainous Link.", 256, 224, 24, 12, "Vanilla Stage Select", "Villainous Link Portrait"),
            ("boss_intro", "Robot Master Intro", "Bubble Man stage intro screen synced with Barba's sampled roar.", 256, 224, 32, 15, "Vanilla Boss Intro", "Barba Man 2 Boss Intro"),
            ("gameplay", "Bubble Man Stage (Fireball Buster)", "Crimson Barba running, jumping, and firing flaming Zelda II fireballs in place of Mega Buster lemons.", 256, 224, 48, 15, "Mega Man & Lemons", "Barba & Fireball Buster"),
            ("wily_reveal", "Evil Link Saucer Reveal", "Wily Castle intro cutscene piloted by Villainous Link.", 256, 224, 40, 15, "Vanilla Dr. Wily Saucer", "Villainous Link Pilot"),
        ],
    },
    {
        "id": "zelda",
        "tab_label": "The Legend of Zelda",
        "name": "The Legend of Barba",
        "original": "The Legend of Zelda (Nintendo)",
        "visibility": "local",
        "archived": True,
        "summary": "Archived post-2.0. Replaces Link with a 16x16 crimson fire-breathing Barba across File Select, Hyrule Overworld, and innate A-button firebreath that ignites secret bushes without the Candle.",
        "lua": ZELDA_LUA,
        "scenes": [
            ("file_select", "File Select", "Save-slot screen updated with Barba's dragon hero icon.", 256, 224, 24, 12, "Vanilla File Select", "Barba Hero Icon"),
            ("overworld_start", "Hyrule Overworld Start", "16x16 crimson dragon Barba walking and breathing fireballs on Screen $77.", 256, 224, 40, 15, "Vanilla Link & Sword", "16x16 Fire-Breathing Barba"),
            ("burn_bush", "Screen $78 Burnable Bush Secret", "Barba's innate A-button firebreath ignites the secret bush on Screen $78 without needing the Candle.", 256, 224, 48, 15, "Vanilla Sword (No Burn)", "Firebreath Ignites Secret Bush"),
        ],
    },
    {
        "id": "mtpo",
        "tab_label": "Mike Tyson's Punch-Out!!",
        "name": "Barba's Punch-Out!!",
        "original": "Mike Tyson's Punch-Out!! (Nintendo)",
        "visibility": "local",
        "archived": True,
        "summary": "Archived post-2.0. BARBA'S PUNCH-OUT!! marquee, custom Tale of the Tape matchup, and crimson back-view Barba bobbing and punching inside the boxing ring.",
        "lua": MTPO_LUA,
        "scenes": [
            ("title", "Title Screen (BARBA'S PUNCH-OUT!!)", "Replaces MIKE TYSON'S header with BARBA'S above the Punch-Out!! marquee, plus Z2 Game Over Link silhouette portrait and green LINK on Title2.", 256, 224, 24, 12, "Mike Tyson's Punch-Out!!", "BARBA'S PUNCH-OUT!!"),
            ("tape", "Tale of the Tape", "Pre-fight Tale of the Tape matchup card customized for Barba's Punch-Out!!.", 256, 224, 24, 12, "Vanilla Tale of the Tape", "Barba's Punch-Out!! Matchup"),
            ("fight", "Round 1 Ring Fight (Barba)", "Crimson back-view Barba bobbing, dodging, and throwing punches in the ring against Glass Joe.", 256, 224, 48, 15, "Vanilla Little Mac", "Crimson Back-View Barba"),
        ],
    },
]

SUBGAMES_BY_ID: dict[str, dict[str, Any]] = {g["id"]: g for g in SUBGAMES}


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def write_grid_png(raw_path: Path, out_png: Path, w: int, h: int, n_frames: int, cols: int = 8) -> dict[str, Any]:
    """Pack raw RGBA frames into a compact 2D grid PNG (indexed PLTE when <=256 colors)."""
    data = raw_path.read_bytes()
    frame_bytes = w * h * 4
    if len(data) < frame_bytes * n_frames:
        raise ValueError(f"{raw_path} too short: {len(data)} < {frame_bytes * n_frames}")

    grid_cols = min(n_frames, cols)
    grid_rows = math.ceil(n_frames / grid_cols)
    sheet_w = grid_cols * w
    sheet_h = grid_rows * h

    # Collect unique RGB colors across captured frames (NES output has <= 64 colors).
    palette_map: dict[bytes, int] = {}
    palette_list: list[bytes] = []
    use_indexed = True

    # Build grid pixel buffer (row-major RGB or RGBA)
    stride_src = w * 4
    rgb_rows: list[bytes] = []
    for gr in range(grid_rows):
        for y in range(h):
            row_chunks: list[bytes] = []
            for gc in range(grid_cols):
                f_idx = gr * grid_cols + gc
                if f_idx < n_frames:
                    off = f_idx * frame_bytes + y * stride_src
                    row_chunks.append(data[off : off + stride_src])
                else:
                    row_chunks.append(b"\x0b\x0d\x13\xff" * w)
            rgba_row = b"".join(row_chunks)
            rgb_rows.append(rgba_row)
            if use_indexed:
                for px_off in range(0, len(rgba_row), 4):
                    rgb = rgba_row[px_off : px_off + 3]
                    if rgb not in palette_map:
                        if len(palette_list) >= 256:
                            use_indexed = False
                            break
                        palette_map[rgb] = len(palette_list)
                        palette_list.append(rgb)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    if use_indexed:
        idx_rows = bytearray()
        for rgba_row in rgb_rows:
            idx_rows.append(0)
            for px_off in range(0, len(rgba_row), 4):
                idx_rows.append(palette_map[rgba_row[px_off : px_off + 3]])
        plte = b"".join(palette_list)
        png_bytes = (
            b"\x89PNG\r\n\x1a\n"
            + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", sheet_w, sheet_h, 8, 3, 0, 0, 0))
            + _png_chunk(b"PLTE", plte)
            + _png_chunk(b"IDAT", zlib.compress(bytes(idx_rows), 9))
            + _png_chunk(b"IEND", b"")
        )
    else:
        rgba_out = bytearray()
        for rgba_row in rgb_rows:
            rgba_out.append(0)
            rgba_out.extend(rgba_row)
        png_bytes = (
            b"\x89PNG\r\n\x1a\n"
            + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", sheet_w, sheet_h, 8, 6, 0, 0, 0))
            + _png_chunk(b"IDAT", zlib.compress(bytes(rgba_out), 9))
            + _png_chunk(b"IEND", b"")
        )

    out_png.write_bytes(png_bytes)
    return {
        "sheet_w": sheet_w,
        "sheet_h": sheet_h,
        "colors": len(palette_list),
        "indexed": use_indexed,
        "bytes": len(png_bytes),
    }


def _check_non_blank_and_diff(
    vanilla_raw: Path,
    modded_raw: Path,
    w: int,
    h: int,
    n_frames: int,
) -> tuple[int, int, float]:
    """Return (vanilla_unique_colors, modded_unique_colors, pixel_diff_pct)."""
    frame_bytes = w * h * 4
    v_data = vanilla_raw.read_bytes()
    m_data = modded_raw.read_bytes()
    sample_indices = sorted({0, n_frames // 2, max(0, n_frames - 1)})
    v_cols: set[bytes] = set()
    m_cols: set[bytes] = set()
    total_px = 0
    diff_px = 0
    for fi in sample_indices:
        off = fi * frame_bytes
        for p in range(0, frame_bytes, 16):  # sample every 4th pixel for speed
            vc = v_data[off + p : off + p + 3]
            mc = m_data[off + p : off + p + 3]
            v_cols.add(vc)
            m_cols.add(mc)
            total_px += 1
            if vc != mc:
                diff_px += 1
    return len(v_cols), len(m_cols), (100.0 * diff_px / max(1, total_px))


def resolve_modded_rom(gid: str) -> Path:
    if gid == "f13":
        candidates = [
            p for p in (ROOT / "play" / "nes" / "f13.nes", ROOT / "build" / "f13_barba.nes", subgame_pack.find_play_rom("f13"))
            if p.is_file()
        ]
        if candidates:
            return max(candidates, key=lambda p: p.stat().st_mtime)
    if gid == "wheel":
        built = ROOT / "build" / "subgames" / "wheel.nes"
        if built.is_file():
            return built
    rom = subgame_pack.find_play_rom(gid)
    if rom.is_file():
        return rom
    fallback = ROOT / "build" / "subgames" / f"{gid}.nes"
    return fallback if fallback.is_file() else rom


def _unpack_scene(scene: tuple[Any, ...] | dict[str, Any]) -> dict[str, Any]:
    """Normalize a 9-tuple, 10-tuple (with meta dict), or dict scene spec."""
    if isinstance(scene, dict):
        return {
            "id": scene["id"],
            "title": scene["title"],
            "description": scene["description"],
            "w": scene["w"],
            "h": scene["h"],
            "frames": scene["frames"],
            "fps": scene["fps"],
            "vanilla_label": scene["vanilla_label"],
            "modded_label": scene["modded_label"],
            "visibility": scene.get("visibility", "public"),
            "target": scene.get("target"),
        }
    if len(scene) == 9:
        sc_id, title, desc, w, h, n_frames, fps, v_lbl, m_lbl = scene
        meta: dict[str, Any] = {}
    elif len(scene) == 10:
        sc_id, title, desc, w, h, n_frames, fps, v_lbl, m_lbl, meta = scene
    else:
        raise ValueError(f"Unexpected scene tuple length {len(scene)}: {scene!r}")
    return {
        "id": sc_id,
        "title": title,
        "description": desc,
        "w": w,
        "h": h,
        "frames": n_frames,
        "fps": fps,
        "vanilla_label": v_lbl,
        "modded_label": m_lbl,
        "visibility": meta.get("visibility", "public"),
        "target": meta.get("target"),
    }


def run_game_capture(game: dict[str, Any], tag: str) -> None:
    gid = game["id"]
    if tag == "vanilla":
        rom = ROOT / "roms" / f"{gid}.nes"
    else:
        rom = resolve_modded_rom(gid)
    if not rom.is_file():
        raise FileNotFoundError(f"Missing {tag} ROM for {gid}: {rom}")

    game_cap_dir = CAP_DIR / gid
    game_cap_dir.mkdir(parents=True, exist_ok=True)
    lua_path = ROOT / "build" / f"sub_cap_{gid}_{tag}.lua"
    header = (
        f"TAG = {json.dumps(tag)}\n"
        f"CAP_DIR = {json.dumps(game_cap_dir.as_posix())}\n"
    )
    lua_path.write_text(header + game["lua"], encoding="utf-8")
    print(f"[{gid}:{tag}] Running Mesen on {rom.relative_to(ROOT)} ...")
    rc = emulator_test.run(lua_path, rom, timeout=180)
    if rc != 0:
        raise SystemExit(f"Capture failed for {gid}:{tag} ({rom}) with exit code {rc}")

    for raw_sc in game["scenes"]:
        sc = _unpack_scene(raw_sc)
        sc_id, w, h, n_frames = sc["id"], sc["w"], sc["h"], sc["frames"]
        raw_path = game_cap_dir / f"{tag}_{sc_id}.rgba"
        out_png = OUT_DIR / f"{gid}_{sc_id}_{tag}.png"
        info = write_grid_png(raw_path, out_png, w, h, n_frames)
        print(
            f"  -> {out_png.relative_to(ROOT)} "
            f"({info['sheet_w']}x{info['sheet_h']}, {n_frames}f, "
            f"{'PLTE' if info['indexed'] else 'RGBA'} {info['colors']}c, "
            f"{info['bytes'] // 1024} KiB)"
        )


def validate_game_pairs(game: dict[str, Any]) -> None:
    gid = game["id"]
    game_cap_dir = CAP_DIR / gid
    for raw_sc in game["scenes"]:
        sc = _unpack_scene(raw_sc)
        sc_id, w, h, n_frames = sc["id"], sc["w"], sc["h"], sc["frames"]
        v_raw = game_cap_dir / f"vanilla_{sc_id}.rgba"
        m_raw = game_cap_dir / f"modded_{sc_id}.rgba"
        if v_raw.is_file() and m_raw.is_file():
            vc, mc, diff = _check_non_blank_and_diff(v_raw, m_raw, w, h, n_frames)
            if vc < 3 or mc < 3:
                raise ValueError(f"Blank/flat capture for {gid}/{sc_id}: vanilla={vc}c, modded={mc}c")
            tag = "WARNING: 0% diff!" if diff == 0.0 else f"diff={diff:.1f}%"
            print(f"  [validate {gid}/{sc_id}] vanilla={vc}c, modded={mc}c, {tag}")


def build_subgames_payload(
    include_local: bool = True, games: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    games_payload: list[dict[str, Any]] = []
    source_games = SUBGAMES if games is None else games
    for g in source_games:
        gid = g["id"]
        g_vis = g.get("visibility", "public")
        if not include_local and g_vis == "local":
            continue

        scenes_payload: list[dict[str, Any]] = []
        for raw_sc in g["scenes"]:
            sc = _unpack_scene(raw_sc)
            sc_vis = sc["visibility"]
            if not include_local and sc_vis == "local":
                continue
            sc_id = sc["id"]
            sc_entry: dict[str, Any] = {
                "id": sc_id,
                "title": sc["title"],
                "description": sc["description"],
                "w": sc["w"],
                "h": sc["h"],
                "frames": sc["frames"],
                "fps": sc["fps"],
                "vanilla": {
                    "label": sc["vanilla_label"],
                    "img": f"previews/subgames/{gid}_{sc_id}_vanilla.png",
                },
                "modded": {
                    "label": sc["modded_label"],
                    "img": f"previews/subgames/{gid}_{sc_id}_modded.png",
                },
            }
            if sc_vis == "local":
                sc_entry["visibility"] = "local"
            if sc.get("target"):
                sc_entry["target"] = sc["target"]
            scenes_payload.append(sc_entry)

        if not include_local and not scenes_payload:
            continue

        summary = (
            g["public_summary"]
            if (not include_local and g.get("public_summary"))
            else g["summary"]
        )
        game_entry: dict[str, Any] = {
            "id": gid,
            "tab_label": g["tab_label"],
            "name": g["name"],
            "original": g["original"],
            "summary": summary,
            "scenes": scenes_payload,
        }
        all_scenes_local = bool(scenes_payload) and all(
            s.get("visibility") == "local" for s in scenes_payload
        )
        if g_vis == "local" or (include_local and all_scenes_local):
            game_entry["visibility"] = "local"
        if g.get("archived"):
            game_entry["archived"] = True
        games_payload.append(game_entry)

    return {"version": 1, "games": games_payload}


def write_subgames_data_js(
    out_dir: Path | None = None, flavor: str = "all"
) -> list[Path]:
    if flavor not in ("public", "local", "all"):
        raise ValueError(f"Unknown flavor: {flavor}")
    target_dir = DATA_JS.parent if out_dir is None else out_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if flavor in ("public", "all"):
        pub_path = target_dir / DATA_JS.name
        pub_payload = build_subgames_payload(include_local=False)
        pub_path.write_text(
            f"window.BARBA_SUBGAMES_DATA = {json.dumps(pub_payload, indent=2)};\n",
            encoding="utf-8",
        )
        print(f"Wrote {pub_path}")
        written.append(pub_path)

    if flavor in ("local", "all"):
        loc_path = target_dir / LOCAL_DATA_JS.name
        loc_payload = build_subgames_payload(include_local=True)
        loc_path.write_text(
            f"window.BARBA_SUBGAMES_DATA = {json.dumps(loc_payload, indent=2)};\n",
            encoding="utf-8",
        )
        print(f"Wrote {loc_path}")
        written.append(loc_path)

    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", action="append", choices=[g["id"] for g in SUBGAMES], help="Game(s) to capture (defaults to all)")
    parser.add_argument("--tag", choices=["vanilla", "modded", "both"], default="both")
    parser.add_argument("--write-data-only", action="store_true", help="Only regenerate web/subgames_data.js")
    args = parser.parse_args()

    if args.write_data_only:
        write_subgames_data_js()
        return

    targets = [SUBGAMES_BY_ID[gid] for gid in args.game] if args.game else SUBGAMES
    tags = ["vanilla", "modded"] if args.tag == "both" else [args.tag]

    for g in targets:
        for t in tags:
            run_game_capture(g, t)
        if args.tag == "both":
            validate_game_pairs(g)

    write_subgames_data_js()


if __name__ == "__main__":
    main()
