-- Single-ROM Rauru -> Waldo Moon Ending -> wave out -> wave in -> Rauru return.
dofile(TEST_DIR .. '/newgame.lua')
local mem = emu.memType.nesMemory
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end

local frame = 0
local phase = 'setup'
local enterStart = 0
local waldoStart = 0
local returnStart = 0
local triggeredMoon = false
local sawHop = false
local sawMeltOut = false
local meltScrollX = {}
local wipeScrollX = {}
local departure = ''
local report = assert(io.open(OUTPUT_DIR .. '/waldo-moon-return.txt', 'w'))
local errors = 0
local function check(cond, msg)
    report:write((cond and 'PASS ' or 'FAIL ') .. msg .. '\n')
    if not cond then errors = errors + 1 end
end

local function location()
    return string.format('world=%02X room=%02X page=%02X x=%02X y=%02X scroll=%02X%02X hp=%02X magic=%02X',
        read(0x707), read(0x561), read(0x3B), read(0x4D), read(0x29),
        read(0x72A), read(0x72C), read(0x774), read(0x773))
end

emu.addMemoryCallback(function()
    if phase == 'waldo' and not triggeredMoon and (frame - waldoStart) >= 60 then
        triggeredMoon = true
        emu.setState({['cpu.pc'] = 0xE1B4})
    end
end, emu.callbackType.exec, 0x8000, 0xFFFF)

emu.addMemoryCallback(function()
    if phase == 'waldo' and triggeredMoon and not sawHop then
        sawHop = true
        check((frame - waldoStart) > 400, 'Moon ending did not cut off early at 360 frames')
    end
end, emu.callbackType.exec, 0xA168)

emu.addMemoryCallback(function()
    if phase == 'waldo' and triggeredMoon and not sawMeltOut then
        sawMeltOut = true
        check(sawHop, 'Reached end of Moon scene ($A1B3 -> $CB10) after Barba hop')
    end
end, emu.callbackType.exec, 0xCB10)

emu.addMemoryCallback(function(_, value)
    if phase == 'waldo' and sawMeltOut then
        meltScrollX[value] = true
    elseif phase == 'return' and (frame - returnStart) < 31 then
        wipeScrollX[value] = true
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
    elseif phase == 'return' then
        local rf = frame - returnStart
        emu.setInput({b = (rf >= 250 and rf < 254)}, 0)
    else
        emu.setInput({}, 0)
    end
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame = frame + 1
    if phase == 'setup' then
        if frame == 1000 then
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
        if ef > 250 and read(0xFFFA) == 0x03 and read(0xFFFB) == 0xF6 then
            phase = 'waldo'
            waldoStart = frame
        elseif ef > 350 then
            check(false, 'Timed out entering Waldo')
            report:write('RESULT FAIL\n'); report:close(); emu.stop(1)
        end
    elseif phase == 'waldo' then
        local wf = frame - waldoStart
        if read(0xFFFA) ~= 0x03 or read(0xFFFB) ~= 0xF6 then
            local meltCount = 0
            for _ in pairs(meltScrollX) do meltCount = meltCount + 1 end
            check(sawMeltOut, 'WaldoMoonReturn ran WaldoMeltOut ($CB10) before restoring Barba')
            check(meltCount >= 5, 'Wave-out varied horizontal scroll across scanlines (' .. meltCount .. ' values)')
            phase = 'return'
            returnStart = frame
        elseif wf > 2200 then
            check(false, 'Timed out waiting for Moon ending transition')
            report:write('RESULT FAIL\n'); report:close(); emu.stop(1)
        end
    elseif phase == 'return' then
        local rf = frame - returnStart
        if rf == 35 then
            local wipeCount = 0
            for _ in pairs(wipeScrollX) do wipeCount = wipeCount + 1 end
            check(wipeCount >= 5, 'Wave-in varied horizontal scroll across scanlines (' .. wipeCount .. ' values)')
            local arrival = location()
            check(arrival == departure, 'Exact Rauru return: ' .. arrival .. ' == ' .. departure)
            check(read(0x74C) == 0x02, 'Return opened villager-style message box ($074C=2)')
        elseif rf == 240 then
            check(read(0x524) == 0x09 and read(0x766) == 0x01, 'Message box finished typing and awaits B')
        elseif rf == 280 then
            check(read(0x74C) == 0x00 and read(0x524) == 0x00, 'Pressing B dismissed the return message box')
            report:write(errors == 0 and 'RESULT PASS\n' or 'RESULT FAIL\n')
            report:close()
            emu.stop(errors == 0 and 0 or 1)
        end
    end
end, emu.eventType.endFrame)
