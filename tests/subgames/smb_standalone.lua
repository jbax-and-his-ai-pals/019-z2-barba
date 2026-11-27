-- Standalone verification of build/subgames/smb.nes (NES 2.0 Mapper 176).
local mem = emu.memType.nesMemory
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end

local report = assert(io.open(OUTPUT_DIR .. '/smb-standalone.txt', 'w'))
local errors = 0
local function check(cond, msg)
    report:write((cond and 'PASS ' or 'FAIL ') .. msg .. '\n')
    if not cond then errors = errors + 1 end
end

local frame = 0
local phase = 'boot'
local phaseStart = 0
local nmiCount = 0
local returnHits = 0
local winHits = 0
local restoreHits = 0
local triggerWin = false

emu.addMemoryCallback(function()
    if triggerWin then
        triggerWin = false
        emu.setState({['cpu.pc'] = 0x8487})
    end
end, emu.callbackType.exec, 0x8000, 0xFFFF)

local regWrites = {
    a001 = nil,
    f5ff0 = nil,
    f5ff1 = nil,
    f5ff2 = nil,
    r6 = nil,
    r7 = nil,
    mmc3Sel = nil,
    winFlag = nil,
}

local function finish()
    phase = 'done'
    report:write(errors == 0 and 'RESULT PASS\n' or 'RESULT FAIL\n')
    report:close()
    emu.stop(errors == 0 and 0 or 1)
end

-- Track SMB_NMI_HOOK ($7800), SMB_WIN_HOOK ($7850), SMB_RETURN ($7880), and restore_addr ($E000)
emu.addMemoryCallback(function()
    nmiCount = nmiCount + 1
end, emu.callbackType.exec, 0x7800)

emu.addMemoryCallback(function()
    winHits = winHits + 1
end, emu.callbackType.exec, 0x7850)

emu.addMemoryCallback(function()
    returnHits = returnHits + 1
    regWrites.a001 = nil
    regWrites.f5ff0 = nil
    regWrites.f5ff1 = nil
    regWrites.f5ff2 = nil
    regWrites.r6 = nil
    regWrites.r7 = nil
end, emu.callbackType.exec, 0x7880)

emu.addMemoryCallback(function(_, value)
    if returnHits > 0 then regWrites.a001 = value end
end, emu.callbackType.write, 0xA001)

emu.addMemoryCallback(function(_, value)
    if returnHits > 0 then regWrites.f5ff0 = value end
end, emu.callbackType.write, 0x5FF0)

emu.addMemoryCallback(function(_, value)
    if returnHits > 0 then regWrites.f5ff1 = value end
end, emu.callbackType.write, 0x5FF1)

emu.addMemoryCallback(function(_, value)
    if returnHits > 0 then regWrites.f5ff2 = value end
end, emu.callbackType.write, 0x5FF2)

emu.addMemoryCallback(function(_, value)
    if returnHits > 0 then regWrites.mmc3Sel = value end
end, emu.callbackType.write, 0x8000)

emu.addMemoryCallback(function(_, value)
    if returnHits > 0 then
        if regWrites.mmc3Sel == 0x06 then regWrites.r6 = value end
        if regWrites.mmc3Sel == 0x07 then regWrites.r7 = value end
    end
end, emu.callbackType.write, 0x8001)

emu.addMemoryCallback(function(_, value)
    regWrites.winFlag = value
end, emu.callbackType.write, 0x648F)

emu.addMemoryCallback(function()
    if phase == 'start_select' then
        restoreHits = restoreHits + 1
        check(regWrites.a001 == 0x80, 'Start+Select SMB_RETURN unlocked $5FF0-$5FF3 ($A001=$80)')
        check(regWrites.f5ff0 == 0x01 and regWrites.f5ff1 == 0x00 and regWrites.f5ff2 == 0x00,
              'Start+Select SMB_RETURN restored outer banks ($5FF0=$01, $5FF1=$00, $5FF2=$00)')
        check(regWrites.r6 == 0x0C and regWrites.r7 == 0x0D,
              'Start+Select SMB_RETURN restored MMC3 R6=$0C, R7=$0D')
        -- Re-enter SMB_BOOT ($7900) in WRAM bank 3 ($A3) to test SMB_WIN_HOOK cleanly
        write(0xA001, 0xA3)
        emu.setState({['cpu.pc'] = 0x7900})
        phase = 'win_wait'
        phaseStart = frame
    elseif phase == 'win' then
        restoreHits = restoreHits + 1
        check(winHits == 1, 'SMB_WIN_HOOK ($7850) executed once on World 8-4 ending')
        check(regWrites.winFlag == 0x4D, 'SMB_WIN_HOOK wrote win magic $4D to $648F')
        check(regWrites.a001 == 0x80 and regWrites.r6 == 0x0C and regWrites.r7 == 0x0D,
              'Win SMB_RETURN restored Barba Mapper 176 banks')
        finish()
    end
end, emu.callbackType.exec, 0xE000)

emu.addEventCallback(function()
    if phase == 'debounce' and frame >= 15 and frame < 22 then
        emu.setInput({start = true, select = true}, 0)
    elseif phase == 'start_select' then
        emu.setInput({start = true, select = true}, 0)
    else
        emu.setInput({}, 0)
    end
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame = frame + 1
    if phase == 'boot' then
        if frame == 5 then
            check(read(0xFFFA) == 0x00 and read(0xFFFB) == 0x78, 'NMI vector points to SMB_NMI_HOOK ($7800)')
            check(read(0x8000) == 0x78 and read(0x8001) == 0xD8, 'SMB PRG mapped at $8000 (SEI; CLD)')
            phase = 'debounce'
            phaseStart = frame
        end
    elseif phase == 'debounce' then
        if frame == 25 then
            check(returnHits == 0, 'Start+Select ignored during 60-frame debounce')
        end
        if read(0x7FFF) == 0x3C and nmiCount >= 60 and read(0x09) > 5 then
            check(true, 'SMB_NMI_HOOK ticked $7FFF to $3C and SMB frame counter ($09) advanced')
            phase = 'start_select'
            phaseStart = frame
        elseif frame - phaseStart > 180 then
            check(false, 'Timed out waiting for NMI debounce $7FFF == $3C')
            finish()
        end
    elseif phase == 'start_select' then
        if frame - phaseStart > 60 then
            check(false, 'Timed out waiting for Start+Select SMB_RETURN')
            finish()
        end
    elseif phase == 'win_wait' then
        if frame - phaseStart == 30 then
            -- Trigger World 8-4 VictoryMode ($8487 -> SMB_WIN_HOOK) via exec callback
            triggerWin = true
            phase = 'win'
            phaseStart = frame
        end
    elseif phase == 'win' then
        if frame - phaseStart > 60 then
            local st = emu.getState()
            check(false, string.format('Timed out waiting for SMB_WIN_HOOK (winHits=%d restore=%d pc=$%04X)', winHits, restoreHits, st['cpu.pc'] or 0))
            finish()
        end
    end
end, emu.eventType.endFrame)
