-- Automatic return from Friday the 13th after beating Day 3 ($8E4A).
dofile(TEST_DIR .. '/newgame.lua')
local mem = emu.memType.nesMemory
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end

local frame = 0
local phase = 'setup'
local enterStart = 0
local f13Start = 0
local returnStart = 0
local triggerWin = false
local triggered = false
local meltStarts = 0
local meltScroll = {}
local wipeScroll = {}
local report = assert(io.open(OUTPUT_DIR .. '/f13-win-return.txt', 'w'))
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
    if triggerWin then
        triggerWin = false
        write(0x0522, 2)
        emu.setState({['cpu.pc'] = 0x8E40})
    end
end, emu.callbackType.exec, 0x8000, 0xFFFF)

emu.addMemoryCallback(function()
    if phase == 'f13' then meltStarts = meltStarts + 1 end
end, emu.callbackType.exec, 0x796C)

emu.addMemoryCallback(function(_, value)
    if phase == 'f13' and meltStarts > 0 then
        meltScroll[value] = true
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
        emu.setInput({start = (ff >= 100 and ff < 105)}, 0)
    elseif phase == 'return' then
        local rf = frame - returnStart
        emu.setInput({b = (rf >= 250 and rf < 254)}, 0)
    end
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame = frame + 1
    if phase == 'setup' then
        if frame == 1000 then
            write(0x707, 1); write(0x706, 0); write(0x769, 3); write(0x561, 5)
            write(0x701, 0); write(0x75C, 0); write(0x704, 0); write(0x736, 0)
            write(0x73D, 0); write(0x726, 1)
        elseif frame > 1100 and read(0x3B) == 0 and read(0x4D) >= 0x94 then
            for slot = 0, 5 do write(0xB6 + slot, 0) end
            write(0x4D, 0x95); write(0x70, 0)
            phase = 'enter'
            enterStart = frame
        end
    elseif phase == 'enter' then
        local ef = frame - enterStart
        if ef > 250 and read(0xFFFA) == 0x52 and read(0xFFFB) == 0x78 then
            phase = 'f13'
            f13Start = frame
        elseif ef > 340 then
            check(false, 'Timed out entering F13')
            finish()
        end
    elseif phase == 'f13' then
        local ff = frame - f13Start
        if ff == 160 and not triggered then
            triggered = true
            -- Simulate beating Day 3 ($0522 = 2 -> $8E40 increments to 3 -> hits $8E4A -> F13Return)
            triggerWin = true
        end
        if read(0xFFFA) ~= 0x52 or read(0xFFFB) ~= 0x78 then
            check(true, 'Beating Day 3 ($8E4A) automatically returned to Barba')
            check(meltStarts == 1, 'Wave-out started once on Day 3 victory')
            check(countValues(meltScroll) >= 5, 'Wave-out varied horizontal scroll')
            phase = 'return'
            returnStart = frame
        elseif ff > 350 then
            check(false, 'Timed out waiting for automatic Day 3 victory return')
            finish()
        end
    elseif phase == 'return' then
        local rf = frame - returnStart
        if rf == 50 then
            check(countValues(wipeScroll) >= 5, 'Wave-in varied horizontal scroll')
            check(read(0x707) == 0x01 and read(0x561) == 0x05 and read(0x4D) == 0x95, 'Returned to exact Ruto location')
            check(read(0x74C) == 0x02, 'Return opened villager-style message box ($074C=2)')
        elseif rf == 240 then
            check(read(0x524) == 0x09 and read(0x766) == 0x01, 'Return message box finished typing and awaits B')
        elseif rf == 280 then
            check(read(0x74C) == 0x00 and read(0x524) == 0x00, 'Pressing B dismissed the return message box')
            check(read(0x63B1) == 0x01, string.format('Day 3 victory set F13 reward $63B1=$01 (got $%02X)', read(0x63B1)))
            finish()
        end
    end
end, emu.eventType.endFrame)
