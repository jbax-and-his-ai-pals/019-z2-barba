-- Comprehensive Mesen verification of Super Barba Bros. (build/subgames/smb.nes).
local mem = emu.memType.nesMemory
local oam = emu.memType.nesSpriteRam
local ppu = emu.memType.nesPpuDebug
local function r(a) return emu.read(a, mem) end
local function w(a, v) emu.write(a, v, mem) end
local function rp(a) return emu.read(a, ppu) end

local report = assert(io.open(OUTPUT_DIR .. '/smb-barba-gameplay.txt', 'w'))
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

local mmc3Sel = 0
local chrBanks = {[0]=0, [1]=0, [2]=0, [3]=0}
local r6Val, r7Val = 28, 29
local dmcPlays = 0
local dmcDisable4015 = 0
local f5ff0, f5ff1, f5ff2 = nil, nil, nil
local a001Val = nil
local restoreHit = false
local winHookHits = 0
local powerupRoarHits = 0
local axeRoarHits = 0
local bossHitRoarHits = 0
local fireShootHits = 0
local r0Saw = {}
local r1Saw = {}
local r2Saw = {}
local r3Saw = {}

emu.addMemoryCallback(function(_, v)
    mmc3Sel = v & 0x07
end, emu.callbackType.write, 0x8000)

emu.addMemoryCallback(function(_, v)
    if mmc3Sel <= 3 then
        chrBanks[mmc3Sel] = v
        if mmc3Sel == 0 then r0Saw[v] = true
        elseif mmc3Sel == 1 then r1Saw[v] = true
        elseif mmc3Sel == 2 then r2Saw[v] = true
        elseif mmc3Sel == 3 then r3Saw[v] = true
        end
    elseif mmc3Sel == 6 then r6Val = v
    elseif mmc3Sel == 7 then r7Val = v
    end
end, emu.callbackType.write, 0x8001)

emu.addMemoryCallback(function(_, v)
    if (v & 0x10) ~= 0 then
        dmcPlays = dmcPlays + 1
    elseif r(0x7C00) > 0 then
        dmcDisable4015 = dmcDisable4015 + 1
    end
end, emu.callbackType.write, 0x4015)

emu.addMemoryCallback(function(_, v) f5ff0 = v end, emu.callbackType.write, 0x5FF0)
emu.addMemoryCallback(function(_, v) f5ff1 = v end, emu.callbackType.write, 0x5FF1)
emu.addMemoryCallback(function(_, v) f5ff2 = v end, emu.callbackType.write, 0x5FF2)
emu.addMemoryCallback(function(_, v) a001Val = v end, emu.callbackType.write, 0xA001)
emu.addMemoryCallback(function() winHookHits = winHookHits + 1 end, emu.callbackType.exec, 0x7850)
emu.addMemoryCallback(function() powerupRoarHits = powerupRoarHits + 1 end, emu.callbackType.exec, 0xD849)
emu.addMemoryCallback(function() axeRoarHits = axeRoarHits + 1 end, emu.callbackType.exec, 0xDE0E)
emu.addMemoryCallback(function() bossHitRoarHits = bossHitRoarHits + 1 end, emu.callbackType.exec, 0xD75C)
emu.addMemoryCallback(function() fireShootHits = fireShootHits + 1 end, emu.callbackType.exec, 0xB64F)

local phase = 'title'
local triggerWin = false
local startSelHits = 0
emu.addMemoryCallback(function()
    if triggerWin and r(0x7C01) == 28 then
        triggerWin = false
        emu.setState({['cpu.pc'] = 0x8487})
    end
end, emu.callbackType.exec, 0x8000, 0xFFFF)

emu.addMemoryCallback(function()
    if phase == 'start_select' then
        restoreHit = true
    elseif phase == 'exit_wait' then
        restoreHit = true
    end
end, emu.callbackType.exec, 0xE000)

emu.addMemoryCallback(function()
    if phase == 'start_select' then
        startSelHits = startSelHits + 1
    end
end, emu.callbackType.exec, 0x7880)

local function oamTilesInRange(lo, hi, palFilter)
    local found = {}
    for i = 0, 252, 4 do
        local y = emu.read(i, oam)
        local t = emu.read(i + 1, oam)
        local a = emu.read(i + 2, oam)
        if y > 0x08 and y < 0xEC and t >= lo and t <= hi then
            if palFilter == nil or (a & 0x03) == palFilter then
                found[t] = (found[t] or 0) + 1
            end
        end
    end
    return found
