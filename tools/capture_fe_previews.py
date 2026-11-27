"""Capture real 60fps-derived NES gameplay scenes from headless Mesen for Barba Enterprise.

Runs a deterministic Lua capture script against both roms/z2.nes (vanilla) and
build/barba.nes (barba), restoring a clean savestate between every scene and
packing each scene into a 2D-grid PNG sprite sheet in web/previews/.
"""
from __future__ import annotations

import argparse
import json
import struct
import zlib
from pathlib import Path

import emulator_test

ROOT = Path(__file__).resolve().parents[1]
CAP_DIR = ROOT / "build" / "fe-captures"
OUT_DIR = ROOT / "web" / "previews"

SCENES = [
    ("title", 256, 208, 120, 15),
    ("ending", 256, 208, 156, 14),
    ("grass_walk", 256, 176, 144, 20),
    ("grass_attack", 256, 176, 84, 20),
    ("upstab", 256, 176, 64, 20),
    ("downstab", 256, 176, 80, 20),
    ("cave_light", 256, 176, 96, 20),
    ("burned_sign", 256, 176, 168, 20),
    ("ngplus_melt", 256, 176, 84, 15),
    ("ow_scenery", 256, 176, 64, 15),
    ("palace_clouds", 256, 176, 72, 15),
    ("spell_scales", 256, 176, 48, 20),
    ("spell_wyrmling", 256, 176, 48, 20),
    ("spell_meteor", 256, 176, 104, 20),
    ("spell_inferno", 256, 176, 108, 20),
    ("saria_town", 256, 176, 64, 20),
    ("town_chaos", 256, 176, 64, 20),
    ("crossover_portals", 256, 176, 120, 20),
    ("ironknuckle_rebound", 256, 176, 96, 20),
    ("palace_roar", 256, 176, 180, 20),
    ("boss_meter", 256, 208, 80, 20),
    ("game_over", 256, 176, 64, 15),
]

