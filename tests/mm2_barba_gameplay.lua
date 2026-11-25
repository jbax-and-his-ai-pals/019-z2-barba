-- Barba Man 2 gameplay & visual/audio verification on build/subgames/mm2.nes.
local mem = emu.memType.nesMemory
local ppu = emu.memType.nesPpuDebug
local prgRom = emu.memType.nesPrgRom
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end
local function readPpu(a) return emu.read(a, ppu) end
local function readPrg(off) return emu.read(off, prgRom) end

local report = assert(io.open(OUTPUT_DIR .. '/mm2_barba_gameplay.txt', 'w'))
local errors = 0
local function check(cond, msg)
    report:write((cond and 'PASS ' or 'FAIL ') .. msg .. '\n')
    if not cond then errors = errors + 1 end
end

local function saveShot(name)
    local png = emu.takeScreenshot()
    assert(png and #png > 0, 'Empty screenshot for ' .. name)
    local f = assert(io.open(OUTPUT_DIR .. '/' .. name, 'wb'))
    f:write(png)
    f:close()
    report:write(string.format('SHOT %s (%d bytes)\n', name, #png))
end

local done = false
local function finish()
    if done then return end
    done = true
    report:write(errors == 0 and 'RESULT PASS\n' or 'RESULT FAIL\n')
    report:close()
    local stop = emu.exit or emu.stop
    stop(errors == 0 and 0 or 1)
end

-- Instrumentation counters
local frame = 0
local phase = 'boot'
local phaseStart = 0

local playRoarCount = 0
local bossIntroRoarCount = 0
local sfxRoarCount = 0
local apu4015WrapperCount = 0
local last4010, last4011, last4012, last4013 = -1, -1, -1, -1
local sawDmcStart4015 = false

local returnCount = 0
local restoreHits = 0
local winHookCount = 0

local triggerWilyReveal = false
local triggerReboot = false
local triggerWin = false

emu.addMemoryCallback(function() playRoarCount = playRoarCount + 1 end, emu.callbackType.exec, 0xF470)
emu.addMemoryCallback(function() bossIntroRoarCount = bossIntroRoarCount + 1 end, emu.callbackType.exec, 0xF4B0)
emu.addMemoryCallback(function() sfxRoarCount = sfxRoarCount + 1 end, emu.callbackType.exec, 0xF4B8)
emu.addMemoryCallback(function() apu4015WrapperCount = apu4015WrapperCount + 1 end, emu.callbackType.exec, 0xF498)
emu.addMemoryCallback(function() winHookCount = winHookCount + 1 end, emu.callbackType.exec, 0xF3C0)
emu.addMemoryCallback(function() returnCount = returnCount + 1 end, emu.callbackType.exec, 0xF3E0)
emu.addMemoryCallback(function()
    if returnCount > 0 then restoreHits = restoreHits + 1 end
end, emu.callbackType.exec, 0xFFD0)

emu.addMemoryCallback(function(_, val) last4010 = val end, emu.callbackType.write, 0x4010)
emu.addMemoryCallback(function(_, val) last4011 = val end, emu.callbackType.write, 0x4011)
emu.addMemoryCallback(function(_, val) last4012 = val end, emu.callbackType.write, 0x4012)
emu.addMemoryCallback(function(_, val) last4013 = val end, emu.callbackType.write, 0x4013)
emu.addMemoryCallback(function(_, val)
    if (val & 0x10) ~= 0 then sawDmcStart4015 = true end
end, emu.callbackType.write, 0x4015)

emu.addMemoryCallback(function()
    if triggerWilyReveal then
        triggerWilyReveal = false
        -- Force PRG bank 13 ($8000-$BFFF -> R6=26, R7=27), $2A=8 (Wily Stage 1 reveal), JMP $9678
        write(0x8000, 0x06); write(0x8001, 26)
        write(0x8000, 0x07); write(0x8001, 27)
        write(0x002A, 0x08)
        emu.setState({['cpu.pc'] = 0x9678})
    elseif triggerReboot then
        triggerReboot = false
        write(0xA001, 0x80)
        write(0x5FF0, 0x21)
        write(0x5FF1, 0x00)
        write(0x5FF2, 0x00)
        emu.setState({['cpu.pc'] = 0xF450})
    elseif triggerWin then
        triggerWin = false
        emu.setState({['cpu.pc'] = 0xC25A})
    end
end, emu.callbackType.exec, 0x8000, 0xFFFF)

local function enterPhase(p)
    phase = p
    phaseStart = frame
end

local function nametableHas(seq)
    for addr = 0x2000, 0x23BF - #seq + 1 do
        local ok = true
        for i = 1, #seq do
            if readPpu(addr + i - 1) ~= seq[i] then
                ok = false
                break
            end
        end
        if ok then return true end
    end
    return false
end

local function stageSelectPortraitMatchesRom()
    -- Bank 8 $8F00..$8FFF is PRG offset 8*0x4000 + 0x0F00 = 0x20F00 -> PPU $1700..$17FF
    for i = 0, 255 do
        if readPpu(0x1700 + i) ~= readPrg(0x20F00 + i) then
            return false
        end
    end
    return true
end

local function playerChrMatchesBank0()
    -- Fireball head/tail tiles $69-$6A at Bank 0 $9690-$96AF (PRG 0x1690..0x16AF) and player tile $00-$0F at 0x1000
    for i = 0, 31 do
        if readPpu(0x0690 + i) ~= readPrg(0x1690 + i) then
            return false
        end
    end
    for i = 0, 15 do
        if readPpu(0x0000 + i) ~= readPrg(0x1000 + i) then
            return false
        end
    end
    return true
end

local function oamHasFireball()
    local sawHead, sawTail = false, false
    for s = 0, 63 do
        local y = read(0x0200 + s * 4)
        local tid = read(0x0200 + s * 4 + 1)
        local attr = read(0x0200 + s * 4 + 2)
        if y < 0xF0 and (attr & 0x03) == 0 then
            if tid == 0x69 then sawHead = true end
            if tid == 0x6A then sawTail = true end
        end
    end
    return sawHead and sawTail
end

local function oamHasActiveSprites(minCount)
    local cnt = 0
    for s = 0, 63 do
        if read(0x0200 + s * 4) < 0xE0 then cnt = cnt + 1 end
    end
    return cnt >= minCount
end

local stageSelSettled = false
local bossIntroShotTaken = false
local gameplayShotTaken = false
local wilyRevealShotTaken = false
local fireballSeen = false
local fireballFrame = -1

emu.addEventCallback(function()
    if phase == 'title_to_stagesel' then
        -- Pulse START every 16 frames to advance Title -> Mode -> Stage Select cleanly
        if (frame % 16) < 4 then
            emu.setInput({start = true}, 0)
        else
            emu.setInput({}, 0)
        end
    elseif phase == 'select_boss' then
        local dt = frame - phaseStart
        if dt >= 4 and dt < 8 then
            emu.setInput({right = true}, 0)
        elseif dt >= 12 and dt < 16 then
            emu.setInput({start = true}, 0)
        else
            emu.setInput({}, 0)
        end
    elseif phase == 'gameplay' then
        local dt = frame - phaseStart
        if dt >= 45 and dt <= 65 then
            emu.setInput({right = true}, 0)
        elseif dt > 70 and (dt % 12) < 4 then
            emu.setInput({b = true}, 0)
        else
            emu.setInput({}, 0)
        end
    elseif phase == 'start_select' then
        emu.setInput({start = true, select = true}, 0)
    else
        emu.setInput({}, 0)
    end
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if done then return end
    frame = frame + 1
    local dt = frame - phaseStart

    if phase == 'boot' then
        if frame >= 30 then
            enterPhase('title_to_stagesel')
        end

    elseif phase == 'title_to_stagesel' then
        if nametableHas({0x05, 0x16, 0x09, 0x0C}) and nametableHas({0x0C, 0x09, 0x0E, 0x0B}) and stageSelectPortraitMatchesRom() then
            if not stageSelSettled then
                stageSelSettled = true
                phaseStart = frame
            elseif dt >= 20 then
                check(true, 'Stage Select displays EVIL LINK nametable text')
                check(not nametableHas({0x17, 0x09, 0x0C, 0x19}), 'Stage Select no longer displays WILY text')
                check(stageSelectPortraitMatchesRom(), 'Stage Select PPU $1700..$17FF matches Villainous Link portrait')
                saveShot('mm2_barba_stagesel.png')
                enterPhase('select_boss')
            end
        elseif dt > 400 then
            check(false, 'Timed out waiting for Stage Select EVIL LINK portrait')
            finish()
        end

    elseif phase == 'select_boss' then
        if bossIntroRoarCount >= 1 then
            enterPhase('boss_intro')
        elseif dt > 120 then
            check(false, 'Timed out waiting for Boss Intro roar hook ($F4B0)')
            finish()
        end

    elseif phase == 'boss_intro' then
        if not bossIntroShotTaken and dt >= 30 then
            bossIntroShotTaken = true
            saveShot('mm2_barba_bossintro.png')
            check(bossIntroRoarCount >= 1, string.format('Boss Intro roar triggered (%d)', bossIntroRoarCount))
            check(playRoarCount >= 1, string.format('MM2_PLAY_ROAR triggered (%d)', playRoarCount))
            check(last4010 == 0x09 and last4011 == 0x40 and last4012 == 0xD5 and last4013 == 0x38,
                string.format('APU DMC setup exact ($4010=%02X $4011=%02X $4012=%02X $4013=%02X)',
                    last4010, last4011, last4012, last4013))
            check(sawDmcStart4015, 'APU $4015 bit 4 set to start roar DMC sample')
            check(apu4015WrapperCount >= 1, string.format('Bank 12 $4015 protection ran (%d)', apu4015WrapperCount))
        end
        if dt >= 45 and readPpu(0x3F11) == 0x16 and readPpu(0x3F12) == 0x27 and readPpu(0x3F13) == 0x30 and playerChrMatchesBank0() then
            enterPhase('gameplay')
        elseif dt > 400 then
            check(false, string.format('Timed out entering gameplay (pal=%02X %02X %02X)',
                readPpu(0x3F11), readPpu(0x3F12), readPpu(0x3F13)))
            finish()
        end

    elseif phase == 'gameplay' then
        if not fireballSeen and oamHasFireball() then
            fireballSeen = true
            fireballFrame = frame
            check(true, 'Fireball Mega Buster shot ($69/$6A Pal 0) active in OAM')
            check(playerChrMatchesBank0(), 'Player & fireball CHR-RAM ($0000/$0690) matches Barba Bank 0 data')
            check(readPpu(0x3F11) == 0x16 and readPpu(0x3F12) == 0x27 and readPpu(0x3F13) == 0x30,
                string.format('Barba Pal 0 active in PPU ($3F11..$3F13 = %02X %02X %02X)',
                    readPpu(0x3F11), readPpu(0x3F12), readPpu(0x3F13)))
        elseif fireballSeen and not gameplayShotTaken and frame >= fireballFrame + 2 then
            gameplayShotTaken = true
            saveShot('mm2_barba_gameplay.png')
            triggerWilyReveal = true
            enterPhase('wily_reveal')
        elseif dt > 260 then
            check(playerChrMatchesBank0(), 'Player & fireball CHR-RAM ($0000/$0690) matches Barba Bank 0 data')
            check(false, 'Timed out waiting for fireball OAM sprites ($69/$6A)')
            finish()
        end

    elseif phase == 'wily_reveal' then
        if not wilyRevealShotTaken and dt >= 165 and oamHasActiveSprites(4) then
            wilyRevealShotTaken = true
            -- Preset 1 loads Bank 6 $9400..$947F into PPU $0400..$047F (PRG offset 6*0x4000 + 0x1400 = 0x19400)
            local pilotOk = true
            for i = 0, 95 do
                if readPpu(0x0400 + i) ~= readPrg(0x19400 + i) then
                    pilotOk = false
                    break
                end
            end
            check(sfxRoarCount >= 1, string.format('Wily Reveal triggered MM2_ROAR_SFX ($F4B8 count=%d)', sfxRoarCount))
            check(playRoarCount >= 2, string.format('MM2_PLAY_ROAR ran on both Boss Intro and Wily Reveal (%d)', playRoarCount))
            check(pilotOk, 'Wily Reveal PPU $0400..$045F matches Villainous Link Bank 6 pilot tiles')
            saveShot('mm2_barba_wily_reveal.png')
            enterPhase('wait_debounce')
        elseif dt > 220 then
            check(false, 'Timed out in Wily Reveal cutscene')
            finish()
        end

    elseif phase == 'wait_debounce' then
        if read(0x07FF) >= 0x3C then
            enterPhase('start_select')
        elseif dt > 120 then
            check(false, 'Timed out waiting for $07FF debounce')
            finish()
        end

    elseif phase == 'start_select' then
        if restoreHits >= 1 then
            check(read(0x648F) == 0x00, string.format('Start+Select leaves reward flag clear ($648F=%02X)', read(0x648F)))
            returnCount = 0
            restoreHits = 0
            triggerReboot = true
            enterPhase('reboot_for_win')
        elseif dt > 30 then
            check(false, 'Start+Select failed to return to $FFD0')
            finish()
        end

    elseif phase == 'reboot_for_win' then
        if dt >= 4 then
            triggerWin = true
            enterPhase('win_wait')
        end

    elseif phase == 'win_wait' then
        if restoreHits >= 1 then
            check(winHookCount >= 1, string.format('Win hook $F3C0 executed (%d)', winHookCount))
            check(read(0x648F) == 0x32, string.format('Win hook sets $648F == $32 (got $%02X)', read(0x648F)))
            finish()
        elseif dt > 30 then
            check(false, 'Win hook failed to return to $FFD0')
            finish()
        end
    end
end, emu.eventType.endFrame)