end

local function countMap(m)
    local n = 0
    for _ in pairs(m) do n = n + 1 end
    return n
end

local frame = 0
local pStart = 0
local inp = {}
local done = false
local bossHitVerified = false
local sawSwordBeam = false
local sawBomb = false
local sawLinkBoss = false
local savedBossShot = false
local savedLivesShot = false
local axeStart = nil
local lastCastlePos = -1
local castleStuck = 0

local castleActive = false

local function setPhase(p)
    phase = p
    pStart = frame
    castleActive = false
end

local function finish()
    done = true
    report:write(errors == 0 and 'RESULT PASS\n' or 'RESULT FAIL\n')
    report:close()
    emu.stop(errors == 0 and 0 or 1)
end

local function placePowerupOnPlayer(kind)
    w(0x0014, 1)                 -- Enemy_Flag[5] = active
    w(0x001B, 0x2E)              -- Enemy_ID[5] = Powerup
    w(0x0039, kind)              -- 0=Mushroom, 1=Fire Flower
    w(0x0023, 0x06)              -- Enemy_State[5] = active/moving
    w(0x0073, r(0x006D))         -- Enemy_PageLoc[5] = Player_PageLoc
    w(0x008C, r(0x0086))         -- Enemy_X_Position[5] = Player_X
    w(0x00BB, 0x01)              -- Enemy_Y_HighPos[5] = 1 (onscreen!)
    w(0x00D4, r(0x00CE))         -- Enemy_Y_Position[5] = Player_Y
    w(0x03D6, 0x00)              -- Enemy_OffscreenBits[5] = visible
    w(0x06C3, 0x00)              -- $06BE+5 collision bit clear
