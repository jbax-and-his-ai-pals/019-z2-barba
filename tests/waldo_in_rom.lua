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
local waldoStart = 0
local returnStart = 0
local departure = ''
local report = assert(io.open(OUTPUT_DIR .. '/waldo-in-rom.txt', 'w'))
local errors = 0
local function check(cond, msg)
    report:write((cond and 'PASS ' or 'FAIL ') .. msg .. '\n')
    if not cond then errors = errors + 1 end
end

emu.addEventCallback(function()
    if phase == 'setup' then
        emu.setInput(newGameInput(frame), 0)
    elseif phase == 'enter' then
        emu.setInput({up = (frame >= 1180 and frame < 1185)}, 0)
    elseif phase == 'waldo' then
        local wf = frame - waldoStart
        emu.setInput({
            start = (wf == 263 or wf == 274 or wf == 285 or wf >= 1360),
            select = (wf == 270 or wf == 272 or wf >= 1360),
        }, 0)
    elseif phase == 'return' then
        local rf = frame - returnStart
        emu.setInput({up = (rf < 12)}, 0)
    end
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame = frame + 1
    if phase == 'setup' then
        if frame == 1000 then
            check(read(0x736) == 0x0B, 'New game reaches side-view play')
            write(0x707, 1); write(0x706, 0); write(0x769, 3); write(0x561, 1)
            write(0x701, 0); write(0x75C, 1); write(0x704, 0); write(0x736, 0)
            write(0x73D, 0); write(0x726, 1)
        elseif frame == 1150 then
            for slot = 0, 5 do write(0xB6 + slot, 0) end
            write(0x4D, 40); write(0x70, 0)
        elseif frame == 1170 then
            departure = location()
            phase = 'enter'
        end
    elseif phase == 'enter' then
        if frame > 1180 and read(0xFFFA) == 0x03 and read(0xFFFB) == 0xF6 then
            check(true, 'Rauru door switched in-ROM to Waldo ($FFFA=$F603)')
            phase = 'waldo'
            waldoStart = frame
        elseif frame > 1220 then
            check(false, 'Timed out waiting for Waldo PRG bank')
            report:write('RESULT FAIL\n'); report:close(); emu.stop(1)
        end
    elseif phase == 'waldo' then
        local wf = frame - waldoStart
        if wf == 1280 then
            screenshot('waldo-in-rom')
        end
        if read(0xFFFA) ~= 0x03 or read(0xFFFB) ~= 0xF6 then
            check(true, 'Waldo Start+Select returned in-ROM to Barba')
            phase = 'return'
            returnStart = frame
        elseif wf > 1500 then
            check(false, 'Timed out waiting for Waldo return to Barba')
            report:write('RESULT FAIL\n'); report:close(); emu.stop(1)
        end
    elseif phase == 'return' then
        local rf = frame - returnStart
        if rf == 30 then
            local arrival = location()
            check(arrival == departure, 'Exact Rauru return: ' .. arrival .. ' == ' .. departure)
            check(read(0xFFFA) ~= 0x03, 'Held Up did not reopen the portal')
            screenshot('barba-after-waldo')
            report:write(errors == 0 and 'RESULT PASS\n' or 'RESULT FAIL\n')
            report:close()
            emu.stop(errors == 0 and 0 or 1)
        end
    end
end, emu.eventType.endFrame)
