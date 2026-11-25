-- Single-ROM Ruto <-> Friday the 13th round trip (NES 2.0 Mapper 176).
dofile(TEST_DIR .. '/newgame.lua')
local mem = emu.memType.nesMemory
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end

local function location()
    return string.format('world=%02X room=%02X page=%02X x=%02X y=%02X scroll=%02X%02X hp=%02X magic=%02X',
        read(0x707), read(0x561), read(0x3B), read(0x4D), read(0x29),
        read(0x72A), read(0x72C), read(0x774), read(0x773))
end

local frame = 0
local phase = 'setup'
local enterStart = 0
local f13Start = 0
local returnStart = 0
local departure = ''
local wipeInStarts = 0
local chrSwitches = 0
local meltStarts = 0
local f13WipeScroll = {}
local meltScroll = {}
local wipeScroll = {}
local report = assert(io.open(OUTPUT_DIR .. '/f13-in-rom.txt', 'w'))
local errors = 0
local function check(cond, msg)
    report:write((cond and 'PASS ' or 'FAIL ') .. msg .. '\n')
    if not cond then errors = errors + 1 end
end

local function finish()
    phase = 'done'
    report:write(errors == 0 and 'RESULT PASS\n' or 'RESULT FAIL\n')
    report:close()
    emu.stop(errors == 0 and 0 or 1)
end

local function countValues(values)
    local count = 0
    for _ in pairs(values) do count = count + 1 end
    return count
end

emu.addMemoryCallback(function()
    if phase == 'f13' then chrSwitches = chrSwitches + 1 end
end, emu.callbackType.exec, 0x7800)

emu.addMemoryCallback(function()
    if phase == 'f13' then wipeInStarts = wipeInStarts + 1 end
end, emu.callbackType.exec, 0x7860)

emu.addMemoryCallback(function()
    if phase == 'f13' then meltStarts = meltStarts + 1 end
end, emu.callbackType.exec, 0x7960)

emu.addMemoryCallback(function(_, value)
    if phase == 'f13' and meltStarts > 0 then
        meltScroll[value] = true
    elseif phase == 'f13' and wipeInStarts > 0 and frame - f13Start < 50 then
        f13WipeScroll[value] = true
    elseif phase == 'return' and frame - returnStart < 40 then
        wipeScroll[value] = true
    end
end, emu.callbackType.write, 0x2005)

emu.addEventCallback(function()
    if phase == 'setup' then
        if frame < 1000 then
            emu.setInput(newGameInput(frame), 0)
        elseif frame >= 1100 and (read(0x3B) ~= 0 or read(0x4D) < 0x94) then
            emu.setInput({right = true}, 0)
        else
            emu.setInput({}, 0)
        end
    elseif phase == 'enter' then
        local ef = frame - enterStart
        emu.setInput({
            up = (ef >= 10 and ef < 15),
            b = (ef >= 250 and ef < 254),
        }, 0)
    elseif phase == 'f13' then
        local ff = frame - f13Start
        emu.setInput({
            start = (ff >= 100 and ff < 105) or (ff >= 240),
            select = (ff >= 240),
        }, 0)
    elseif phase == 'return' then
        local rf = frame - returnStart
        emu.setInput({up = (rf < 12), b = (rf >= 250 and rf < 254)}, 0)
    end
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame = frame + 1
    if phase == 'setup' then
        if frame == 1000 then
            check(read(0x736) == 0x0B, 'New game reaches side-view play')
            write(0x707, 1); write(0x706, 0); write(0x056B, 1); write(0x769, 3); write(0x561, 5)
            write(0x701, 0); write(0x75C, 0); write(0x704, 0); write(0x736, 0)
            write(0x73D, 0); write(0x726, 1)
        elseif frame > 1100 and read(0x3B) == 0 and read(0x4D) >= 0x94 then
            for slot = 0, 5 do write(0xB6 + slot, 0) end
            write(0x4D, 0x95); write(0x70, 0)
            departure = location()
            phase = 'enter'
            enterStart = frame
        end
    elseif phase == 'enter' then
        local ef = frame - enterStart
        if ef == 15 then
            check(read(0x74C) == 0x02, 'Ruto door opened enter message box ($074C=2)')
            check(read(0xFFFA) ~= 0x40, 'Message box runs before wavy transition to F13')
        elseif ef == 240 then
            check(read(0x524) == 0x09 and read(0x766) == 0x01, 'Enter message box finished typing and awaits B')
        elseif ef > 250 and read(0xFFFA) == 0x40 and read(0xFFFB) == 0x78 then
            check(true, 'Ruto door switched in-ROM to Friday the 13th ($FFFA=$7840)')
            phase = 'f13'
            f13Start = frame
        elseif ef > 340 then
            local st = emu.getState()
            check(false, string.format('Timed out waiting for F13 PRG bank (pc=%04X fffa=%02X%02X)', st['cpu.pc'], read(0xFFFB), read(0xFFFA)))
            finish()
        end
    elseif phase == 'f13' then
        local ff = frame - f13Start
        if ff == 80 then
            check(wipeInStarts == 1, 'F13 title screen ran 30-frame wave-in')
            check(countValues(f13WipeScroll) >= 5, 'F13 title wave-in varied horizontal scroll')
            check(read(0x2A) == 0x1E, 'F13 title rendering enabled ($2A=$1E)')
        elseif ff == 200 then
            check(chrSwitches >= 1, 'F13 CHR bankswitching ran via MMC3 (' .. chrSwitches .. ' calls)')
        end
        if read(0xFFFA) ~= 0x40 or read(0xFFFB) ~= 0x78 then
            check(true, 'F13 Start+Select returned in-ROM to Barba')
            check(meltStarts == 1, 'Wave-out started once while Start+Select was held')
            check(countValues(meltScroll) >= 5, 'Wave-out varied horizontal scroll')
            phase = 'return'
            returnStart = frame
        elseif ff > 500 then
            check(false, 'Timed out waiting for F13 return to Barba')
            finish()
        end
    elseif phase == 'return' then
        local rf = frame - returnStart
        if rf == 50 then
            check(countValues(wipeScroll) >= 5, 'Wave-in varied horizontal scroll')
            local arrival = location()
            check(arrival == departure, 'Exact Ruto return: ' .. arrival .. ' == ' .. departure)
            check(read(0xFFFA) ~= 0x40, 'Held Up did not reopen the portal')
            check(read(0x74C) == 0x02, 'Return opened villager-style message box ($074C=2)')
        elseif rf == 240 then
            check(read(0x524) == 0x09 and read(0x766) == 0x01, 'Message box finished typing and awaits B')
        elseif rf == 280 then
            check(read(0x74C) == 0x00 and read(0x524) == 0x00, 'Pressing B dismissed the return message box')
            finish()
        end
    end
end, emu.eventType.endFrame)
