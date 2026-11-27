-- Wheel of Barba (Round 2) end-to-end gameplay verification.
-- Verifies:
--   1. Menu board shows "WHEEL OF BARBA EDITION", Stage shows Barba (no Link).
--   2. Main Board loads a Zelda II / Barba Universe puzzle & category, and DARK LINK / BARBA contestants.
--   3. Barba walks fast (4 px/frame) to a letter target ($B3) and enters the unveil state ($B0=$09).
--   3. Big Spin ($A660 -> $FC6F) and Puzzle Solve ($9750 -> $FC69) trigger Barba DMC roar ($4012=$88, $4013=$88, $4015=$1F).
--   4. Relocated Bonus Prize copy ($E130 -> $FC84) swaps R6=2 and restores R6=$1C cleanly.
--   5. Start+Select exits to $80F0 without reward, and Bonus Win ($C988 -> $78A0) sets $648E=$57.

local results = {}
local done = false
local frame = 0
local inp = {}

local function check(cond, msg)
    local tag = cond and 'PASS' or 'FAIL'
    table.insert(results, tag .. ' ' .. msg)
end

local function finish()
    if done then return end
    done = true
    local allOk = true
    for _, line in ipairs(results) do
        if line:sub(1, 4) == 'FAIL' then allOk = false break end
    end
    table.insert(results, allOk and 'RESULT PASS' or 'RESULT FAIL')
    local f = assert(io.open(OUTPUT_DIR .. '/wheel_barba_gameplay.txt', 'w'))
    f:write(table.concat(results, '\n') .. '\n')
    f:close()
    local stop = emu.exit or emu.stop
    stop(allOk and 0 or 1)
end

local function read(addr)
    return emu.read(addr, emu.memType.nesMemory)
end

local function write(addr, val)
    emu.write(addr, val, emu.memType.nesMemory)
end

