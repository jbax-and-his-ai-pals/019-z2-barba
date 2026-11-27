-- Barba Kong (Round 2 MMC3) gameplay, art/palette, CHR banking, roar/DMC, and portal contract test.
local mem = emu.memType.nesMemory
local ppu = emu.memType.nesPpuDebug
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end
local function readPal(i) return emu.read(0x3F00 + i, ppu) end

local report = assert(io.open(OUTPUT_DIR .. '/dk_barba_gameplay.txt', 'w'))
local errors = 0
local function check(cond, msg)
    report:write((cond and 'PASS ' or 'FAIL ') .. msg .. '\n')
    report:flush()
    if not cond then errors = errors + 1 end
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

local frame = 0
local phase = 'title'
local phaseStart = 0
local illegal5ffxWrites = 0
local inExitTrampoline = false
local dmcWriteSeen = false
local dmcEnableSeen = false
local restoreHits = 0
local winHookCount = 0
local roarBeforeDeath = 0

local seenR0Normal = {}
local seenR0Fury = {}
local seenR1 = {}
local seenR4 = {}
local sawFireballSprite = false
local sawZeldaSprite = false
local sawBarbaSprite = false
local furySpinTileSeen = false
local furyBackwardRight = 0
local furyBackwardLeft = 0
local furyUpSeen = false
local furyFwdSeen = false
local furyDownSeen = false
local furyLeftShotSeen = false
local furyTotalShots = 0
local furyStraightShots = 0

emu.addMemoryCallback(function(addr, val)
    if not inExitTrampoline and frame > 5 then
        illegal5ffxWrites = illegal5ffxWrites + 1
    end
end, emu.callbackType.write, 0x5FF0, 0x5FF2)

emu.addMemoryCallback(function(addr, val)
    dmcWriteSeen = true
end, emu.callbackType.write, 0x4012)

emu.addMemoryCallback(function(addr, val)
    if (val & 0x10) ~= 0 then
        dmcEnableSeen = true
    end
end, emu.callbackType.write, 0x4015)

emu.addMemoryCallback(function()
    inExitTrampoline = true
end, emu.callbackType.exec, 0x7960)

emu.addMemoryCallback(function()
    winHookCount = winHookCount + 1
end, emu.callbackType.exec, 0x7870)

emu.addMemoryCallback(function()
    restoreHits = restoreHits + 1
end, emu.callbackType.exec, 0x80F0)

local function saveShot(name)
    local png = emu.takeScreenshot()
    local f = assert(io.open(OUTPUT_DIR .. '/' .. name, 'wb'))
    f:write(png)
    f:close()
end

