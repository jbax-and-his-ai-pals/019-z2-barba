-- Single-ROM Rauru <-> Where's Waldo? round trip (NES 2.0 Mapper 176).
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
local waldoStart = 0
local returnStart = 0
local departure = ''
local meltStarts = 0
local meltScroll = {}
local wipeScroll = {}
local report = assert(io.open(OUTPUT_DIR .. '/waldo-in-rom.txt', 'w'))
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
    if phase == 'waldo' then meltStarts = meltStarts + 1 end
end, emu.callbackType.exec, 0xCB10)

emu.addMemoryCallback(function(_, value)
    if phase == 'waldo' and meltStarts > 0 then
        meltScroll[value] = true
    elseif phase == 'return' and frame - returnStart < 40 then
        wipeScroll[value] = true
    end
end, emu.callbackType.write, 0x2005)

emu.addEventCallback(function()
    if phase == 'setup' then
        if frame < 1000 then
            emu.setInput(newGameInput(frame), 0)
        elseif frame >= 1100 and (read(0x3B) < 1 or read(0x4D) < 0x26) then
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
    elseif phase == 'waldo' then
        local wf = frame - waldoStart
        emu.setInput({
            start = (wf == 263 or wf == 274 or wf == 285 or wf >= 1360),
            select = (wf == 270 or wf == 272 or wf >= 1360),
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
            write(0x707, 1); write(0x706, 0); write(0x769, 3); write(0x561, 1)
            write(0x701, 0); write(0x75C, 0); write(0x704, 0); write(0x736, 0)
            write(0x73D, 0); write(0x726, 1)
        elseif frame > 1100 and read(0x3B) == 1 and read(0x4D) >= 0x26 then
            for slot = 0, 5 do write(0xB6 + slot, 0) end
            write(0x4D, 40); write(0x70, 0)
            departure = location()
            phase = 'enter'
            enterStart = frame
        end
    elseif phase == 'enter' then
        local ef = frame - enterStart
        if ef == 15 then
            check(read(0x74C) == 0x02, 'Door opened enter message box ($074C=2)')
            check(read(0xFFFA) ~= 0x03, 'Message box runs before wavy transition to Waldo')
        elseif ef == 240 then
            check(read(0x524) == 0x09 and read(0x766) == 0x01, 'Enter message box finished typing and awaits B')
            screenshot('waldo-enter-msg')
        elseif ef > 250 and read(0xFFFA) == 0x03 and read(0xFFFB) == 0xF6 then
            check(true, 'Rauru door switched in-ROM to Waldo ($FFFA=$F603)')
            phase = 'waldo'
            waldoStart = frame
        elseif ef > 320 then
            check(false, 'Timed out waiting for Waldo PRG bank')
            finish()
        end
    elseif phase == 'waldo' then
        local wf = frame - waldoStart
        if wf == 1280 then
            screenshot('waldo-in-rom')
        end
        if read(0xFFFA) ~= 0x03 or read(0xFFFB) ~= 0xF6 then
            check(true, 'Waldo Start+Select returned in-ROM to Barba')
            check(meltStarts == 1, 'Wave-out started once while Start+Select was held')
            check(countValues(meltScroll) >= 5, 'Wave-out varied horizontal scroll')
            phase = 'return'
            returnStart = frame
        elseif wf > 1500 then
            check(false, 'Timed out waiting for Waldo return to Barba')
            finish()
        end
    elseif phase == 'return' then
        local rf = frame - returnStart
        if rf == 50 then
            check(countValues(wipeScroll) >= 5, 'Wave-in varied horizontal scroll')
            local arrival = location()
            check(arrival == departure, 'Exact Rauru return: ' .. arrival .. ' == ' .. departure)
            check(read(0xFFFA) ~= 0x03, 'Held Up did not reopen the portal')
            check(read(0x74C) == 0x02, 'Return opened villager-style message box ($074C=2)')
        elseif rf == 240 then
            check(read(0x524) == 0x09 and read(0x766) == 0x01, 'Message box finished typing and awaits B')
            screenshot('barba-after-waldo')
        elseif rf == 280 then
            check(read(0x74C) == 0x00 and read(0x524) == 0x00, 'Pressing B dismissed the return message box')
            finish()
        end
    end
end, emu.eventType.endFrame)
