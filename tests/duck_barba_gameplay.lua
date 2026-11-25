-- Villager Hunt (MMC3 Duck Hunt) gameplay verification:
-- Title screen, D-pad crosshair, A-button fireball burst, Z2 villagers, Barba roar/DMC,
-- Villainous Link miss laugh, Game C Octorok/Moa/Palace Plate, round-clear win hook, Start+Select.
local mem = emu.memType.nesMemory
local oam = emu.memType.nesSpriteRam
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end

local VH_CURSOR_X     = 0x0620
local VH_CURSOR_Y     = 0x0621
local VH_FIRE_TIMER   = 0x0624
local VH_TARGET_KIND0 = 0x0627
local VH_ROAR_TIMER   = 0x0629
local VH_MMC3_MODE    = 0x062A
local VH_CUR_R0       = 0x062B
local VH_CUR_R1       = 0x062C
local VH_CUR_BG       = 0x062D

local report = assert(io.open(OUTPUT_DIR .. '/duck_barba_gameplay.txt', 'w'))
local errors = 0
local function check(cond, msg)
    report:write((cond and 'PASS ' or 'FAIL ') .. msg .. '\n')
    if not cond then errors = errors + 1 end
end

local function saveShot(name)
    local png = emu.takeScreenshot()
    local f = assert(io.open(OUTPUT_DIR .. '/' .. name, 'wb'))
    f:write(png)
    f:close()
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
local phase = 'title_wait'
local phaseStart = 0
local inp = {}

local sawIntroRoarDmc = false
local sawIntroScreenShake = false
local shakeSettledBeforeEnemy = false
local roarFinishedCleanly = false
local sawFullBodyBarba = false
local sawDownstabJump = false
local savedJumpShot = false
local sawBarbaCatch = false
local sawLinkLaugh = false
local sawRoundClearRoar = false
local winHookCount = 0
local restoreHits = 0
local dpadMoved = false
local startCX, startCY = 0, 0
local prevAmmo = 3
local sawShotFireball = false
local sawVillagerHit = false
local savedVillagerShot = false
local savedBurstShot = false
local missShotsRemaining = 0
local clayShotDone = false

emu.addMemoryCallback(function(_, val)
    if (val & 0x10) ~= 0 and read(VH_MMC3_MODE) == 0x40 then
        if phase == 'wait_intro' then
            sawIntroRoarDmc = true
        elseif phase == 'round_clear' then
            sawRoundClearRoar = true
        end
    end
end, emu.callbackType.write, 0x4015)

emu.addMemoryCallback(function()
    winHookCount = winHookCount + 1
end, emu.callbackType.exec, 0x7870)

emu.addMemoryCallback(function()
    restoreHits = restoreHits + 1
end, emu.callbackType.exec, 0x80F0)

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

local function hasCrosshairOam()
    local y0 = emu.read(0x10, oam)
    local t0 = emu.read(0x11, oam)
    return y0 < 0xEC and t0 == 0x00
end

local function hasFireballOam()
    local y0 = emu.read(0x00, oam)
    local t0 = emu.read(0x01, oam)
    return y0 < 0xEC and t0 >= 0x04 and t0 <= 0x0F
end