end

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if done then return end
    frame = frame + 1
    inp = {}

    if phase == 'title' then
        if frame == 45 then
            local p0c1, p0c2, p0c3 = rp(0x3F11), rp(0x3F12), rp(0x3F13)
            check(p0c1 == 0x16 and p0c2 == 0x27 and p0c3 == 0x30,
                string.format('Title sprite pal 0 is Barba ($16/$27/$30), got %02X/%02X/%02X', p0c1, p0c2, p0c3))
            check(chrBanks[0] == 0, 'Title uses Wyrmling R0=0 (got ' .. chrBanks[0] .. ')')
            check(chrBanks[1] == 16, 'Title uses World Enemies R1=16 (got ' .. chrBanks[1] .. ')')
            saveShot('smb_barba_01_title.png')
            setPhase('press_start')
        end

    elseif phase == 'press_start' then
        local elapsed = frame - pStart
        if elapsed < 4 then inp = {start = true} end
        if r(0x0770) == 1 and r(0x0772) < 3 and emu.read(0x021D, oam) == 0x34 and not savedLivesShot then
            savedLivesShot = true
            local blAttr = emu.read(0x021E, oam)
            check((blAttr & 0x40) == 0, string.format('Lives screen Small Barba bottom-left unflipped (attr=%02X)', blAttr))
            saveShot('smb_barba_01b_lives.png')
        end
        if r(0x0770) == 1 and r(0x0772) == 3 and elapsed > 20 then
            setPhase('w1_wyrmling')
        elseif elapsed > 240 then
            check(false, 'Entered 1-1 gameplay (OperMode=' .. r(0x0770) .. ' Task=' .. r(0x0772) .. ')')
            finish()
        end

    elseif phase == 'w1_wyrmling' then
        local elapsed = frame - pStart
        -- Walk right until first Z2 Bot slime is fully onscreen before snapping screenshot
        if elapsed < 120 then inp = {right = true} end
        local bot = oamTilesInRange(0x70, 0x73)
        if (countMap(bot) >= 4 and elapsed >= 60) or elapsed >= 220 then
            local wyrm = oamTilesInRange(0x32, 0x43, 0)
            check(countMap(wyrm) >= 2, 'Wyrmling OAM tiles $32-$43 active (' .. countMap(wyrm) .. ' distinct)')
            check(countMap(bot) >= 2, 'Z2 Bot OAM tiles $70-$73 active (' .. countMap(bot) .. ' distinct)')
            saveShot('smb_barba_02_wyrmling_bot.png')
            setPhase('collect_mushroom')
        end

    elseif phase == 'collect_mushroom' then
        local elapsed = frame - pStart
        if elapsed == 1 then
            placePowerupOnPlayer(0)
        elseif r(0x0756) == 0 then
            w(0x0073, r(0x006D)); w(0x008C, r(0x0086)); w(0x00BB, 1); w(0x00D4, r(0x00CE))
        end
        if r(0x0756) == 1 and r(0x7C00) > 0 then
            if chrBanks[0] == 14 then
                check(powerupRoarHits >= 1, 'Mushroom collection triggered OnPowerupRoar')
                check(dmcPlays >= 1, 'Sampled Barba roar started APU DMC ($4015 bit 4)')
                check(chrBanks[0] == 14, 'Roar uses open-jaw Barba R0=14 (got ' .. chrBanks[0] .. ')')
                saveShot('smb_barba_03_super_roar.png')
                setPhase('wait_super_calm')
            end
        elseif elapsed > 120 then
            check(false, 'Collected Mushroom for Super Barba ($0756=' .. r(0x0756) .. ', roar=' .. r(0x7C00) .. ', R0=' .. chrBanks[0] .. ')')
            setPhase('wait_super_calm')
        end

    elseif phase == 'wait_super_calm' then
        local elapsed = frame - pStart
        if elapsed == 110 then
            check(chrBanks[0] == 2, 'Super Barba idle returns to R0=2 (got ' .. chrBanks[0] .. ')')
            check(dmcDisable4015 == 0, 'SoundEngine preserved DMC bit 4 while roaring (0 cuts)')
            local barba = oamTilesInRange(0x00, 0x2F, 0)
            local trail = oamTilesInRange(0x30, 0x3B, 0)
            local boxW = r(0x04AE) - r(0x04AC)
            local boxH = r(0x04AF) - r(0x04AD)
            check(countMap(barba) >= 4, 'Super Barba 24x32 OAM tiles present (' .. countMap(barba) .. ')')
            check(countMap(trail) >= 8, 'Full Body Barba bend/torso/tail OAM tiles present (' .. countMap(trail) .. ')')
            check(boxW >= 30 and boxH >= 28, string.format('Full Body Barba collision widened & raised (%dx%d)', boxW, boxH))
            saveShot('smb_barba_04_super_barba.png')
            setPhase('test_crouch')
        end

    elseif phase == 'test_crouch' then
        local elapsed = frame - pStart
        inp = {down = true}
        if elapsed == 12 then
            local crouchTiles = oamTilesInRange(0x3C, 0x3D, 0)
            local trail = oamTilesInRange(0x30, 0x3B, 0)
            local boxW = r(0x04AE) - r(0x04AC)
            local boxH = r(0x04AF) - r(0x04AD)
            check(r(0x0714) ~= 0, 'Crouch flag set ($0714=' .. r(0x0714) .. ')')
            check(countMap(crouchTiles) == 2, 'Crouched Barba uses corridor bend $3C/$3D (' .. countMap(crouchTiles) .. ')')
            check(countMap(trail) >= 8, 'Crouched Barba keeps bend/torso/tail (' .. countMap(trail) .. ')')
            check(boxH <= 16 and boxW >= 30, string.format('Crouched hitbox compact vertically & wide (%dx%d)', boxW, boxH))
            saveShot('smb_barba_04a_crouch.png')
            setPhase('collect_flower')
        end

    elseif phase == 'collect_flower' then
        local elapsed = frame - pStart
        if elapsed == 1 then
            placePowerupOnPlayer(1)
            w(0x008C, r(0x0086) + 24)  -- offset 24px right for 4 frames to inspect OAM
        elseif elapsed == 4 then
            local fi = oamTilesInRange(0xEB, 0xEE)
            check(countMap(fi) == 4, 'Z2 Fireball powerup item uses 4 distinct tiles ($EB-$EE, got ' .. countMap(fi) .. ')')
            saveShot('smb_barba_04b_fire_item.png')
            w(0x008C, r(0x0086))       -- move onto Barba to collect
        elseif elapsed > 4 and r(0x0756) < 2 then
            w(0x0073, r(0x006D)); w(0x008C, r(0x0086)); w(0x00BB, 1); w(0x00D4, r(0x00CE))
        end
        if r(0x0756) == 2 and not sawFlowerShake and r(0x7C05) > 0 then
            sawFlowerShake = true
            check(true, 'Fireball pickup started screen shake (W_SHAKE_TIMER=' .. r(0x7C05) .. ')')
        end
        if r(0x0756) == 2 and elapsed > 10 then
            if chrBanks[0] == 12 then
                local p0c1, p0c2, p0c3 = rp(0x3F11), rp(0x3F12), rp(0x3F13)
                check(p0c1 == 0x26 and p0c2 == 0x37 and p0c3 == 0x30,
                    string.format('Inferno Barba palette ($26/$37/$30), got %02X/%02X/%02X', p0c1, p0c2, p0c3))
                check(chrBanks[0] == 12, 'Inferno Barba uses R0=12 (got ' .. chrBanks[0] .. ')')
                check(sawFlowerShake == true, 'Fireball pickup triggered screen shake')
                w(0x7C00, 0); w(0x7C05, 0)
                setPhase('shoot_fireball')
            end
        elseif elapsed > 140 then
            check(false, 'Became Inferno Barba ($0756=' .. r(0x0756) .. ', R0=' .. chrBanks[0] .. ')')
            setPhase('shoot_fireball')
        end

    elseif phase == 'shoot_fireball' then
        local elapsed = frame - pStart
        if elapsed >= 2 and elapsed <= 6 then inp = {b = true} end
        if elapsed == 8 then
            check(fireShootHits >= 1, 'Fire button triggered OnFireballShoot')
            local fb = oamTilesInRange(0x64, 0x65)
            check(countMap(fb) >= 1, 'Flame-crowned Barba fireball OAM ($64/$65) visible')
            saveShot('smb_barba_05_inferno_fireball.png')
            setPhase('showcase_enemies')
        end

    elseif phase == 'showcase_enemies' then
        local elapsed = frame - pStart
        if elapsed <= 4 then
            w(0x0024, 0); w(0x0025, 0)  -- clear player fireballs before enemy showcase
            local baseX = r(0x006D) * 256 + r(0x0086)
            local function setX(slot, dx)
                local wx = baseX + dx
                w(0x006E + slot, math.floor(wx / 256))
                w(0x0087 + slot, wx % 256)
            end
            -- Slot 0: Stalfos (0x00)
            w(0x000F, 1); w(0x0016, 0x00); w(0x001E, 0); setX(0, 24);  w(0x00B6, 1); w(0x00CF, 0xB0); w(0x0046, 2); w(0x03C5, 1)
            -- Slot 1: Red Ironknuckle (0x01)
            w(0x0010, 1); w(0x0017, 0x01); w(0x001F, 0); setX(1, 48);  w(0x00B7, 1); w(0x00D0, 0xB0); w(0x0047, 2); w(0x03C6, 2)
            -- Slot 2: Wizzrobe (0x11)
            w(0x0011, 1); w(0x0018, 0x11); w(0x0020, 0); setX(2, 74);  w(0x00B8, 1); w(0x00D1, 0x70); w(0x0048, 2); w(0x03C7, 1)
            -- Slot 3: Geldarm (0x0D) — $0058+3 = 0x80 sets emerged bit
            w(0x0012, 1); w(0x0019, 0x0D); w(0x0021, 0); setX(3, 100); w(0x00B9, 1); w(0x00D2, 0xB0); w(0x005B, 0x80); w(0x03C8, 1)
            -- Slot 4: Bubble (0x12)
            w(0x0013, 1); w(0x001A, 0x12); w(0x0022, 0); setX(4, 126); w(0x00BA, 1); w(0x00D3, 0x90); w(0x004A, 2); w(0x03C9, 2)
        elseif elapsed == 6 then
            local stalfos = oamTilesInRange(0xA0, 0xAB)
            local ik = oamTilesInRange(0xC0, 0xCB)
            local wiz = oamTilesInRange(0xB0, 0xBB)
            local geld = oamTilesInRange(0x90, 0x93)
            for k, v in pairs(oamTilesInRange(0xBC, 0xBF)) do geld[k] = (geld[k] or 0) + v end
            for k, v in pairs(oamTilesInRange(0xE5, 0xE6)) do geld[k] = (geld[k] or 0) + v end
            local bub = oamTilesInRange(0x96, 0x9D)
            check(countMap(stalfos) >= 2, 'Stalfos OAM tiles ($A0-$AB) rendered (' .. countMap(stalfos) .. ')')
            check(countMap(ik) >= 2, 'Ironknuckle OAM tiles ($C0-$CB) rendered (' .. countMap(ik) .. ')')
            check(countMap(wiz) >= 2, 'Wizzrobe OAM tiles ($B0-$BB) rendered (' .. countMap(wiz) .. ')')
            check(countMap(geld) >= 2, 'Geldarm OAM tiles ($90-$93/$BC-$BF/$E5-$E6) rendered (' .. countMap(geld) .. ')')
            check(countMap(bub) >= 2, 'Bubble OAM tiles ($96-$9D) rendered (' .. countMap(bub) .. ')')
            saveShot('smb_barba_06_z2_enemies.png')
            check(r2Saw[4] and r2Saw[8], 'Crystal Flagpole shimmer toggled R2 between 4 and 8')
            -- Enter Castle 1-4 (World 0, Level 3, AreaPointer $60, AreaType 3)
            w(0x075F, 0x00)
            w(0x075C, 0x03)
            w(0x0760, 0x00)
            w(0x0750, 0x60)
            w(0x074E, 0x03)
            w(0x07A0, 0x01)  -- fast ScreenTimer for lives card
            w(0x0772, 0x00)
            w(0x0770, 0x01)
            setPhase('castle_1_4_run')
        end

    elseif phase == 'castle_1_4_run' then
        local elapsed = frame - pStart
        if r(0x0772) == 3 and chrBanks[1] == 18 then
            if not castleActive then
                castleActive = true
                pStart = frame
                elapsed = 0
            end
            -- Keep Barba invincible & rescue from lava pits/ledges while sprinting to Villainous Link's bridge
            w(0x079E, 0x10)
            if r(0x00CE) > 0xC4 then
                w(0x00CE, 0x70)
                w(0x009F, 0x00)
            end
            local curPos = r(0x071A) * 256 + r(0x0086)
            if curPos == lastCastlePos then
                castleStuck = castleStuck + 1
                if castleStuck == 20 then
                    local ny = r(0x00CE) - 28
                    if ny < 0x48 then ny = 0xB0 end
                    w(0x00CE, ny)
                    w(0x009F, 0x00)
                    castleStuck = 0
                end
            else
                lastCastlePos = curPos
                castleStuck = 0
            end
            inp = {right = true, b = true}
            if (elapsed % 28) < 12 then inp.a = true end
            local foundBowser = false
            for s = 0, 4 do
                if r(0x000F + s) ~= 0 and r(0x0016 + s) == 0x2D then
                    foundBowser = true
                    break
                end
            end
            if foundBowser and r(0x071A) >= 0x07 then
                w(0x7C00, 0)
                setPhase('fight_villainous_link')
            elseif elapsed > 2000 then
                check(false, string.format('Reached Villainous Link in Castle 1-4 (Page=%d X=%02X Y=%02X R1=%d)', r(0x071A), r(0x0086), r(0x00CE), chrBanks[1]))
                setPhase('verify_win_hook')
            end
        elseif elapsed > 240 then
            check(false, 'Castle 1-4 loaded (Task=' .. r(0x0772) .. ' R1=' .. chrBanks[1] .. ')')
            setPhase('verify_win_hook')
        end

    elseif phase == 'fight_villainous_link' then
        local elapsed = frame - pStart
        w(0x079E, 0x10)
        w(0x0756, 0x02)
        w(0x0754, 0x00)
        w(0x0714, 0x00)
        if r(0x00CE) > 0xC4 then w(0x00CE, 0x80); w(0x009F, 0x00) end
        inp = {}
        -- Walk onto the bridge (Page 8, X < $18) so Barba, Villainous Link, Sword Beam, and Bombs are all in frame
        if r(0x006D) < 8 or r(0x0086) < 0x18 then inp.right = true end
        if (elapsed % 8) < 4 then inp.b = true end
        local vl = oamTilesInRange(0xBF, 0xCA, 1)
        if countMap(vl) >= 2 then sawLinkBoss = true end
        local sb = oamTilesInRange(0x80, 0x83)
        if countMap(sb) >= 1 then sawSwordBeam = true end
        local bm = oamTilesInRange(0x84, 0x85)
        if countMap(bm) >= 1 then sawBomb = true end
        if bossHitRoarHits > 0 then bossHitVerified = true end

        if not savedBossShot and sawLinkBoss and sawBomb and sawSwordBeam and elapsed >= 60 then
            saveShot('smb_barba_07_villainous_link.png')
            savedBossShot = true
        end

        if (bossHitVerified and r(0x0483) == 0 and sawBomb and sawSwordBeam and savedBossShot) or elapsed > 360 then
            if not savedBossShot then saveShot('smb_barba_07_villainous_link.png'); savedBossShot = true end
            check(chrBanks[1] == 18, 'Castle uses Villainous Link/Bosses bank R1=18')
            check(r3Saw[10] and r3Saw[11], 'Castle Triforce Axe shimmer toggled R3 between 10 and 11')
            check(sawLinkBoss, 'Villainous Link OAM tiles ($BF-$CA pal 1) rendered')
            check(bossHitVerified, 'Fireball hitting Villainous Link triggered OnBossHitRoar (hits=' .. bossHitRoarHits .. ')')
            check(sawSwordBeam, 'Villainous Link fired Sword Beam ($80-$83)')
            check(sawBomb, 'Villainous Link threw Bombs ($84-$85) in World 1-4')
            setPhase('grab_axe')
        end

    elseif phase == 'grab_axe' then
        local elapsed = frame - pStart
        w(0x079E, 0x10)
        w(0x0754, 0x00)
        if axeRoarHits > 0 and not axeStart then axeStart = frame end
        if not axeStart then
            inp = {right = true}
            if r(0x00CE) > 0xB8 then w(0x00CE, 0x80); w(0x009F, 0x00) end
            if (elapsed % 30) < 10 then inp.a = true end
        end
        local fairy = oamTilesInRange(0xA0, 0xAB, 3)
        if axeStart and ((countMap(fairy) >= 6 and (frame - axeStart) > 120) or (frame - axeStart) > 220) then
            check(axeRoarHits >= 1, 'Triforce Axe triggered OnAxeRoar')
            check(countMap(fairy) >= 2, 'Caged Fairy OAM tiles ($A0-$AB pal 3) rendered (' .. countMap(fairy) .. ')')
            saveShot('smb_barba_08_caged_fairy.png')
            -- Ensure debounce expired ($7FFF == $3C) then verify Start+Select exit trampoline
            w(0x7FFF, 0x3C)
            f5ff0, f5ff1, f5ff2, r6Val, r7Val, a001Val = nil, nil, nil, nil, nil, nil
            restoreHit = false
            setPhase('start_select')
        elseif elapsed > 480 then
            check(false, string.format('Touched Triforce Axe in Castle 1-4 (axeRoarHits=%d pg=%d x=%02X y=%02X)', axeRoarHits, r(0x006D), r(0x0086), r(0x00CE)))
            setPhase('verify_win_hook')
        end

    elseif phase == 'start_select' then
        inp = {start = true, select = true}
        local elapsed = frame - pStart
        if restoreHit or elapsed > 60 then
            check(startSelHits >= 1, 'Start+Select triggered SMB_RETURN ($7880)')
            check(f5ff0 == 1 and f5ff1 == 0 and f5ff2 == 0, 'Start+Select restored outer banks ($5FF0=1, $5FF1=0, $5FF2=0)')
            check(r6Val == 0x0C and r7Val == 0x0D, 'Start+Select restored R6=$0C, R7=$0D')
            check(a001Val == 0x80, 'Start+Select unlocked $A001=$80')
            check(restoreHit, 'Start+Select trampoline reached $E000')
            -- Re-enter SMB_BOOT ($7900) in WRAM bank 3 ($A3) to verify win hook cleanly
            w(0xA001, 0xA3)
            emu.setState({['cpu.pc'] = 0x7900})
            restoreHit = false
            f5ff0, f5ff1, f5ff2, r6Val, r7Val = nil, nil, nil, nil, nil
            setPhase('win_reenter')
        end

    elseif phase == 'win_reenter' then
        if frame - pStart == 30 then
            setPhase('verify_win_hook')
        end

    elseif phase == 'verify_win_hook' then
        if frame - pStart == 1 then
            triggerWin = true
            setPhase('exit_wait')
        end

    elseif phase == 'exit_wait' then
        local elapsed = frame - pStart
        if restoreHit or elapsed > 60 then
            check(winHookHits >= 1, 'SMB_WIN_HOOK ($7850) executed at $8487')
            check(r(0x648F) == 0x4D, string.format('$648F == $4D win magic (got %02X)', r(0x648F)))
            check(f5ff0 == 1 and f5ff1 == 0 and f5ff2 == 0, 'SMB_RETURN restored outer banks ($5FF0=1, $5FF1=0, $5FF2=0)')
            check(r6Val == 0x0C and r7Val == 0x0D, 'SMB_RETURN restored R6=$0C, R7=$0D')
            check(restoreHit, 'Clean exit trampoline reached $E000')
            finish()
        end
    end
end, emu.eventType.endFrame)