emu.addEventCallback(function()
    if phase == 'press_start' then
        emu.setInput({start = true}, 0)
    elseif phase == 'play_25m' then
        local pf = frame - phaseStart
        if pf < 45 then
            emu.setInput({right = true}, 0)
        elseif pf >= 45 and pf < 60 then
            emu.setInput({right = true, a = true}, 0)
        else
            emu.setInput({}, 0)
        end
    elseif phase == 'fury_check' then
        local pf = frame - phaseStart
        if pf >= 150 and pf < 160 then
            emu.setInput({left = true}, 0)
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

    -- Track multi-bank MMC3 CHR cycling
    if frame > 10 and (phase == 'play_25m' or phase == 'play_100m' or phase == 'fury_check') then
        local r0 = read(0x7FFA)
        local r1 = read(0x7FFB)
        local r4 = read(0x7FFC)
        if read(0x00A0) == 0 then
            seenR0Normal[r0] = true
        else
            seenR0Fury[r0] = true
        end
        seenR1[r1] = true
        seenR4[r4] = true
    end

    if phase == 'title' then
        if frame == 65 then
            check(read(0x004E) == 0x01, 'Title mode active ($4E=$01)')
            check(read(0x7FFF) == 0x3C, 'Debounce reached $3C')
            check(readPal(1) == 0x2C and readPal(2) == 0x38 and readPal(3) == 0x12,
                string.format('Title Barba Kong logo palette (%02X %02X %02X)', readPal(1), readPal(2), readPal(3)))
            check(readPal(0x11) == 0x16 and readPal(0x12) == 0x27 and readPal(0x13) == 0x30,
                'Title fireball cursor SPR0 palette is Barba colors')
            saveShot('dk_barba_title.png')
            phase = 'press_start'
            phaseStart = frame
        end

    elseif phase == 'press_start' then
        if frame - phaseStart >= 6 then
            phase = 'wait_25m'
            phaseStart = frame
        end

    elseif phase == 'wait_25m' then
        if read(0x004E) == 0 and read(0x004F) == 1 then
            check(read(0x7FFD) >= 1, 'Title Start triggered sampled Barba roar (roar_count=' .. read(0x7FFD) .. ')')
            check(dmcWriteSeen and dmcEnableSeen, 'DMC $4012 and $4015 bit 4 written for roar.dmc')
            phase = 'play_25m'
            phaseStart = frame
        elseif frame - phaseStart > 600 then
            check(false, 'Timed out entering 25m stage (4E=' .. read(0x004E) .. ' 4F=' .. read(0x004F) .. ')')
            finish()
        end

    elseif phase == 'play_25m' then
        local pf = frame - phaseStart
        if pf == 90 then
            -- Verify palettes for Big Bad Link (BG2), Lil' Barba (SPR0), Princess Zelda (SPR1), Fireballs (SPR2)
            check(readPal(0x09) == 0x2A and readPal(0x0A) == 0x36 and readPal(0x0B) == 0x17,
                string.format('Big Bad Link BG2 palette ($2A $36 $17, got %02X %02X %02X)', readPal(0x09), readPal(0x0A), readPal(0x0B)))
            check(readPal(0x11) == 0x16 and readPal(0x12) == 0x27 and readPal(0x13) == 0x30,
                string.format('Lil Barba SPR0 palette ($16 $27 $30, got %02X %02X %02X)', readPal(0x11), readPal(0x12), readPal(0x13)))
            check(readPal(0x15) == 0x25 and readPal(0x16) == 0x36 and readPal(0x17) == 0x27,
                string.format('Princess Zelda SPR1 palette ($25 $36 $27, got %02X %02X %02X)', readPal(0x15), readPal(0x16), readPal(0x17)))
            check(readPal(0x19) == 0x12 and readPal(0x1A) == 0x21 and readPal(0x1B) == 0x30,
                string.format('Zelda Blue Bomb/Hazard SPR2 palette ($12 $21 $30, got %02X %02X %02X)', readPal(0x19), readPal(0x1A), readPal(0x1B)))
        end
        -- Inspect active sprites on 25m
        if read(0x0200) < 0xEF and read(0x0201) <= 0x2F then
            sawBarbaSprite = true
        end
        if read(0x02E8) < 0xEF and read(0x02E9) == 0xD5 and (read(0x02F1) == 0xD7 or read(0x02F1) == 0xDB) then
            sawZeldaSprite = true
        end
        for slot = 0, 8 do
            local y = read(0x0230 + slot * 16)
            local t = read(0x0231 + slot * 16)
            if y < 0xEF and t >= 0x80 and t <= 0x97 then
                sawFireballSprite = true
            end
        end
        if pf == 120 then
            saveShot('dk_barba_25m.png')
            check(sawBarbaSprite, 'Lil Barba sprite active in OAM[0..3]')
            check(sawZeldaSprite, 'Princess Zelda sprite active at top ($D5 + $D7/$DB)')
            check(sawFireballSprite, 'Fireball/Bomb hazard active in OAM ($80-$97)')
            -- Trigger Flame/Breath Fury state ($A0=1, $9F=1, $96=$0A) and check R0 fury bank swap
            write(0x00A0, 1)
            write(0x009F, 1)
            write(0x0096, 0x0A)
            write(0x003F, 0x30)
            write(0x7FE0, 0)
            write(0x7FE5, 0)
            write(0x7FEA, 0)
            phase = 'fury_check'
            phaseStart = frame
        end

    elseif phase == 'fury_check' then
        local pf = frame - phaseStart
        -- Check Barba OAM[0..3] tiles never use back-facing climb tiles ($10..$1F) while holding Flame Fury
        for s = 0, 3 do
            local tid = read(0x0201 + s * 4)
            if tid >= 0x10 and tid <= 0x1F then
                furySpinTileSeen = true
            end
        end
        -- Sample newly spawned fireball slots ($7FE0/$7FE5, timer == 0x19 right after step)
        local facing = read(0x0057)
        for _, base in ipairs({0x7FE0, 0x7FE5}) do
            local timer = read(base)
            if timer == 0x19 then
                local vx = read(base + 3)
                local vy = read(base + 4)
                local sx = vx >= 128 and vx - 256 or vx
                local sy = vy >= 128 and vy - 256 or vy
                if pf < 150 and facing == 1 then
                    furyTotalShots = furyTotalShots + 1
                    if sy == 0 and sx == 3 then furyStraightShots = furyStraightShots + 1 end
                    if sx < 0 then furyBackwardRight = furyBackwardRight + 1 end
                    if sy < 0 then furyUpSeen = true end
                    if sy == 0 then furyFwdSeen = true end
                    if sy > 0 then furyDownSeen = true end
                elseif pf >= 165 and facing ~= 1 then
                    if sx > 0 then furyBackwardLeft = furyBackwardLeft + 1 end
                    if sx < 0 then furyLeftShotSeen = true end
                end
            end
        end
        if pf == 240 then
            local furyCount = 0
            for _ in pairs(seenR0Fury) do furyCount = furyCount + 1 end
            check(furyCount >= 1 and (seenR0Fury[4] or seenR0Fury[6]),
                'Flame Fury switched MMC3 R0 to Wyrmling Fury banks (4/6)')
            check(not furySpinTileSeen, 'Flame Fury kept Barba facing forward (no $10-$1F climb/spin tiles)')
            check(furyBackwardRight == 0 and furyBackwardLeft == 0,
                string.format('Flame Fury never fired backward (right_bad=%d, left_bad=%d)', furyBackwardRight, furyBackwardLeft))
            check(furyUpSeen and furyFwdSeen and furyDownSeen,
                string.format('Flame Fury covered 180-deg forward cone (up=%s fwd=%s down=%s)',
                    tostring(furyUpSeen), tostring(furyFwdSeen), tostring(furyDownSeen)))
            check(furyTotalShots >= 6 and furyStraightShots * 2 >= furyTotalShots,
                string.format('Flame Fury favored straight-forward shots (%d/%d)', furyStraightShots, furyTotalShots))
            check(furyLeftShotSeen, 'Flame Fury fired left after turning left')
            write(0x00A0, 0)
            write(0x009F, 0)
            write(0x0096, 0)
            -- Jump to 100m stage ($53=4) to inspect Big Bad Link, Zelda, Z2 Bubbles & Rivets
            write(0x0053, 4)
            write(0x0043, 0x76)
            write(0x004E, 0)
            write(0x004F, 0)
            write(0x009A, 0)
            phase = 'play_100m'
            phaseStart = frame
        end

    elseif phase == 'play_100m' then
        if frame - phaseStart == 110 then
            check(readPal(0x09) == 0x2A and readPal(0x0A) == 0x36 and readPal(0x0B) == 0x17,
                '100m preserved Big Bad Link BG2 palette ($2A $36 $17)')
            saveShot('dk_barba_100m.png')
            local r0Count, r1Count, r4Count = 0, 0, 0
            for _ in pairs(seenR0Normal) do r0Count = r0Count + 1 end
            for _ in pairs(seenR1) do r1Count = r1Count + 1 end
            for _ in pairs(seenR4) do r4Count = r4Count + 1 end
            check(r0Count >= 2, 'MMC3 R0 Lil Barba animated across >= 2 banks (count=' .. r0Count .. ')')
            check(r1Count >= 4, 'MMC3 R1 Zelda/Hazards animated across 4 banks (count=' .. r1Count .. ')')
            check(r4Count >= 4, 'MMC3 R4/R5 Big Bad Link animated across 4 bank pairs (count=' .. r4Count .. ')')
            check(illegal5ffxWrites == 0, 'Zero writes to $5FF0-$5FF2 during gameplay (got ' .. illegal5ffxWrites .. ')')
            roarBeforeDeath = read(0x7FFD)
            write(0x7FF8, 0)
            write(0x004E, 0)
            write(0x004F, 1)
            write(0x0058, 0)
            write(0x0098, 0)
            write(0x0096, 0xFF)
            phase = 'death_roar'
            phaseStart = frame
        end

    elseif phase == 'death_roar' then
        if read(0x7FFD) > roarBeforeDeath or frame - phaseStart >= 60 then
            check(read(0x7FFD) > roarBeforeDeath,
                string.format('Death ($D0D5) triggered sampled Barba roar (before=%d after=%d)',
                    roarBeforeDeath, read(0x7FFD)))
            check(read(0x7FF8) > 0, 'Death roar set DK_ROAR_TIMER (' .. read(0x7FF8) .. ')')
            phase = 'start_select'
            phaseStart = frame
        end

    elseif phase == 'fury_check' then
        local pf = frame - phaseStart
        if pf >= 150 and pf < 160 then
            emu.setInput({left = true}, 0)
        else
            emu.setInput({}, 0)
        end
    elseif phase == 'start_select' then
        if restoreHits >= 1 then
            check(read(0x648F) ~= 0x44, 'Start+Select exited cleanly without setting reward')
            restoreHits = 0
            inExitTrampoline = false
            write(0xA001, 0xA3)
            emu.setState({['cpu.pc'] = 0x7AE0})
            phase = 'win_reset'
            phaseStart = frame
        elseif frame - phaseStart > 20 then
            check(false, 'Start+Select exit timed out')
            finish()
        end

    elseif phase == 'win_reset' then
        if frame - phaseStart == 70 then
            write(0x004E, 0); write(0x004F, 1); write(0x009A, 1)
            write(0x044F, 8); write(0x0450, 1); write(0x0043, 0)
            phase = 'win_wait'
            phaseStart = frame
        end

    elseif phase == 'win_wait' then
        if restoreHits >= 1 then
            check(winHookCount >= 1, '100m win hook ($7870) executed')
            check(read(0x648F) == 0x44, string.format('100m win set reward flag $648F=$44 (got $%02X)', read(0x648F)))
            finish()
        elseif frame - phaseStart > 20 then
            check(false, '100m win hook timed out')
            finish()
        end
    end
end, emu.eventType.endFrame)