local function readAsciiRange(addr, len)
    local t = {}
    for i = 0, len - 1 do
        local b = read(addr + i) & 0x7F
        if b >= 0x20 and b <= 0x5A then
            t[#t + 1] = string.char(b)
        else
            t[#t + 1] = ' '
        end
    end
    return table.concat(t)
end

local function readContestantName(baseAddr)
    local t = {}
    for i = 0, 9 do
        local b = read(baseAddr + i)
        if b == 0xC5 or b == 0xD4 or b == 0x00 then
            t[#t + 1] = ' '
        elseif b >= 0xC6 and b <= 0xDF then
            t[#t + 1] = string.char(string.byte('A') + b - 0xC6)
        elseif b >= 0xE5 and b <= 0xFE then
            t[#t + 1] = string.char(string.byte('A') + b - 0xE5)
        else
            t[#t + 1] = '?'
        end
    end
    return table.concat(t)
end

local function savePng(name)
    local data = emu.takeScreenshot()
    local f = io.open(OUTPUT_DIR .. '/' .. name, 'wb')
    if f then f:write(data); f:close() end
end

local playRoarHits = 0
local solveRoarHits = 0
local spinRoarHits = 0
local prizeCopyHits = 0
local restoreHits = 0
local winHookHits = 0
local dmcWrites = {}

-- Guard against Bank 3's original NMI ($FC48) by verifying Bank 0 ($7FFD & 3 == 0)
emu.addMemoryCallback(function()
    if (read(0x7FFD) & 0x03) == 0 then playRoarHits = playRoarHits + 1 end
end, emu.callbackType.exec, 0xFC48)
emu.addMemoryCallback(function()
    if (read(0x7FFD) & 0x03) == 0 then solveRoarHits = solveRoarHits + 1 end
end, emu.callbackType.exec, 0xFC69)
emu.addMemoryCallback(function()
    if (read(0x7FFD) & 0x03) == 0 then spinRoarHits = spinRoarHits + 1 end
end, emu.callbackType.exec, 0xFC6F)
emu.addMemoryCallback(function()
    if (read(0x7FFD) & 0x03) == 0 then prizeCopyHits = prizeCopyHits + 1 end
end, emu.callbackType.exec, 0xFC84)
emu.addMemoryCallback(function() winHookHits = winHookHits + 1 end, emu.callbackType.exec, 0x78A0)
emu.addMemoryCallback(function() restoreHits = restoreHits + 1 end, emu.callbackType.exec, 0x80F0)

for _, reg in ipairs({0x4010, 0x4011, 0x4012, 0x4013, 0x4015}) do
    emu.addMemoryCallback(function(addr, val)
        dmcWrites[addr] = val
    end, emu.callbackType.write, reg)
end

local pendingTest = nil
local triggerBoot = false
local triggerWin = false
local captureTurnBanner = false
local turnBannerText = nil

emu.addMemoryCallback(function()
    if captureTurnBanner and (read(0x7FFD) & 0x03) == 0 then
        captureTurnBanner = false
        local t = {}
        for i = 5, 20 do
            local b = read(0x0507 + i)
            if b == 0xD4 then
                t[#t + 1] = ' '
            elseif b == 0xD5 then
                t[#t + 1] = "'"
            elseif b >= 0xE5 and b <= 0xFE then
                t[#t + 1] = string.char(string.byte('A') + b - 0xE5)
            else
                t[#t + 1] = string.format('[%02X]', b)
            end
        end
        turnBannerText = table.concat(t)
        emu.setState({['cpu.pc'] = 0x927A})
    end
end, emu.callbackType.exec, 0x9949)

-- Execute subroutine tests safely at $927A (where Bank 0 is active and SP=$FF).
emu.addMemoryCallback(function()
    if pendingTest == 'turn_banner' then
        pendingTest = nil
        captureTurnBanner = true
        write(0x0006, 0x02) -- CPU1 = DARK LINK
        emu.setState({['cpu.pc'] = 0x9928})
    elseif pendingTest == 'spin_roar' then
        pendingTest = nil
        -- Run the real 0:A660 Big Spin hook (calls JSR $FC6F then jumps to $8BAB idle loop)
        write(0x047B, 0xEA) -- 'F' in FREE SPIN buffer read by $AAC9
        write(0x006A, 0x24)
        emu.setState({['cpu.pc'] = 0xA660})
    elseif pendingTest == 'solve_roar' then
        pendingTest = nil
        write(0x0024, 0x05)
        write(0x01FF, 0x92)
        write(0x01FE, 0x79)
        emu.setState({['cpu.sp'] = 0xFD, ['cpu.pc'] = 0x9750})
    elseif pendingTest == 'prize_copy' then
        pendingTest = nil
        write(0x00CA, 0x00)
        write(0x01FF, 0x92)
        write(0x01FE, 0x79)
        emu.setState({['cpu.sp'] = 0xFD, ['cpu.pc'] = 0xE130})
    end
end, emu.callbackType.exec, 0x927A)

emu.addMemoryCallback(function()
    if triggerBoot then
        triggerBoot = false
        write(0xA001, 0xA3)
        emu.setState({['cpu.pc'] = 0x7AE0})
    elseif triggerWin and (read(0x7FFD) & 0x03) == 0 then
        triggerWin = false
        write(0x00C9, 0x80)
        emu.setState({['cpu.pc'] = 0xC988})
    end
end, emu.callbackType.exec, 0x8000, 0xFFFF)

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

local phase = 'nav_to_board'
local phaseStart = 0
local checkedMenu = false
local checkedBoard = false

emu.addEventCallback(function()
    if done then return end
    frame = frame + 1
    if frame > 4000 then
        check(false, string.format('Global timeout in phase=%s at frame=%d (nmi=$%04X $52=%02X)',
            phase, frame, read(0x000E) + read(0x000F) * 256, read(0x0052)))
        finish()
        return
    end

    local nmi = read(0x000E) + read(0x000F) * 256
    local s52 = read(0x0052)

    if phase == 'nav_to_board' then
        inp = {}
        if nmi ~= 0xB67C and nmi ~= 0xC216 and nmi ~= 0x917C then
            if frame >= 700 and (frame % 30) < 2 then inp = {start = true} end
        elseif nmi == 0xB67C then
            if s52 == 0x00 and not checkedMenu then
                -- Wait ~25 frames for menu CHR/OAM to settle before pressing A
                if phaseStart == 0 then phaseStart = frame end
                if frame >= phaseStart + 25 then
                    checkedMenu = true
                    local menuText = readAsciiRange(0x03D1, 64)
                    check(menuText:find('WHEEL', 1, true) ~= nil and menuText:find('BARBA', 1, true) ~= nil,
                        'Menu board contains WHEEL OF BARBA (' .. menuText:gsub('%s+', ' ') .. ')')
                    savePng('wheel_barba_menu.png')
                end
            elseif s52 == 0x00 or s52 == 0x01 or s52 == 0x02 then
                if (frame % 30) < 2 then inp = {a = true} end
            elseif s52 == 0x03 or s52 == 0x04 or s52 == 0x05 then
                -- Cursor starts at 'A' (0); 1x left wraps to END (or if on '<-', another left/right finds END).
                local step = math.floor(frame / 16) % 4
                local inWindow = (frame % 16) < 2
                if inWindow then
                    if step == 0 then inp = {a = true}
                    elseif step == 1 then inp = {left = true}
                    elseif step == 2 then inp = {a = true}
                    else inp = {left = true} end
                end
            end
        elseif nmi == 0x917C then
            phase = 'verify_board'
            phaseStart = frame
        end

    elseif phase == 'verify_board' then
        inp = {}
        if frame == phaseStart + 40 and not checkedBoard then
            checkedBoard = true
            local puzText = readAsciiRange(0x03D1, 64)
            local catId = read(0x008C)
            check(catId < 10, string.format('Puzzle category valid ($8C=%d)', catId))
            local clean = puzText:gsub('%s+', ' ')
            check(#clean > 3 and clean:find('MONKEY', 1, true) == nil, 'Zelda II / Barba puzzle loaded: "' .. clean .. '"')

            local c1 = readContestantName(0x041C)
            local c2 = readContestantName(0x0426)
            check(c1:find('DARK LINK', 1, true) ~= nil, 'CPU1 is DARK LINK (got "' .. c1 .. '")')
            check(c2:find('BARBA', 1, true) ~= nil, 'CPU2 is BARBA (got "' .. c2 .. '")')

            local barbaSprites, linkSprites = 0, 0
            for i = 0, 63 do
                local y = read(0x0200 + i * 4)
                if y < 0xEF then
                    local t = read(0x0200 + i * 4 + 1)
                    local a = read(0x0200 + i * 4 + 2) & 0x03
                    if a == 0 and ((t >= 0x6C and t <= 0x83) or (t >= 0x8C and t <= 0xA3)) then
                        barbaSprites = barbaSprites + 1
                    elseif a == 1 and ((t >= 0x7E and t <= 0x85) or (t >= 0x9E and t <= 0xA5)) then
                        linkSprites = linkSprites + 1
                    end
                end
            end
            check(barbaSprites == 24, 'Barba full-body OAM sprites present (' .. barbaSprites .. ')')
            check(linkSprites == 0, 'Villainous Link removed (0 OAM sprites, got ' .. linkSprites .. ')')

            local chrSum = 0
            for off = 0, 287 do
                chrSum = chrSum + emu.read(0x16C0 + off, emu.memType.nesPpuDebug)
            end
            check(chrSum > 0, 'Barba CHR-RAM tiles loaded in $16C0 (sum=' .. chrSum .. ')')
            check(read(0x7FFB) == 1, string.format('Main Board Vertical-mirroring NT XOR active ($7FFB=%02X)', read(0x7FFB)))

            savePng('wheel_barba_board.png')
            -- Trigger Barba Vanna walk to target X=$A0 and unveil row 1 ($B4=$09)
            write(0x009D, 0x12)
            write(0x00AC, 0x00)
            write(0x00B3, 0xA0)
            write(0x00B4, 0x09)
            write(0x00B0, 0x05)
            phase = 'test_barba_walk'
            phaseStart = frame
        end

    elseif phase == 'test_barba_walk' then
        local x = read(0x0004)
        local b0 = read(0x00B0)
        if x == 0xA0 and b0 == 0x09 then
            local elapsed = frame - phaseStart
            check(elapsed <= 85, string.format('Barba walked to $A0 and entered unveil $B0=$09 in %d frames', elapsed))
            phase = 'test_turn_banner'
            phaseStart = frame
            pendingTest = 'turn_banner'
        elseif frame - phaseStart > 95 then
            check(false, string.format('Barba walk/unveil timed out ($04=$%02X $B0=$%02X $AB=$%02X)', x, b0, read(0x00AB)))
            phase = 'test_turn_banner'
            phaseStart = frame
            pendingTest = 'turn_banner'
        end

    elseif phase == 'test_turn_banner' then
        if frame - phaseStart >= 5 then
            check(turnBannerText == "DARK LINK'S TURN",
                'Turn banner places possessive after full name (got "' .. tostring(turnBannerText) .. '")')
            phase = 'test_spin_roar'
            phaseStart = frame
            pendingTest = 'spin_roar'
        end

    elseif phase == 'test_spin_roar' then
        if frame - phaseStart >= 5 then
            check(spinRoarHits >= 1 and playRoarHits >= 1,
                string.format('Big Spin triggered WHEEL_PLAY_ROAR (spin=%d, roar=%d)', spinRoarHits, playRoarHits))
            check(dmcWrites[0x4012] == 0x88 and dmcWrites[0x4013] == 0x88 and dmcWrites[0x4015] == 0x1F,
                string.format('DMC registers programmed ($4012=$%02X, $4013=$%02X, $4015=$%02X)',
                    dmcWrites[0x4012] or 0, dmcWrites[0x4013] or 0, dmcWrites[0x4015] or 0))
            dmcWrites = {}
            playRoarHits = 0
            phase = 'test_solve_roar'
            phaseStart = frame
            pendingTest = 'solve_roar'
        end

    elseif phase == 'test_solve_roar' then
        if frame - phaseStart >= 5 then
            check(solveRoarHits >= 1 and playRoarHits >= 1,
                string.format('Puzzle Solve triggered WHEEL_PLAY_ROAR (solve=%d, roar=%d)', solveRoarHits, playRoarHits))
            check(dmcWrites[0x4012] == 0x88 and dmcWrites[0x4015] == 0x1F,
                string.format('Solve DMC playback started ($4012=$%02X, $4015=$%02X)',
                    dmcWrites[0x4012] or 0, dmcWrites[0x4015] or 0))
            phase = 'test_prize_copy'
            phaseStart = frame
            pendingTest = 'prize_copy'
        end

    elseif phase == 'test_prize_copy' then
        if frame - phaseStart >= 5 then
            check(prizeCopyHits >= 1, 'Relocated Bonus Prize copy ($E130 -> $FC84) executed (' .. prizeCopyHits .. ')')
            check(read(0x8030) ~= 0xFF, string.format('MMC3 R6 restored after prize copy ($8030=$%02X)', read(0x8030)))
            phase = 'test_start_select'
            phaseStart = frame
        end

    elseif phase == 'test_start_select' then
        inp = {start = true, select = true}
        if restoreHits >= 1 then
            check(true, 'Start+Select exited cleanly to $80F0')
            check(read(0x648E) ~= 0x57, string.format('Start+Select did not set win flag ($648E=$%02X)', read(0x648E)))
            inp = {}
            restoreHits = 0
            winHookHits = 0
            triggerBoot = true
            phase = 'wait_win_reboot'
            phaseStart = frame
        elseif frame - phaseStart > 20 then
            check(false, 'Start+Select did not reach $80F0 within 20 frames')
            finish()
        end

    elseif phase == 'wait_win_reboot' then
        inp = {}
        if frame - phaseStart == 70 then
            triggerWin = true
            phase = 'test_win_hook'
            phaseStart = frame
        end

    elseif phase == 'test_win_hook' then
        if restoreHits >= 1 then
            check(winHookHits >= 1, 'Bonus Round Win hook ($78A0) executed (' .. winHookHits .. ')')
            check(read(0x648E) == 0x57, string.format('Reward flag $648E == $57 (got $%02X)', read(0x648E)))
            finish()
        elseif frame - phaseStart > 20 then
            check(false, 'Bonus Round Win did not reach $80F0 within 20 frames')
            finish()
        end
    end
end, emu.eventType.endFrame)