LUA_TEMPLATE = r"""
dofile(TEST_DIR..'/newgame.lua')
local mem = emu.memType.nesMemory
local function r(a) return emu.read(a, mem) end
local function w(a, v) emu.write(a, v, mem) end

local TAG = __TAG__
local CAP_DIR = __CAP_DIR__
local SELECTED = __SELECTED__
local frame = 0
local bootOffset = 0
local phase = SELECTED['title'] and 'title' or 'boot'
local phaseStart = 0
local captured = 0
local buffers = {}
local reportLines = {}

local baseState = nil
local wantBaseSave = false
local wantLoad = false
local pendingPhase = nil
local pendingSetup = nil
local owTargetY = nil
local owTargetX = nil

local SCENE_ORDER = {
    'grass_walk', 'grass_attack', 'upstab', 'downstab', 'cave_light',
    'burned_sign', 'ngplus_melt', 'ow_scenery', 'palace_clouds',
    'spell_scales', 'spell_wyrmling', 'spell_meteor', 'spell_inferno',
    'saria_town', 'town_chaos', 'crossover_portals', 'ironknuckle_rebound',
    'palace_roar', 'boss_meter', 'game_over', 'ending',
}
local sceneCursor = 0

local function finishCapture()
    if phase == 'done' then return end
    phase = 'done'
    local rf = assert(io.open(CAP_DIR..'/'..TAG..'_report.txt', 'w'))
    rf:write(table.concat(reportLines, '\n')..'\n')
    rf:close()
    for _, f in pairs(buffers) do f:close() end
    buffers = {}
    stopScenario(0)
end

local function logReport(line)
    reportLines[#reportLines + 1] = line
end

local function openBuf(name)
    if not buffers[name] then
        buffers[name] = assert(io.open(CAP_DIR..'/'..TAG..'_'..name..'.rgba', 'wb'))
    end
    return buffers[name]
end

local function dumpCrop(name, cx, cy, cw, ch, blankFromY)
    local px = emu.getScreenBuffer()
    local f = openBuf(name)
    local chunks = {}
    local blackRow = string.rep(string.char(0, 0, 0, 255), cw)
    for y = cy, cy + ch - 1 do
        if blankFromY and y >= blankFromY then
            chunks[#chunks + 1] = blackRow
        else
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
    end
    f:write(table.concat(chunks))
end

local function clearSpells()
    w(0x76F, 0); w(0x74A, 0); w(0x74B, 0); w(0x74C, 0)
    w(0x70F, 0); w(0x710, 0)
    w(0xD0, 0); w(0xD9, 0); w(0xDE, 0)
    w(0x57D, 0); w(0x479, 0)
    w(0x728, 0); w(0x767, 0); w(0x0524, 0)
    w(0x6470, 0); w(0x6473, 0); w(0x6474, 0)
    w(0x770, 0xFF); w(0x771, 0xFF)
end

local function clearActors(keepKind)
    for s = 0, 5 do
        if r(0xB6 + s) == 1 then
            local k = r(0xA1 + s)
            if k ~= 0x02 and (not keepKind or k ~= keepKind) then
                w(0xB6 + s, 0)
            end
        end
    end
end

local function pxWorld() return r(0x3B) * 256 + r(0x4D) end
local function camWorld() return r(0x72A) * 256 + r(0xFD) end
local function screenX() return pxWorld() - camWorld() end

local function scheduleScene(nextPhase, setupFn)
    pendingPhase = nextPhase
    pendingSetup = setupFn
    wantLoad = true
end

local function enterGrass()
    clearSpells()
    w(0x707, 0); w(0x706, 0); w(0x70A, 0); w(0x769, 1); w(0x561, 0)
    w(0x568, 0); w(0x56B, 0); w(0x56C, 0); w(0x701, 0)
    w(0x75C, 0); w(0x704, 0); w(0x73D, 0); w(0x726, 1)
    w(0x774, 255); w(0x783, 8); w(0x784, 8); w(0x777, 8); w(0x773, 0xFF)
    w(0x796, 0x14)
    w(0x748, 0xFF); w(0x563, 5); w(0x736, 0)
end

local function enterOverworldAt(owY, owX)
    clearSpells()
    owTargetY = owY
    owTargetX = owX
    w(0x707, 0); w(0x706, 0); w(0x70A, 0); w(0x769, 1)
    w(0x561, 0); w(0x568, 0); w(0x56B, 0); w(0x56C, 0)
    w(0x701, 0); w(0x75C, 0); w(0x704, 0); w(0x73D, 0)
    w(0x73, owY); w(0x74, owX); w(0x562, 1); w(0x563, 5); w(0x748, 0xFF)
    w(0x86, 0); w(0x87, 0); w(0x88, 0); w(0x89, 0)
    w(0x736, 2); w(0x726, 1)
end

local function enterSariaOverworld()
    enterOverworldAt(86, 8)
    w(0x562, 2)
end

local function enterRauruTown(page, room)
    clearSpells()
    w(0xB5, 1); w(0x707, 1); w(0x706, 0); w(0x70A, 0); w(0x769, 3)
    w(0x56B, 0); w(0x561, room or 0); w(0x568, 0); w(0x56C, 0)
    w(0x701, 0); w(0x75C, page); w(0x704, 0)
    w(0x736, 0); w(0x73D, 0); w(0x726, 1); w(0x748, 0x2C)
    w(0x774, 255); w(0x784, 8); w(0x777, 8)
end

local function enterPalaceRoom(room, page)
    clearSpells()
    w(0xB5, 1); w(0x707, 3); w(0x706, 0); w(0x70A, 0); w(0x769, 4)
    w(0x56B, 1); w(0x561, room); w(0x568, 0); w(0x56C, 0)
    w(0x701, 0); w(0x75C, page); w(0x704, 0)
    w(0x736, 0); w(0x73D, 0); w(0x726, 1); w(0x748, 0x34)
    w(0x794, 6); w(0x796, 0x14)
    for flag = 0x78D, 0x792 do w(flag, 0) end
    w(0x700, 9); w(0x774, 255); w(0x773, 255)
    w(0x783, 8); w(0x784, 8); w(0x777, 8); w(0x778, 8); w(0x779, 8)
end

local function enterThunderbird()
    clearSpells()
    w(0x06DA, 0xFF)
    w(0x6E3F, 0); w(0x794, 0)
    for flag = 0x78D, 0x792 do w(flag, 1) end
    w(0xB5, 1); w(0x707, 5); w(0x706, 2); w(0x70A, 2); w(0x769, 5)
    w(0x73, 73); w(0x74, 4); w(0x748, 0x36)
    w(0x56B, 7); w(0x561, 0x35); w(0x568, 6); w(0x56C, 2)
    w(0x701, 0); w(0x75C, 0); w(0x704, 0)
    w(0x736, 0); w(0x73D, 0); w(0x726, 1)
    w(0x700, 9); w(0x774, 255); w(0x773, 255)
    w(0x783, 8); w(0x784, 8); w(0x777, 8); w(0x778, 8); w(0x779, 8)
end

local function enterDarkGrotto()
    clearSpells()
    w(0xB5, 1); w(0x707, 0); w(0x706, 0); w(0x70A, 0); w(0x769, 1)
    w(0x561, 0x0E); w(0x568, 0); w(0x56B, 0); w(0x56C, 0)
    w(0x701, 0); w(0x75C, 0); w(0x704, 0)
    w(0x736, 0); w(0x73D, 0); w(0x726, 1); w(0x748, 0x0F)
    w(0x785, 0)
    w(0x774, 255); w(0x773, 255); w(0x783, 8); w(0x784, 8); w(0x777, 8)
end

local function enterGameOverCombat()
    clearSpells()
    w(0xB5, 1); w(0x707, 3); w(0x706, 0); w(0x70A, 0); w(0x769, 4)
    w(0x561, 5); w(0x568, 0); w(0x56B, 1); w(0x56C, 0)
    w(0x701, 0); w(0x75C, 0); w(0x704, 0)
    w(0x736, 0); w(0x73D, 0); w(0x726, 1); w(0x748, 0x34)
    w(0x700, 1); w(0x774, 1); w(0x784, 8)
    w(0x0494, 0); w(0x050C, 0); w(0x048D, 0)
end

local function prepSpell(learnAddr, spellId)
    w(learnAddr, 1)
    w(0x0749, spellId)
    w(0x074A, 0)
    w(0x0773, 0xFF)
    w(0x0774, 255)
    w(0x0783, 8)
    w(0x0778, 8)
end

local titleScrollStarted = false
local centerDone = false
local centerSettle = 0
local centerStartFrame = 0
local actionStartFrame = 0

local thunderCastDt = nil
local tbPrevX = 0
local tbStuckCount = 0
local tbJumpUntil = 0
local tbSawCast = false

local bossFightDt = nil
local bossSlotIdx = nil
local bossStartHp = nil
local bossMinHp = nil

local meltTargetX = nil
local ngSawMelt = false

local signSub = 'read1'
local signSubDt = 0
local signSlot = nil
local signTargetX = 0x98
local signScorchSeen = false
local signLastPtr = 0
local signStable = 0
local signStartPtr = 0
local signSawDlg1 = false
local signSawDlg2 = false

local grassSub = 'ow'
local grassSideStart = nil
local grassOwFrames = 0
local grassSideFrames = 0
local meteorDive = false

local palaceSawRoar = false
local palaceSawPosShake = false
local palaceSawNegShake = false
local palaceRoarStartDt = nil
local palaceRoarEndDt = nil

local endingTick = 0
local endingMaxStep = 0
local endingSawFire = false

local sawGameOver = false
local goCapStart = nil

local arcadeSub = 'approach'
local arcadeEnterFrame = 0
local arcadeFadeCount = 0

local ikReboundSeen = false
local ikTargetAlive = 1

local function nextScene()
    while true do
        sceneCursor = sceneCursor + 1
        local name = SCENE_ORDER[sceneCursor]
        if not name then
            finishCapture()
            return
        end
        if SELECTED[name] then
            if name == 'grass_walk' then
                scheduleScene('grass_ow_wait', function() enterOverworldAt(42, 28) end)
            elseif name == 'grass_attack' then
                scheduleScene('grass_attack_wait', enterGrass)
            elseif name == 'upstab' then
                scheduleScene('upstab_wait', enterGrass)
            elseif name == 'downstab' then
                scheduleScene('downstab_wait', function() enterPalaceRoom(5, 0) end)
            elseif name == 'cave_light' then
                scheduleScene('cave_light_wait', enterDarkGrotto)
            elseif name == 'burned_sign' then
                signSub = 'read1'; signSubDt = 0; signSlot = nil; signScorchSeen = false
                signLastPtr = 0; signStable = 0; signStartPtr = 0; signSawDlg1 = false; signSawDlg2 = false
                scheduleScene('burned_sign_wait', function() enterRauruTown(0) end)
            elseif name == 'ngplus_melt' then
                ngSawMelt = false
                scheduleScene('ngplus_melt_wait', function()
                    enterOverworldAt(44, 41)
                    w(0x07A0, 2); w(0x0789, 0)
                end)
            elseif name == 'ow_scenery' then
                scheduleScene('ow_scenery_wait', function() enterOverworldAt(42, 28) end)
            elseif name == 'palace_clouds' then
                scheduleScene('palace_clouds_wait', function() enterPalaceRoom(0, 0) end)
            elseif name == 'spell_scales' then
                scheduleScene('spell_scales_wait', enterGrass)
            elseif name == 'spell_wyrmling' then
                scheduleScene('spell_wyrmling_wait', enterGrass)
            elseif name == 'spell_meteor' then
                meteorDive = false
                scheduleScene('spell_meteor_wait', enterGrass)
            elseif name == 'spell_inferno' then
                thunderCastDt = nil; tbPrevX = 0; tbStuckCount = 0; tbJumpUntil = 0; tbSawCast = false
                scheduleScene('spell_inferno_wait', enterThunderbird)
            elseif name == 'saria_town' then
                scheduleScene('saria_ow_wait', enterSariaOverworld)
            elseif name == 'town_chaos' then
                scheduleScene('town_chaos_wait', function() enterRauruTown(1) end)
            elseif name == 'crossover_portals' then
                arcadeSub = 'approach'; arcadeEnterFrame = 0; arcadeFadeCount = 0
                scheduleScene('crossover_portals_wait', function() enterRauruTown(1, 1) end)
            elseif name == 'ironknuckle_rebound' then
                ikReboundSeen = false; ikTargetAlive = 1
                scheduleScene('ironknuckle_rebound_wait', function() enterPalaceRoom(5, 0) end)
            elseif name == 'palace_roar' then
                palaceSawRoar = false; palaceSawPosShake = false; palaceSawNegShake = false
                palaceRoarStartDt = nil; palaceRoarEndDt = nil
                scheduleScene('palace_roar_wait', function() enterPalaceRoom(0x0D, 3) end)
            elseif name == 'boss_meter' then
                bossFightDt = nil; bossSlotIdx = nil; bossStartHp = nil; bossMinHp = nil
                scheduleScene('boss_meter_wait', function()
                    enterPalaceRoom(0x0D, 0)
                    w(0x777, 4)
                end)
            elseif name == 'game_over' then
                sawGameOver = false; goCapStart = nil
                scheduleScene('gameover_wait', enterGameOverCombat)
            elseif name == 'ending' then
                endingTick = 0; endingMaxStep = 0; endingSawFire = false
                scheduleScene('ending_gp_wait', enterThunderbird)
            end
            return
        end
    end
end

emu.addMemoryCallback(function()
    if phase == 'game_over' then
        sawGameOver = true
    end
end, emu.callbackType.exec, 0xCA72)

emu.addMemoryCallback(function()
    if owTargetY and r(0x736) == 2 then
        w(0x73, owTargetY)
        w(0x74, owTargetX)
        owTargetY = nil
        owTargetX = nil
    end
    if wantBaseSave then
        wantBaseSave = false
        baseState = emu.createSavestate()
        nextScene()
    end
    if wantLoad then
        wantLoad = false
        assert(emu.loadSavestate(baseState), 'loadSavestate failed for '..tostring(pendingPhase))
        phase = pendingPhase
        phaseStart = frame
        captured = 0
        if pendingSetup then pendingSetup() end
    end
end, emu.callbackType.exec, 0xC07B)

emu.addEventCallback(function()
    local dt = frame - phaseStart
    if phase == 'title' then
        emu.setInput({}, 0)
    elseif phase == 'boot' then
        emu.setInput(newGameInput(frame - bootOffset), 0)
    elseif phase == 'grass_walk' then
        if grassSub == 'ow' then
            w(0x86, 0); w(0x87, 0); w(0x88, 0); w(0x89, 0)
            local b = {}
            if dt >= 6 and dt < 20 then b.down = true
            elseif dt >= 20 and dt < 34 then b.right = true
            elseif dt >= 34 and dt < 48 then b.up = true
            elseif dt >= 48 and dt < 62 then b.left = true
            elseif dt >= 62 and r(0x82) == 3 then
                local dx = (r(0x4E) - r(0xFD) - 0x80) % 256
                if dx >= 128 then dx = dx - 256 end
                local dy = (r(0x2A) - r(0x7F) - 0x6D) % 256
                if dy >= 128 then dy = dy - 256 end
                if math.abs(dx) >= math.abs(dy) and math.abs(dx) > 4 then
                    if dx < 0 then b.left = true else b.right = true end
                elseif math.abs(dy) > 4 then
                    if dy < 0 then b.up = true else b.down = true end
                else
                    if dx < 0 then b.left = true else b.right = true end
                end
            elseif dt >= 62 then
                b.right = true
            end
            emu.setInput(b, 0)
        elseif grassSub == 'side' and grassSideStart then
            local sdt = dt - grassSideStart
            local right = (sdt >= 4 and sdt < 72)
            local left = (sdt >= 78 and sdt < 144)
            emu.setInput({right = right, left = left}, 0)
        else
            emu.setInput({}, 0)
        end
    elseif phase == 'grass_attack' then
        if not centerDone then
            emu.setInput({right = (pxWorld() < 192)}, 0)
        else
            local adt = frame - actionStartFrame
            local jump = (adt >= 90 and adt < 108) or (adt >= 140 and adt < 158) or (adt >= 195 and adt < 213)
            local fire = (adt >= 6 and adt < 10) or (adt >= 22 and adt < 26)
                      or (adt >= 46 and adt < 50) or (adt >= 66 and adt < 70)
                      or (adt >= 100 and adt < 105)
            local down = (adt >= 40 and adt < 84) or (adt >= 146 and adt < 182)
            local up = (adt >= 201 and adt < 237)
            emu.setInput({a = jump, b = fire, down = down, up = up}, 0)
        end
    elseif phase == 'upstab' then
        if not centerDone then
            emu.setInput({right = (pxWorld() < 192)}, 0)
        else
            local adt = frame - actionStartFrame
            local jump = (adt >= 8 and adt < 36) or (adt >= 68 and adt < 96)
            local holdUp = (adt >= 10 and adt < 58) or (adt >= 70 and adt < 118)
            emu.setInput({a = jump, up = holdUp, b = holdUp}, 0)
        end
    elseif phase == 'downstab' then
        local right = (dt >= 4 and dt < 50) or (dt >= 50 and dt < 138 and pxWorld() < 208)
        local jump = (dt >= 50 and dt < 74)
        local holdDown = (dt >= 74 and dt < 158)
        emu.setInput({right = right, a = jump, down = holdDown}, 0)
    elseif phase == 'cave_light' then
        local fire = (dt >= 16 and dt < 76) and ((dt - 16) % 10 < 3)
        emu.setInput({b = fire}, 0)
    elseif phase == 'burned_sign' then
        local b = {}
        local px = r(0x4D)
        local talkKey = (TAG == 'vanilla') and 'b' or 'up'
        if signSub == 'read1' then
            if r(0x74C) == 0 then
                if px < signTargetX - 10 then b.right = true
                elseif px > signTargetX - 2 then b.left = true
                else w(0x70, 0); b[talkKey] = (signSubDt % 8 < 3) end
            else
                if signStable >= 26 then b.b = (signSubDt % 6 < 2) end
            end
        elseif signSub == 'back_off' then
            if signSubDt < 34 then
                b.left = true
            elseif signSubDt >= 38 and signSubDt < 44 then
                b.right = true
            end
        elseif signSub == 'burn' then
            if not signScorchSeen then
                if TAG == 'vanilla' then
                    if signSubDt < 40 then b.b = (signSubDt % 12 < 3) end
                else
                    local t = signSubDt % 36
                    if signSubDt < 40 then b.b = (t % 8 < 3)
                    else b.a = (t < 16); b.b = (t >= 8 and t < 12) end
                end
            end
        elseif signSub == 'read2' then
            if r(0x74C) == 0 then
                if px < signTargetX - 10 then b.right = true
                elseif px > signTargetX - 2 then b.left = true
                else w(0x70, 0); b[talkKey] = (signSubDt % 8 < 3) end
            end
        end
        emu.setInput(b, 0)
    elseif phase == 'ngplus_melt' then
        w(0x86, 0); w(0x87, 0); w(0x88, 0); w(0x89, 0)
        local b = {}
        if dt >= 4 and dt < 10 then b.right = true
        elseif dt >= 16 and dt < 22 then b.b = true
        elseif dt >= 48 and dt < 80 then b.right = true
        elseif dt >= 86 and dt < 92 then b.b = true
        elseif dt >= 118 and dt < 150 then b.right = true
        end
        emu.setInput(b, 0)
    elseif phase == 'ow_scenery' then
        w(0x86, 0); w(0x87, 0); w(0x88, 0); w(0x89, 0)
        emu.setInput({}, 0)
    elseif phase == 'palace_clouds' then
        emu.setInput({}, 0)
    elseif phase == 'spell_scales' then
        if not centerDone then
            emu.setInput({right = (pxWorld() < 192)}, 0)
        else
            local adt = frame - actionStartFrame
            local fire = (adt >= 64 and adt < 68) or (adt >= 88 and adt < 92)
            emu.setInput({select = (adt >= 16 and adt < 20), right = (adt >= 34 and adt < 58), b = fire}, 0)
        end
    elseif phase == 'spell_wyrmling' then
        if not centerDone then
            emu.setInput({right = (pxWorld() < 192)}, 0)
        else
            local adt = frame - actionStartFrame
            emu.setInput({
                select = (adt >= 16 and adt < 20),
                right = (adt >= 34 and adt < 82),
                up = (adt >= 38 and adt < 88),
                left = (adt >= 82 and adt < 118),
            }, 0)
        end
    elseif phase == 'spell_meteor' then
        if not centerDone then
            emu.setInput({right = (pxWorld() < 192)}, 0)
        else
            local adt = frame - actionStartFrame
            local cast = (adt >= 6 and adt < 10)
            local jump = (adt >= 18 and adt < 46) or (adt >= 112 and adt < 140)
            local dive = meteorDive and (r(0x479) ~= 0)
            emu.setInput({select = cast, a = jump, down = dive, b = dive}, 0)
        end
    elseif phase == 'spell_inferno' then
        if not thunderCastDt then
            local px = pxWorld()
            local jump = (frame <= tbJumpUntil)
            emu.setInput({right = (px < 366), a = jump}, 0)
        else
            local fdt = dt - thunderCastDt
            local cast = (not tbSawCast) and (fdt >= 18) and ((fdt - 18) % 10 < 4)
            local fire = (fdt >= 95) and (fdt % 14 < 4)
            local jump = (TAG == 'vanilla') and (fdt >= 120) and (fdt % 34 < 16)
            emu.setInput({select = cast, b = fire, a = jump}, 0)
        end
    elseif phase == 'saria_ow' then
        w(0x86, 0); w(0x87, 0); w(0x88, 0); w(0x89, 0)
        emu.setInput({down = true}, 0)
    elseif phase == 'saria_town' then
        emu.setInput({left = (dt >= 6)}, 0)
    elseif phase == 'town_chaos' then
        local right = (dt >= 10 and dt < 32) or (dt >= 120 and dt < 144)
        local left = (dt >= 62 and dt < 92)
        local fire = (dt >= 12) and (dt % 14 < 4)
        emu.setInput({right = right, left = left, b = fire}, 0)
    elseif phase == 'crossover_portals' then
        if arcadeSub == 'approach' then
            emu.setInput({right = (r(0x4D) < 40)}, 0)
        elseif arcadeSub == 'enter' then
            local ef = frame - arcadeEnterFrame
            emu.setInput({up = (ef >= 6 and ef < 12)}, 0)
        elseif arcadeSub == 'hallway' then
            emu.setInput({right = true}, 0)
        else
            emu.setInput({}, 0)
        end
    elseif phase == 'ironknuckle_rebound' then
        if not centerDone then
            emu.setInput({}, 0)
        else
            local adt = frame - actionStartFrame
            if TAG == 'vanilla' then
                local step = (pxWorld() < 194)
                local down = (adt < 88)
                local slash = (adt >= 16 and adt < 20) or (adt >= 48 and adt < 52)
                           or (adt >= 94 and adt < 98) or (adt >= 148 and adt < 152)
                emu.setInput({right = step, b = slash, down = down}, 0)
            else
                local down = (adt < 88)
                local fire = (adt >= 14 and adt < 18) or (adt >= 52 and adt < 56)
                          or (adt >= 94 and adt < 98) or (adt >= 148 and adt < 152)
                emu.setInput({b = fire, down = down}, 0)
            end
        end
    elseif phase == 'palace_roar' then
        emu.setInput({right = (dt >= 8 and r(0x794) == 6)}, 0)
    elseif phase == 'boss_meter' then
        local px = pxWorld()
        if not bossFightDt then
            emu.setInput({right = (px < 388)}, 0)
        else
            local fdt = dt - bossFightDt
            local jump = (TAG == 'vanilla') and (fdt % 32 < 12) or (fdt % 34 < 16)
            local fire = (TAG == 'vanilla') and (fdt % 32 >= 6 and fdt % 32 < 12) or (fdt % 10 < 4)
            local lo = (TAG == 'vanilla') and 406 or 384
            local hi = (TAG == 'vanilla') and 418 or 406
            emu.setInput({right = (px < lo), left = (px > hi), a = jump, b = fire}, 0)
        end
    else
        emu.setInput({}, 0)
    end
end, emu.eventType.inputPolled)

local function waitReady(nextPhase, settleFrames)
    local need = settleFrames or 20
    if frame >= phaseStart + need and r(0x736) == 11 and r(0x726) == 0 and r(0x29) > 0 then
        phase = nextPhase
        phaseStart = frame
        captured = 0
        centerDone = false
        centerSettle = 0
        centerStartFrame = frame
        actionStartFrame = frame
        return true
    elseif frame > phaseStart + 240 then
        phase = nextPhase
        phaseStart = frame
        captured = 0
        centerDone = false
        centerSettle = 0
        centerStartFrame = frame
        actionStartFrame = frame
        return true
    end
    return false
end

local function stepCenterWalk(targetPx)
    if centerDone then return true end
    w(0x774, 255); w(0x050C, 0)
    clearActors()
    if pxWorld() >= targetPx or (frame - centerStartFrame) >= 90 then
        w(0x70, 0)
        centerSettle = centerSettle + 1
        if centerSettle >= 8 then
            centerDone = true
            actionStartFrame = frame
            return true
        end
    end
    return false
end

emu.addEventCallback(function()
    frame = frame + 1
    if phase == 'title' then
        if not titleScrollStarted and ((r(0x736) == 3 and r(0x0726) == 0 and r(0xFC) >= 0x34) or frame >= 320) then
            titleScrollStarted = true
        end
        if titleScrollStarted and frame % 5 == 0 and captured < 120 then
            dumpCrop('title', 0, 24, 256, 208)
            captured = captured + 1
            if captured >= 120 then
                logReport(string.format('title frames=%d endMode=%d endFC=%02X', captured, r(0x736), r(0xFC)))
                bootOffset = frame - 170
                phase = 'boot'
                phaseStart = frame
                captured = 0
            end
        end
    elseif phase == 'boot' then
        if (frame - bootOffset) >= 950 and r(0x736) == 11 and r(0x726) == 0 and r(0x29) > 0 then
            wantBaseSave = true
            phase = 'boot_saving'
        end
    elseif phase == 'grass_ow_wait' then
        w(0x86, 0); w(0x87, 0); w(0x88, 0); w(0x89, 0)
        if r(0x736) == 5 and r(0x726) == 0 and (frame - phaseStart) >= 20 then
            grassSub = 'ow'; grassSideStart = nil
            grassOwFrames = 0; grassSideFrames = 0
            phase = 'grass_walk'
            phaseStart = frame
            captured = 0
            w(0x050E, 0x60)
            w(0x82, 3)
            w(0x2A, (r(0x7F) + 0x74) % 256)
            w(0x4E, (r(0xFD) + 0xB0) % 256)
            w(0x056D, 0); w(0x0575, 0)
        end
    elseif phase == 'grass_walk' then
        local dt = frame - phaseStart
        if grassSub == 'ow' then
            if r(0x736) ~= 5 then
                grassSub = 'trans'
            else
                if r(0x82) == 3 then
                    if r(0x050E) < 0x20 then w(0x050E, 0x60) end
                    local fy = (r(0x2A) - r(0x7F)) % 256
                    local vy = r(0x056D)
                    if vy >= 128 then vy = vy - 256 end
                    if fy < 0x6A and vy < 0 then w(0x056D, 0) end
                    if dt >= 62 then
                        local dx = (r(0x4E) - r(0xFD) - 0x80) % 256
                        if dx >= 128 then dx = dx - 256 end
                        local dy = (r(0x2A) - r(0x7F) - 0x6D) % 256
                        if dy >= 128 then dy = dy - 256 end
                        local vx = r(0x0575)
                        if vx >= 128 then vx = vx - 256 end
                        if (dx > 0 and vx > 0) or (dx < 0 and vx < 0) then w(0x0575, 0) end
                        if (dy > 0 and vy > 0) or (dy < 0 and vy < 0) then w(0x056D, 0) end
                    end
                end
                if dt >= 2 and dt % 2 == 0 and captured < 84 then
                    dumpCrop('grass_walk', 0, 32, 256, 176)
                    captured = captured + 1
                    grassOwFrames = grassOwFrames + 1
                end
            end
        elseif grassSub == 'trans' then
            if r(0x736) ~= 11 and dt % 2 == 0 and captured < 92 then
                dumpCrop('grass_walk', 0, 32, 256, 176)
                captured = captured + 1
            end
            if r(0x736) == 11 and r(0x726) == 0 then
                grassSub = 'side'
                grassSideStart = dt
            end
        elseif grassSub == 'side' then
            if dt % 2 == 0 and captured < 144 then
                dumpCrop('grass_walk', 0, 32, 256, 176)
                captured = captured + 1
                grassSideFrames = grassSideFrames + 1
            end
            if captured >= 144 then
                logReport(string.format('grass_walk frames=%d owFrames=%d sideFrames=%d endPx=%d screenX=%d',
                    captured, grassOwFrames, grassSideFrames, pxWorld(), screenX()))
                nextScene()
            end
        end
    elseif phase == 'grass_attack_wait' then
        waitReady('grass_attack')
    elseif phase == 'grass_attack' then
        if stepCenterWalk(192) then
            local adt = frame - actionStartFrame
            if adt % 3 == 0 and captured < 84 then
                dumpCrop('grass_attack', 0, 32, 256, 176)
                captured = captured + 1
                if captured >= 84 then
                    logReport(string.format('grass_attack frames=%d px=%d screenX=%d', captured, pxWorld(), screenX()))
                    nextScene()
                end
            end
        end
    elseif phase == 'upstab_wait' then
        if waitReady('upstab') then
            w(0x796, 0x14); w(0x4D, 72); w(0x3B, 0); w(0x9F, 1); w(0x5F, 1)
        end
    elseif phase == 'upstab' then
        if stepCenterWalk(192) then
            local adt = frame - actionStartFrame
            if adt >= 2 and adt % 2 == 0 and captured < 64 then
                dumpCrop('upstab', 0, 32, 256, 176)
                captured = captured + 1
                if captured >= 64 then
                    logReport(string.format('upstab frames=%d px=%d screenX=%d', captured, pxWorld(), screenX()))
                    nextScene()
                end
            end
        end
    elseif phase == 'downstab_wait' then
        if waitReady('downstab') then
            clearActors()
            w(0x796, 0x14); w(0x76F, 0)
            w(0x3B, 0); w(0x4D, 48); w(0x29, 176); w(0x9F, 1); w(0x5F, 1); w(0x70, 0)
            w(0xB6 + 1, 1); w(0xA1 + 1, 0x04); w(0x4E + 1, 162); w(0x3C + 1, 0); w(0x2A + 1, 176); w(0xC2 + 1, 4); w(0x040E + 1, 0); w(0x71 + 1, 0)
            w(0xB6 + 2, 1); w(0xA1 + 2, 0x04); w(0x4E + 2, 196); w(0x3C + 2, 0); w(0x2A + 2, 176); w(0xC2 + 2, 4); w(0x040E + 2, 0); w(0x71 + 2, 0)
        end
    elseif phase == 'downstab' then
        local dt = frame - phaseStart
        if dt < 50 then
            if r(0xB6 + 1) == 1 then w(0x4E + 1, 162); w(0x71 + 1, 0) end
            if r(0xB6 + 2) == 1 then w(0x4E + 2, 196); w(0x71 + 2, 0) end
        end
        if dt >= 4 and dt % 2 == 0 and captured < 80 then
            dumpCrop('downstab', 0, 32, 256, 176)
            captured = captured + 1
            if captured >= 80 then
                logReport(string.format('downstab frames=%d endPx=%d screenX=%d bot1=%d bot2=%d',
                    captured, pxWorld(), screenX(), r(0xB6 + 1), r(0xB6 + 2)))
                nextScene()
            end
        end
    elseif phase == 'cave_light_wait' then
        if waitReady('cave_light', 36) then
            clearActors()
            w(0x785, 0)
            w(0x72A, 1); w(0x72C, 0x28); w(0x3B, 1); w(0x4D, 0xA8); w(0x29, 0x80)
            w(0x9F, 1); w(0x5F, 1); w(0x70, 0); w(0x479, 0); w(0x57D, 0)
        end
    elseif phase == 'cave_light' then
        local dt = frame - phaseStart
        w(0x785, 0)
        clearActors()
        w(0x29, 0x80); w(0x57D, 0); w(0x479, 0)
        if dt == 1 then
            w(0x72A, 1); w(0x72C, 0x28); w(0x3B, 1); w(0x4D, 0xA8)
            w(0x70, 0)
        end
        if dt >= 4 and dt % 2 == 0 and captured < 96 then
            dumpCrop('cave_light', 0, 32, 256, 176)
            captured = captured + 1
            if captured >= 96 then
                logReport(string.format('cave_light frames=%d 07AF=%02X 0785=%d px=%d py=%d screenX=%d',
                    captured, r(0x07AF), r(0x785), pxWorld(), r(0x29), screenX()))
                nextScene()
            end
        end
    elseif phase == 'burned_sign_wait' then
        if waitReady('burned_sign') then
            clearActors(0x22)
            for s = 0, 5 do
                if r(0xB6 + s) == 1 and r(0xA1 + s) == 0x22 then
                    signSlot = s
                    local sx = r(0x4E + s)
                    signTargetX = sx
                    w(0x3B, r(0x3C + s))
                    w(0x4D, math.max(24, sx - 48))
                    w(0x9F, 1); w(0x5F, 1); w(0x70, 0)
                end
            end
        end
    elseif phase == 'burned_sign' then
        clearActors(0x22)
        local dt = frame - phaseStart
        signSubDt = signSubDt + 1
        local ptrNow = r(0x569) + r(0x56A) * 256
        if r(0x74C) ~= 0 then
            if ptrNow ~= signLastPtr then
                signLastPtr = ptrNow
                signStable = 0
            else
                signStable = signStable + 1
            end
        else
            signLastPtr = ptrNow
            signStable = 0
        end
        if signSub == 'read1' then
            if r(0x74C) ~= 0 then
                signSawDlg1 = true
            elseif signSawDlg1 and signSubDt > 16 then
                signSub = 'back_off'; signSubDt = 0
            elseif signSubDt > 160 then
                signSub = 'back_off'; signSubDt = 0
            end
        elseif signSub == 'back_off' then
            if signSubDt >= 44 then
                signSub = 'burn'; signSubDt = 0
            end
        elseif signSub == 'burn' then
            if signSlot and r(0x4A0 + signSlot) ~= 0 then
                if not signScorchSeen then
                    signScorchSeen = true
                    signSubDt = 0
                end
            end
            if (signScorchSeen and signSubDt >= 26) or (not signScorchSeen and signSubDt >= 88) then
                signSub = 'read2'; signSubDt = 0
            end
        elseif signSub == 'read2' then
            if r(0x74C) ~= 0 then signSawDlg2 = true end
        end
        if dt % 3 == 0 and captured < 168 then
            dumpCrop('burned_sign', 0, 32, 256, 176)
            captured = captured + 1
            if captured >= 168 then
                logReport(string.format('burned_sign frames=%d room=%02X slot=%s dlg1=%s scorch=%s dlg2=%s',
                    captured, r(0x561), tostring(signSlot), tostring(signSawDlg1), tostring(signScorchSeen), tostring(signSawDlg2)))
                nextScene()
            end
        end
    elseif phase == 'ngplus_melt_wait' then
        w(0x86, 0); w(0x87, 0); w(0x88, 0); w(0x89, 0)
        if r(0x736) == 5 and r(0x726) == 0 and (frame - phaseStart) >= 24 then
            w(0x07A0, 2); w(0x0789, 0)
            meltTargetX = r(0x74)
            phase = 'ngplus_melt'
            phaseStart = frame
            captured = 0
        elseif frame > phaseStart + 240 then
            phase = 'ngplus_melt'; phaseStart = frame; captured = 0
        end
    elseif phase == 'ngplus_melt' then
        local dt = frame - phaseStart
        w(0x07A0, 2); w(0x0789, 0)
        w(0x86, 0); w(0x87, 0); w(0x88, 0); w(0x89, 0)
        if meltTargetX and r(0x74) > meltTargetX then ngSawMelt = true end
        if dt % 2 == 0 and captured < 84 then
            dumpCrop('ngplus_melt', 0, 32, 256, 176)
            captured = captured + 1
            if captured >= 84 then
                logReport(string.format('ngplus_melt frames=%d ow=(%d,%d) moved=%s',
                    captured, r(0x73), r(0x74), tostring(ngSawMelt)))
                nextScene()
            end
        end
    elseif phase == 'ow_scenery_wait' then
        w(0x86, 0); w(0x87, 0); w(0x88, 0); w(0x89, 0)
        if r(0x736) == 5 and r(0x726) == 0 and (frame - phaseStart) >= 24 then
            phase = 'ow_scenery'
            phaseStart = frame
            captured = 0
        elseif frame > phaseStart + 240 then
            phase = 'ow_scenery'; phaseStart = frame; captured = 0
        end
    elseif phase == 'ow_scenery' then
        local dt = frame - phaseStart
        w(0x86, 0); w(0x87, 0); w(0x88, 0); w(0x89, 0)
        if dt % 3 == 0 and captured < 64 then
            dumpCrop('ow_scenery', 0, 32, 256, 176)
            captured = captured + 1
            if captured >= 64 then
                logReport(string.format('ow_scenery frames=%d ow=(%d,%d)', captured, r(0x73), r(0x74)))
                nextScene()
            end
        end
    elseif phase == 'palace_clouds_wait' then
        waitReady('palace_clouds', 24)
    elseif phase == 'palace_clouds' then
        local dt = frame - phaseStart
        if dt % 6 == 0 and captured < 72 then
            dumpCrop('palace_clouds', 0, 32, 256, 176)
            captured = captured + 1
            if captured >= 72 then
                logReport(string.format('palace_clouds frames=%d px=%d room=%02X', captured, pxWorld(), r(0x561)))
                nextScene()
            end
        end
    elseif phase == 'spell_scales_wait' then
        if waitReady('spell_scales') then prepSpell(0x077B, 0) end
    elseif phase == 'spell_scales' then
        if stepCenterWalk(192) then
            local adt = frame - actionStartFrame
            if adt % 3 == 0 and captured < 48 then
                dumpCrop('spell_scales', 0, 32, 256, 176)
                captured = captured + 1
                if captured >= 48 then
                    logReport(string.format('spell_scales frames=%d px=%d screenX=%d', captured, pxWorld(), screenX()))
                    nextScene()
                end
            end
        end
    elseif phase == 'spell_wyrmling_wait' then
        if waitReady('spell_wyrmling') then prepSpell(0x077E, 3) end
    elseif phase == 'spell_wyrmling' then
        if stepCenterWalk(192) then
            local adt = frame - actionStartFrame
            if adt % 3 == 0 and captured < 48 then
                dumpCrop('spell_wyrmling', 0, 32, 256, 176)
                captured = captured + 1
                if captured >= 48 then
                    logReport(string.format('spell_wyrmling frames=%d px=%d screenX=%d', captured, pxWorld(), screenX()))
                    nextScene()
                end
            end
        end
    elseif phase == 'spell_meteor_wait' then
        if waitReady('spell_meteor') then prepSpell(0x077F, 4) end
    elseif phase == 'spell_meteor' then
        if stepCenterWalk(192) then
            local adt = frame - actionStartFrame
            if r(0x479) == 0 then meteorDive = false end
            if not meteorDive and adt >= 28 and adt < 90 and r(0x479) ~= 0 and r(0x57D) < 0x80 then
                meteorDive = true
            elseif not meteorDive and adt >= 122 and r(0x479) ~= 0 and r(0x57D) < 0x80 then
                meteorDive = true
            end
            if adt >= 4 and adt % 2 == 0 and captured < 104 then
                dumpCrop('spell_meteor', 0, 32, 256, 176)
                captured = captured + 1
                if captured >= 104 then
                    logReport(string.format('spell_meteor frames=%d px=%d screenX=%d', captured, pxWorld(), screenX()))
                    nextScene()
                end
            end
        end
    elseif phase == 'spell_inferno_wait' then
        if waitReady('spell_inferno') then
            prepSpell(0x0782, 7)
            thunderCastDt = nil; tbPrevX = 0; tbStuckCount = 0; tbJumpUntil = 0; tbSawCast = false
        end
    elseif phase == 'spell_inferno' then
        local dt = frame - phaseStart
        w(0x774, 255); w(0x050C, 0)
        if not thunderCastDt then
            local px = pxWorld()
            if px <= tbPrevX and px < 366 then
                tbStuckCount = tbStuckCount + 1
                if tbStuckCount >= 5 and frame > tbJumpUntil then
                    tbJumpUntil = frame + 18
                    tbStuckCount = 0
                end
            else
                tbStuckCount = 0
            end
            tbPrevX = px
            local tbActive = false
            local tbInfo = 'none'
            for s = 0, 5 do
                if r(0xB6 + s) == 1 and r(0xA1 + s) == 0x22 then
                    local tx = r(0x3C + s) * 256 + r(0x4E + s)
                    tbInfo = string.format('s=%d tx=%d ty=%d inv=%d', s, tx, r(0x2A + s), r(0x0504 + s))
                    if r(0x0504 + s) == 0 and tx >= 320 and tx <= 504 then
                        tbActive = true
                    end
                end
            end
            if (px >= 364 and r(0x479) == 0 and tbActive) or dt >= 480 then
                w(0x70, 0)
                thunderCastDt = dt
                logReport(string.format('spell_inferno_start dt=%d px=%d tb=%s', dt, px, tbInfo))
            end
        else
            local fdt = dt - thunderCastDt
            if fdt == 14 then
                prepSpell(0x0782, 7)
            end
            if r(0x6470) > 0 or r(0xD9) > 0 or r(0x074B) > 0 then
                tbSawCast = true
            end
            if fdt % 2 == 0 and captured < 108 then
                dumpCrop('spell_inferno', 0, 32, 256, 176)
                captured = captured + 1
                if captured >= 108 then
                    logReport(string.format('spell_inferno frames=%d px=%d screenX=%d cast=%s',
                        captured, pxWorld(), screenX(), tostring(tbSawCast)))
                    nextScene()
                end
            end
        end
    elseif phase == 'saria_ow_wait' then
        w(0x86, 0); w(0x87, 0); w(0x88, 0); w(0x89, 0)
        if frame >= phaseStart + 12 and r(0x736) == 5 and r(0x726) == 0 then
            phase = 'saria_ow'; phaseStart = frame; captured = 0
        elseif frame > phaseStart + 160 then
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
        if r(0x736) == 11 and (frame - phaseStart) % 3 == 0 and captured < 64 then
            dumpCrop('saria_town', 0, 64, 256, 176)
            captured = captured + 1
            if captured >= 64 then
                logReport(string.format('saria_town frames=%d', captured))
                nextScene()
            end
        elseif frame - phaseStart > 400 then
            while captured < 64 do
                dumpCrop('saria_town', 0, 64, 256, 176)
                captured = captured + 1
            end
            nextScene()
        end
    elseif phase == 'town_chaos_wait' then
        if waitReady('town_chaos') then
            w(0x3B, 1); w(0x4D, 112); w(0x57D, 0); w(0x479, 0)
        end
    elseif phase == 'town_chaos' then
        if (frame - phaseStart) % 3 == 0 and captured < 64 then
            dumpCrop('town_chaos', 0, 32, 256, 176)
            captured = captured + 1
            if captured >= 64 then
                logReport(string.format('town_chaos frames=%d', captured))
                nextScene()
            end
        end
    elseif phase == 'crossover_portals_wait' then
        clearActors()
        if waitReady('crossover_portals') then
            clearActors()
            if TAG ~= 'vanilla' then
                w(0x6806, 0xFF); w(0x6807, 0xFF)
                w(0x05EA, 0); w(0x6460, 0); w(0x6462, 0)
                if r(0x6467) ~= 0 then w(0x6468, 1) end
            end
            w(0x3B, 1); w(0x4D, 24); w(0x9F, 1); w(0x5F, 1); w(0x70, 0)
            arcadeSub = 'approach'; arcadeEnterFrame = 0; arcadeFadeCount = 0
        end
    elseif phase == 'crossover_portals' then
        local dt = frame - phaseStart
        local wantCap = (dt % 3 == 0)
        if arcadeSub == 'approach' then
            if TAG ~= 'vanilla' then
                clearActors()
                w(0x05EA, 0); w(0x6460, 0); w(0x6462, 0)
                if r(0x6467) ~= 0 then w(0x6468, 1) end
            end
            if r(0x4D) >= 40 then
                w(0x70, 0)
                arcadeSub = 'enter'
                arcadeEnterFrame = frame
            end
        elseif arcadeSub == 'enter' then
            local ef = frame - arcadeEnterFrame
            if TAG ~= 'vanilla' and r(0x561) ~= 0x1C then
                clearActors()
                w(0x05EA, 0); w(0x6460, 0); w(0x6462, 0)
                if r(0x6467) ~= 0 then w(0x6468, 1) end
            end
            if r(0x726) ~= 0 then
                arcadeFadeCount = arcadeFadeCount + 1
                if arcadeFadeCount > 3 then wantCap = false end
            end
            if ef > 12 and r(0x561) == 0x1C and r(0x736) == 11 and r(0x726) == 0 then
                arcadeSub = 'hallway'
            elseif ef > 180 then
                arcadeSub = 'hallway'
            end
        elseif arcadeSub == 'hallway' then
            if TAG ~= 'vanilla' then
                w(0x6806, 0xFF); w(0x6807, 0xFF)
            end
        end
        if wantCap and captured < 120 then
            dumpCrop('crossover_portals', 0, 32, 256, 176)
            captured = captured + 1
            if captured >= 120 then
                logReport(string.format('crossover_portals frames=%d room=%02X endPage=%d endX=%d',
                    captured, r(0x561), r(0x3B), r(0x4D)))
                nextScene()
            end
        end
    elseif phase == 'ironknuckle_rebound_wait' then
        if waitReady('ironknuckle_rebound') then
            clearActors()
            w(0x72A, 0); w(0x72C, 52); w(0xFD, 52)
            w(0x3B, 0); w(0x4D, 184); w(0x29, 176); w(0x9F, 1); w(0x5F, 1); w(0x70, 0); w(0x479, 0); w(0x57D, 0); w(0x777, 4)
            w(0xB6 + 1, 1); w(0xA1 + 1, 0x18)
            w(0x4E + 1, 224); w(0x3C + 1, 0); w(0x2A + 1, 176)
            w(0xC2 + 1, 0x0C); w(0x0444 + 1, 0); w(0x60 + 1, 2)
            w(0x040E + 1, 0); w(0x71 + 1, 0); w(0xA8 + 1, 0); w(0xAF + 1, 0); w(0x0504 + 1, 0x20)
            w(0xB6 + 2, 1); w(0xA1 + 2, 0x04); w(0xC2 + 2, 4)
            w(0x4E + 2, 152); w(0x3C + 2, 0); w(0x2A + 2, 192)
            w(0x040E + 2, 0); w(0x71 + 2, 0); w(0x1A + 2, 1)
            w(0xA8 + 2, 0); w(0xAF + 2, 0); w(0x057E + 2, 0)
            ikReboundSeen = false; ikTargetAlive = 1
        end
    elseif phase == 'ironknuckle_rebound' then
        w(0x774, 255); w(0x050C, 0); w(0x777, 4)
        if not centerDone then
            w(0x72A, 0); w(0x72C, 52); w(0xFD, 52)
            w(0x3B, 0); w(0x4D, 184); w(0x9F, 1); w(0x5F, 1); w(0x70, 0)
            w(0x4E + 1, 224); w(0x71 + 1, 0); w(0x0444 + 1, 0); w(0x60 + 1, 2); w(0xA8 + 1, 0); w(0xAF + 1, 0); w(0x0504 + 1, 0x20)
            if r(0xB6 + 2) == 1 then w(0x4E + 2, 152); w(0x71 + 2, 0); w(0xA8 + 2, 0); w(0x057E + 2, 0) end
            centerSettle = centerSettle + 1
            if centerSettle >= 12 then
                centerDone = true
                actionStartFrame = frame
            end
        else
            local adt = frame - actionStartFrame
            if r(0xB6 + 1) == 1 then
                w(0x4E + 1, 224); w(0x71 + 1, 0); w(0x0444 + 1, 0); w(0x60 + 1, 2); w(0xA8 + 1, 0); w(0xAF + 1, 0); w(0x0504 + 1, 0x20)
            end
            if r(0xB6 + 2) == 1 then
                w(0x4E + 2, 152); w(0x71 + 2, 0); w(0xA8 + 2, 0); w(0x057E + 2, 0)
            end
            if (r(0x8D) == 1 and r(0x7D) == 0xC8) or (r(0x8E) == 1 and r(0x7E) == 0xC8) then
                ikReboundSeen = true
            end
            ikTargetAlive = r(0xB6 + 2)
            if adt >= 2 and adt % 2 == 0 and captured < 96 then
                dumpCrop('ironknuckle_rebound', 0, 32, 256, 176)
                captured = captured + 1
                if captured >= 96 then
                    logReport(string.format('ironknuckle_rebound frames=%d px=%d screenX=%d reboundSeen=%s targetKind=%02X targetY=%d targetAlive=%d ikAlive=%d ikHp=%d',
                        captured, pxWorld(), screenX(), tostring(ikReboundSeen), r(0xA1 + 2), r(0x2A + 2), ikTargetAlive, r(0xB6 + 1), r(0xC2 + 1)))
                    nextScene()
                end
            end
        end
    elseif phase == 'palace_roar_wait' then
        if waitReady('palace_roar_settle') then
            w(0x3B, 3); w(0x4D, 80); w(0x29, 144); w(0x57D, 0); w(0x479, 0)
        end
    elseif phase == 'palace_roar_settle' then
        if frame - phaseStart >= 24 then
            palaceSawRoar = false; palaceSawPosShake = false; palaceSawNegShake = false
            palaceRoarStartDt = nil; palaceRoarEndDt = nil
            phase = 'palace_roar'
            phaseStart = frame
            captured = 0
        end
    elseif phase == 'palace_roar' then
        local dt = frame - phaseStart
        if TAG ~= 'vanilla' then
            local roaring = (r(0x5EE) & 0x88) == 0x88
            if roaring then
                palaceSawRoar = true
                if not palaceRoarStartDt then palaceRoarStartDt = dt end
                palaceRoarEndDt = dt
                local shake = r(0x64FA)
                if shake == 4 then palaceSawPosShake = true end
                if shake == 0xFC then palaceSawNegShake = true end
            end
        end
        if dt % 3 == 0 and captured < 180 then
            dumpCrop('palace_roar', 0, 32, 256, 176)
            captured = captured + 1
            if captured >= 180 then
                logReport(string.format('palace_roar frames=%d crystals=%d sawRoar=%s posShake=%s negShake=%s roarDt=%s..%s endMode=%d',
                    captured, r(0x794), tostring(palaceSawRoar), tostring(palaceSawPosShake), tostring(palaceSawNegShake),
                    tostring(palaceRoarStartDt), tostring(palaceRoarEndDt), r(0x736)))
                nextScene()
            end
        end
    elseif phase == 'boss_meter_wait' then
        if waitReady('boss_meter') then
            bossFightDt = nil; bossSlotIdx = nil; bossStartHp = nil; bossMinHp = nil
        end
    elseif phase == 'boss_meter' then
        local dt = frame - phaseStart
        local px = pxWorld()
        w(0x774, 255); w(0x770, 0xFF); w(0x771, 0xFF); w(0x777, 4)
        for s = 0, 5 do
            if r(0xB6 + s) == 1 and r(0xA1 + s) == 0x20 then
                bossSlotIdx = s
                local hp = r(0xC2 + s)
                if not bossStartHp and hp > 0 and hp < 0xF0 then bossStartHp = hp; bossMinHp = hp end
                if bossMinHp and hp < bossMinHp then bossMinHp = hp end
            end
        end
        if not bossFightDt and ((px >= 380 and r(0x728) ~= 0 and bossSlotIdx ~= nil) or dt >= 320) then
            bossFightDt = dt
        end
        if bossFightDt and dt >= bossFightDt and (dt - bossFightDt) % 2 == 0 and captured < 80 then
            dumpCrop('boss_meter', 0, 32, 256, 208, (TAG == 'vanilla') and 224 or nil)
            captured = captured + 1
            if captured >= 80 then
                logReport(string.format('boss_meter frames=%d px=%d lock=%d slot=%s hp=%s->%s',
                    captured, px, r(0x728), tostring(bossSlotIdx), tostring(bossStartHp), tostring(bossMinHp)))
                nextScene()
            end
        end
    elseif phase == 'gameover_wait' then
        if waitReady('game_over') then
            clearActors()
            w(0x700, 1); w(0x774, 1); w(0x0494, 0); w(0x050C, 0); w(0x048D, 0)
            w(0xB6 + 1, 1); w(0xA1 + 1, 0x04); w(0xC2 + 1, 4)
            w(0x4E + 1, r(0x4D)); w(0x3C + 1, r(0x3B)); w(0x2A + 1, r(0x29))
            w(0x040E + 1, 0); w(0xA8 + 1, 0); w(0xAF + 1, 0); w(0x1A + 1, 1); w(0x71 + 1, 0)
            sawGameOver = false; goCapStart = nil
        end
    elseif phase == 'game_over' then
        if not sawGameOver then
            if r(0x736) == 11 and r(0x774) > 0 and (frame - phaseStart) % 15 == 0 then
                w(0x700, 1); w(0x774, 1); w(0x0494, 0); w(0x050C, 0)
                w(0xB6 + 1, 1); w(0xA1 + 1, 0x04)
                w(0x4E + 1, r(0x4D)); w(0x3C + 1, r(0x3B)); w(0x2A + 1, r(0x29))
            end
        elseif not goCapStart then
            if r(0x726) == 0 then
                goCapStart = frame + 6
            end
        elseif frame >= goCapStart then
            w(0x0501, 0x80)
            if (frame - goCapStart) % 2 == 0 and captured < 64 then
                dumpCrop('game_over', 0, 32, 256, 176)
                captured = captured + 1
                if captured >= 64 then
                    logReport(string.format('game_over frames=%d sawCA72=%s mode=%d', captured, tostring(sawGameOver), r(0x736)))
                    nextScene()
                end
            end
        end
    elseif phase == 'ending_gp_wait' then
        if (r(0x736) == 11 and r(0x726) == 0 and (frame - phaseStart) >= 12) or frame > phaseStart + 240 then
            clearSpells()
            w(0x0707, 0); w(0x0706, 0); w(0x0700, 0); w(0x0726, 0)
            w(0x0736, 0x08); w(0x076C, 0x03); w(0x0761, 0x00); w(0x0033, 0x00); w(0x0037, 0x00)
            phase = 'ending'; phaseStart = frame; captured = 0
            endingTick = 0; endingMaxStep = 0; endingSawFire = false
        end
    elseif phase == 'ending' then
        local s = r(0x0761)
        if s > endingMaxStep then endingMaxStep = s end
        if TAG ~= 'vanilla' and r(0x05F8) == 1 then endingSawFire = true end
        local visible = (r(0x076C) == 4 and r(0x0736) == 5 and r(0x0726) == 0)
        if visible then
            local wantCap = false
            if s <= 3 then
                wantCap = (endingTick >= 4 and (endingTick - 4) % 30 == 0)
            elseif s == 4 or s == 5 then
                wantCap = (endingTick % 16 == 0)
            elseif s >= 6 and s <= 8 then
                if TAG ~= 'vanilla' and r(0x05F8) == 1 then
                    wantCap = (endingTick % 3 == 0)
                else
                    wantCap = (endingTick % 9 == 0)
                end
            else
                wantCap = (endingTick % 2 == 0)
            end
            if wantCap and captured < 156 then
                dumpCrop('ending', 0, 24, 256, 208)
                captured = captured + 1
                if captured >= 156 then
                    logReport(string.format('ending frames=%d endStep=%d maxStep=%d sawFire=%s',
                        captured, s, endingMaxStep, tostring(endingSawFire)))
                    nextScene()
                end
            end
            endingTick = endingTick + 1
        end
        if captured < 156 and frame - phaseStart > 3500 then
            while captured < 156 do
                dumpCrop('ending', 0, 24, 256, 208)
                captured = captured + 1
            end
            logReport(string.format('ending frames=%d endStep=%d maxStep=%d sawFire=%s (fallback)',
                captured, s, endingMaxStep, tostring(endingSawFire)))
            nextScene()
        end
    end
end, emu.eventType.endFrame)
"""