emu.addEventCallback(function()
    if done then return end
    frame = frame + 1
    inp = {}

    if phase == 'title_wait' then
        if frame == 65 then
            check(read(0x0024) == 0x01, 'Title screen active ($24=$01)')
            saveShot('duck_title.png')
            phase = 'start_game_a'
            phaseStart = frame
        end

    elseif phase == 'start_game_a' then
        local dt = frame - phaseStart
        if dt <= 4 then
            inp = {a = true}
        elseif read(0x0024) == 0x00 then
            check(true, 'A button started Game A (Villager Hunt)')
            phase = 'wait_intro'
            phaseStart = frame
        elseif dt > 30 then
            check(false, 'A button did not start Game A')
            finish()
        end

    elseif phase == 'wait_intro' then
        local dt = frame - phaseStart
        if dt == 40 then
            saveShot('duck_barba_intro.png')
        end
        if read(0x00A1) == 2 or (read(0x0025) == 0x01) then
            local f35 = read(0x0035)
            local x33 = read(0x0033)
            if (f35 == 0x0C or f35 == 0x0D) and x33 >= 48 and not sawFullBodyBarba then
                local minX, maxX, minY, maxY = 255, 0, 255, 0
                for o = 0x90, 0xFC, 4 do
                    local oy = emu.read(o, oam)
                    local ox = emu.read(o + 3, oam)
                    if oy < 0xEC then
                        if ox < minX then minX = ox end
                        if ox > maxX then maxX = ox end
                        if oy < minY then minY = oy end
                        if oy > maxY then maxY = oy end
                    end
                end
                if (maxX - minX) >= 40 and (maxY - minY) >= 40 then
                    sawFullBodyBarba = true
                end
            elseif (f35 == 0x12 or f35 == 0x13) then
                if not savedJumpShot and f35 == 0x12 then
                    saveShot('duck_barba_jump.png')
                    savedJumpShot = true
                end
                if read(0x000B) ~= 0 then
                    sawIntroScreenShake = true
                end
                local minY, maxY = 255, 0
                for o = 0x90, 0xFC, 4 do
                    local oy = emu.read(o, oam)
                    if oy < 0xEC then
                        if oy < minY then minY = oy end
                        if oy > maxY then maxY = oy end
                    end
                end
                if (maxY - minY) >= 80 then
                    sawDownstabJump = true
                end
            end
        end
        if sawIntroRoarDmc and read(VH_ROAR_TIMER) == 0 and read(VH_MMC3_MODE) == 0x00 then
            roarFinishedCleanly = true
        end
        if read(0x0025) == 0x03 and read(0x0300) ~= 0 and read(0x0301) == 0x03 then
            shakeSettledBeforeEnemy = (read(0x000B) == 0) and (read(0x0629) == 0)
            check(sawIntroRoarDmc, 'Barba intro triggered sampled roar.dmc with bank 29 ($40 mode)')
            check(sawIntroScreenShake, 'Barba downstab jump triggered screen shake ($0B != 0)')
            check(shakeSettledBeforeEnemy, 'Screen shake and roar ended before first enemy emerged')
            check(sawFullBodyBarba, 'Barba intro rendered full-body (3 vertical rows + 2-tile horizontal tail)')
            check(sawDownstabJump, 'Barba jump into grass rendered full-length Z2 downstab graphic (96px tall)')
            startCX = read(VH_CURSOR_X)
            startCY = read(VH_CURSOR_Y)
            check(hasCrosshairOam(), string.format('Crosshair visible at (%d,%d)', startCX, startCY))
            phase = 'dpad_aim_and_shoot'
            phaseStart = frame
        elseif dt > 560 then
            check(false, string.format('Timed out waiting for villager spawn ($25=%02X $0301=%02X)', read(0x0025), read(0x0301)))
            finish()
        end

    elseif phase == 'dpad_aim_and_shoot' then
        local dt = frame - phaseStart
        if sawIntroRoarDmc and read(VH_ROAR_TIMER) == 0 and read(VH_MMC3_MODE) == 0x00 then
            roarFinishedCleanly = true
        end
        local tx = read(0x0303)
        local ty = read(0x0302)
        if not savedVillagerShot and ty <= 132 then
            savedVillagerShot = true
            saveShot('duck_villager.png')
        end
        if dt <= 8 then
            inp = {right = true, down = true}
        elseif dt == 9 then
            local cx, cy = read(VH_CURSOR_X), read(VH_CURSOR_Y)
            dpadMoved = (cx > startCX) and (cy > startCY)
            check(dpadMoved, string.format('D-pad moved crosshair (%d,%d)->(%d,%d)', startCX, startCY, cx, cy))
        else
            local cx, cy = read(VH_CURSOR_X), read(VH_CURSOR_Y)
            local dx = tx - cx
            local dy = ty - cy
            if math.abs(dx) > 4 then
                if dx > 0 then inp.right = true else inp.left = true end
            end
            if math.abs(dy) > 4 then
                if dy > 0 then inp.down = true else inp.up = true end
            end
            if math.abs(dx) <= 6 and math.abs(dy) <= 6 and ty <= 132 and read(0x0301) == 0x03 and not sawShotFireball then
                prevAmmo = read(0x00BA)
                inp = {a = true}
                sawShotFireball = true
            end
        end

        if sawShotFireball then
            local ft = read(VH_FIRE_TIMER)
            if ft > 0 and ft <= 11 and hasFireballOam() and not savedBurstShot then
                savedBurstShot = true
                check(true, 'A-button fired Barba fireball burst OAM')
                saveShot('duck_fireball_hit.png')
            end
            if read(0x0301) == 0x04 or read(0x0301) == 0x05 then
                sawVillagerHit = true
            end
            if sawVillagerHit and read(0x03A0) ~= 0 and (read(0x03A1) == 0x0C or read(0x03A1) == 0x0D) then
                if read(0x03A2) <= 0x90 then
                    sawBarbaCatch = true
                    check(read(0x00AA) >= 1, 'Villager hit incremented round score counter ($AA=' .. read(0x00AA) .. ')')
                    check(read(0x00BA) < prevAmmo, 'A-button shot consumed ammo')
                    check(read(VH_CUR_R1) == 14, 'Barba celebration uses R1=14')
                    local aboveBad, belowBad = 0, 0
                    for off = 0x60, 0x8C, 4 do
                        local sy = emu.read(off, oam)
                        if sy < 0xEF then
                            local bgBit = emu.read(off + 2, oam) & 0x20
                            if sy < 0x8F and bgBit ~= 0 then aboveBad = aboveBad + 1 end
                            if sy >= 0x8F and bgBit == 0 then belowBad = belowBad + 1 end
                        end
                    end
                    check(aboveBad == 0 and belowBad == 0,
                        string.format('Barba/XP bag above bushes draws on top of trees (aboveBad=%d belowBad=%d)', aboveBad, belowBad))
                    saveShot('duck_barba_catch.png')
                    phase = 'miss_for_link'
                    phaseStart = frame
                    missShotsRemaining = 3
                end
            elseif dt > 360 then
                check(sawVillagerHit, 'A-button fireball hit villager (state=' .. read(0x0301) .. ')')
                check(sawBarbaCatch, string.format('Barba catch did not run ($03A0=%02X $03A1=%02X)', read(0x03A0), read(0x03A1)))
                finish()
            end
        elseif dt > 240 then
            check(false, 'Timed out aiming at villager')
            finish()
        end

    elseif phase == 'miss_for_link' then
        local dt = frame - phaseStart
        if read(0x0025) == 0x03 and read(0x0300) ~= 0 and read(0x0301) == 0x03 and read(0x00B9) ~= 0 then
            -- Aim far corner away from target and waste 3 shots
            local tx = read(0x0303)
            local aimX = (tx < 128) and 224 or 16
            local cx = read(VH_CURSOR_X)
            if math.abs(aimX - cx) > 6 then
                if aimX > cx then inp.right = true else inp.left = true end
            elseif missShotsRemaining > 0 and (dt % 6 == 0) then
                inp = {b = true}
                missShotsRemaining = missShotsRemaining - 1
            end
        end
        if read(0x03A0) ~= 0 and read(VH_CUR_R1) == 16 and read(0x03A2) <= 0x90 then
            sawLinkLaugh = true
            check(true, 'Miss triggered Villainous Link laugh (R1=16)')
            saveShot('duck_link_laugh.png')
            -- Advance Round 1 -> Round 2 (Overworld Grass)
            write(0x00AA, 0x0A); write(0x00AB, 0x06); write(0x00BB, 0x0A); write(0x00BC, 0x00)
            write(0x0300, 0x00); write(0x0350, 0x00); write(0x00A9, 0x01); write(0x002B, 0x00)
            write(0x0025, 0x04)
            phase = 'wait_grass_round'
            phaseStart = frame
        elseif dt > 640 then
            check(false, 'Timed out waiting for Villainous Link laugh ($03A0=' .. read(0x03A0) .. ' st=' .. read(0x03A1) .. ' R1=' .. read(VH_CUR_R1) .. ')')
            finish()
        end

    elseif phase == 'wait_grass_round' then
        local dt = frame - phaseStart
        if dt > 30 and read(0x0025) == 0x03 and read(0x0300) ~= 0 and read(0x0301) == 0x03 then
            check(read(0x0636) == 1 and read(VH_CUR_BG) == 32,
                string.format('Round 2 switched to Z2 Overworld Grass (scene=%d BG=%d)', read(0x0636), read(VH_CUR_BG)))
            saveShot('duck_grass.png')
            -- Advance Round 2 -> Round 3 (Desert)
            write(0x00AA, 0x0A); write(0x00AB, 0x06); write(0x00BB, 0x0A); write(0x00BC, 0x00)
            write(0x0300, 0x00); write(0x0350, 0x00); write(0x00A9, 0x01); write(0x002B, 0x00)
            write(0x0025, 0x04)
            phase = 'wait_desert_round'
            phaseStart = frame
        elseif dt > 800 then
            check(false, string.format('Timed out waiting for Round 2 Grass ($25=%02X BG=%d)', read(0x0025), read(VH_CUR_BG)))
            finish()
        end

    elseif phase == 'wait_desert_round' then
        local dt = frame - phaseStart
        if dt > 30 and read(0x0025) == 0x03 and read(0x0300) ~= 0 and read(0x0301) == 0x03 then
            check(read(0x0636) == 2 and read(VH_CUR_BG) == 36,
                string.format('Round 3 switched to Z2 Desert (scene=%d BG=%d)', read(0x0636), read(VH_CUR_BG)))
            saveShot('duck_desert.png')
            phase = 'game_c_reset'
            phaseStart = frame
            emu.reset()
        elseif dt > 800 then
            check(false, string.format('Timed out waiting for Round 3 Desert ($25=%02X BG=%d)', read(0x0025), read(VH_CUR_BG)))
            finish()
        end

    elseif phase == 'game_c_reset' then
        local dt = frame - phaseStart
        if dt >= 65 and dt <= 68 then
            inp = {down = true}
        elseif dt >= 75 and dt <= 78 then
            inp = {down = true}
        elseif dt == 82 then
            check(read(0x05FE) == 0x02, string.format('D-pad Down selected Game C ($05FE=%02X)', read(0x05FE)))
        elseif dt >= 84 and dt <= 88 then
            inp = {a = true}
        elseif read(0x0024) == 0x00 and read(0x0025) == 0x0B and read(0x0300) ~= 0 and read(0x0301) == 0x03 and read(0x0302) <= 136 then
            if not clayShotDone then
                check(read(VH_CUR_R0) == 10, 'Game C switches R0=10 (Octoroks/Moas/Palace Plates)')
                saveShot('duck_game_c.png')
                -- Aim & shoot Game C target
                local tx, ty = read(0x0303), read(0x0302)
                write(VH_CURSOR_X, tx)
                write(VH_CURSOR_Y, ty)
                inp = {a = true}
                clayShotDone = true
                phase = 'game_c_hit_wait'
                phaseStart = frame
            end
        elseif dt > 450 then
            check(false, string.format('Timed out reaching Game C target ($25=%02X $0301=%02X)', read(0x0025), read(0x0301)))
            finish()
        end

    elseif phase == 'game_c_hit_wait' then
        local dt = frame - phaseStart
        if read(0x00AA) >= 1 then
            check(true, 'Game C A-button fireball hit flying target ($AA=' .. read(0x00AA) .. ')')
            -- Now test Round Clear roar ($D30F) + Round 1 -> Round 2 transition in standalone
            phase = 'round_clear'
            phaseStart = frame
            write(0x00AA, 0x0A)
            write(0x00AB, 0x06)
            write(0x00BB, 0x0A)
            write(0x00BC, 0x00)
            write(0x0300, 0x00)
            write(0x0350, 0x00)
            write(0x00A9, 0x01)
            write(0x002B, 0x00)
            write(0x0025, 0x04)
        elseif dt > 60 then
            check(false, 'Game C target did not register hit')
            finish()
        end

    elseif phase == 'round_clear' then
        local dt = frame - phaseStart
        if dt > 30 and read(0x0025) == 0x0B and read(0x0300) ~= 0 and read(0x0301) == 0x03 then
            check(roarFinishedCleanly, 'Intro roar timer cleanly restored MMC3 PRG mode $00')
            check(sawRoundClearRoar, 'Round Clear triggered sampled Barba roar.dmc')
            check(winHookCount == 0, 'Standalone round clear did not exit via DUCK_WIN_HOOK')
            check(true, 'Standalone Round 1 cleared and advanced cleanly to Round 2')
            -- Now test Start+Select exit after reboot
            restoreHits = 0
            write(0xA001, 0xA3)
            emu.setState({['cpu.pc'] = 0x7AE0})
            phase = 'start_select_exit'
            phaseStart = frame
        elseif dt > 800 then
            check(false, string.format('Timed out waiting for Round 2 ($25=%02X $0300=%02X $0301=%02X)', read(0x0025), read(0x0300), read(0x0301)))
            finish()
        end

    elseif phase == 'start_select_exit' then
        local dt = frame - phaseStart
        if dt >= 68 then
            inp = {start = true, select = true}
        end
        if restoreHits >= 1 then
            check(true, 'Start+Select cleanly exited to $80F0')
            finish()
        elseif dt > 120 then
            check(false, 'Start+Select did not exit within 120 frames')
            finish()
        end
    end
end, emu.eventType.endFrame)