def write_png_from_frames(raw_path: Path, out_png: Path, w: int, h: int, n_frames: int, max_cols: int = 12) -> None:
    data = raw_path.read_bytes()
    frame_bytes = w * h * 4
    if len(data) < frame_bytes * n_frames:
        raise ValueError(f"{raw_path} too short: {len(data)} < {frame_bytes * n_frames}")
    cols = min(n_frames, max_cols)
    grid_rows = (n_frames + cols - 1) // cols
    sheet_w = w * cols
    sheet_h = h * grid_rows
    row_bytes = w * 4
    blank_row = b"\x00" * row_bytes

    rows = bytearray()
    for gr in range(grid_rows):
        for y in range(h):
            rows.append(0)
            for gc in range(cols):
                f = gr * cols + gc
                if f < n_frames:
                    off = f * frame_bytes + y * row_bytes
                    rows.extend(data[off : off + row_bytes])
                else:
                    rows.extend(blank_row)

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
        + chunk(b"IHDR", struct.pack(">IIBBBBB", sheet_w, sheet_h, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows), 6))
        + chunk(b"IEND", b"")
    )


def run_capture(tag: str, rom: Path, selected: set[str]) -> None:
    CAP_DIR.mkdir(parents=True, exist_ok=True)
    for name in selected:
        raw_path = CAP_DIR / f"{tag}_{name}.rgba"
        if raw_path.exists():
            raw_path.unlink()
    lua_selected = "{" + ", ".join(f"[{json.dumps(name)}] = true" for name in sorted(selected)) + "}"
    lua_path = ROOT / "build" / f"fe_capture_{tag}.lua"
    script = (
        LUA_TEMPLATE.replace("__TAG__", json.dumps(tag))
        .replace("__CAP_DIR__", json.dumps(CAP_DIR.as_posix()))
        .replace("__SELECTED__", lua_selected)
    )
    lua_path.write_text(script, encoding="utf-8")
    rc = emulator_test.run(lua_path, rom, timeout=360)
    if rc != 0:
        raise SystemExit(f"Capture failed for {tag} ({rom}) with exit code {rc}")
    for name, w, h, n_frames, _fps in SCENES:
        if name not in selected:
            continue
        raw_path = CAP_DIR / f"{tag}_{name}.rgba"
        out_png = OUT_DIR / f"cap_{tag}_{name}.png"
        write_png_from_frames(raw_path, out_png, w, h, n_frames)
        print(f"Wrote {out_png} ({w}x{h} x {n_frames} frames)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture vanilla & barba FE preview strips")
    parser.add_argument("--tag", choices=["vanilla", "barba", "both"], default="both")
    parser.add_argument("--scenes", help="Comma-separated subset of scene names to capture")
    args = parser.parse_args()
    all_names = {name for name, _, _, _, _ in SCENES}
    if args.scenes:
        selected = {s.strip() for s in args.scenes.split(",") if s.strip()}
        unknown = selected - all_names
        if unknown:
            raise SystemExit(f"Unknown scene(s): {', '.join(sorted(unknown))}")
    else:
        selected = all_names
    if args.tag in ("vanilla", "both"):
        run_capture("vanilla", ROOT / "roms" / "z2.nes", selected)
    if args.tag in ("barba", "both"):
        run_capture("barba", ROOT / "build" / "barba.nes", selected)


if __name__ == "__main__":
    main()
