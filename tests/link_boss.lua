-- Verify Palace 6 "Lava Link" boss: Link palette, Link sprite art, and Spear (05) sword beams.
dofile(TEST_DIR..'/newgame.lua')
local frame=0
local mem=emu.memType.nesMemory
local pal=emu.memType.nesPaletteRam
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/link_boss.txt','w'))
local errors=0
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n')
    if not ok then errors=errors+1 end
end

local sawBoss=false
local sawSpear=false
local sawFlame=false
-- Boss hits (hit timer set to $30 on a $21 slot) versus Link hurt SFX ($E9 = 1) written by LavaLinkHurt ($A795-$A7A8).
local bossHits,hurtSfx=0,0
emu.addMemoryCallback(function(addr,value)
    -- Only the damage routine's store counts; DEC's read-modify-write also writes the old $30 back.
    local pc=emu.getState()['cpu.pc']
    if value==0x30 and r(0xA1+addr-0x040E)==0x21 and pc>=0xE700 and pc<0xE800 then bossHits=bossHits+1 end
end,emu.callbackType.write,0x040E,0x0413)
emu.addMemoryCallback(function(addr,value)
    local pc=emu.getState()['cpu.pc']
    if value==1 and pc>=0xA795 and pc<0xA7AA then hurtSfx=hurtSfx+1 end
end,emu.callbackType.write,0xE9,0xE9)
local bossPaletteOk=false
local pal1Ok=true
local shotBeamPng=false
local bossSlot=nil
local bossStartHp=nil
local bossMinHp=255
local entranceRoars=0
local sampled=LABELS.RoarAudio~=nil
local cameraLockedAt,landedAt,cameraLockY,lastY
local airborneAtCameraLock,keptClimbing,smoothDescent=false,false,true
local centeredAt,centeredInAir,heldCenter=nil,false,true
local platformX=0x188 -- screen x $88 anchor plus $10 to Barba's center
local lockedAt,roarAt,drainedAt,completedAt,risingAt
local roarRequestedAt,settledOnLanding=nil,true
local lockedX,lockedY,releasedAt,playerUpdateAt,movedAt,musicAt
local heldPosition=true
local roarTrailSeen=false
local shakeFrames,shakeLeft,shakeRight=0,false,false
local matchedBands,settledAtRise=true,false
local firstShakeAt,lastShakeAt
local quietFrames=0
local function shakeOffset()
    local camera=(r(0x746)&1)*256+r(0xFD)
    local irqCamera=(r(0x64E0)&1)*256+r(0x64DC)
    return (irqCamera-camera+256)%512-256
end
local hudReference,hudShakeFrames,spriteShakeFrames=nil,0,0
local scopedShake,shakeWrites=true,0
local lavaIrqCount,lavaIrqMin,lavaIrqMax=0,999,-1
emu.addMemoryCallback(function(_,value)
    if risingAt and (value&0x20)~=0 then
        local sl=emu.getState()['ppu.scanline']
        lavaIrqCount=lavaIrqCount+1
        if sl<lavaIrqMin then lavaIrqMin=sl end
        if sl>lavaIrqMax then lavaIrqMax=sl end
    end
end,emu.callbackType.write,0x2001,0x2001)
local dmaSprites={}
emu.addMemoryCallback(function()
    if r(0x728)~=2 then return end
    dmaSprites={}
    for o=0,0x2C,4 do
        local y,tile,attr,x=r(0x200+o),r(0x201+o),r(0x202+o),r(0x203+o)
        if y<0xF0 and tile~=0xF5 and x>=4 and x<252 then
            dmaSprites[#dmaSprites+1]={o,y,tile~1,attr,x}
        end
    end
end,emu.callbackType.write,0x4014)
emu.addMemoryCallback(function()
    shakeWrites=shakeWrites+1
    scopedShake=scopedShake and roarAt~=nil and not risingAt
        and r(0x707)==4 and r(0x56B)==6 and r(0x561)==0x3A and r(0x728)==2
end,emu.callbackType.exec,assert(LABELS.ShakeLavaHud6))
emu.addMemoryCallback(function()
    if not lockedAt or playerUpdateAt then return end
    -- $903A is also used in other banks. The player update returns to $D4F6.
    local sp=emu.getState()['cpu.sp']
    if r(0x100+((sp+1)&0xFF))==0xF5 and r(0x100+((sp+2)&0xFF))==0xD4 then
        playerUpdateAt=frame+1
    end
end,emu.callbackType.exec,0x903A)
local roarRequestAddr=sampled and 0x5EE or 0x5F0
local roarRequestValue=sampled and 0x48 or 0x30
emu.addMemoryCallback(function(_,value)
    if lockedAt and not roarRequestedAt and value==roarRequestValue then
        roarRequestedAt=frame+1
    end
end,emu.callbackType.write,roarRequestAddr,roarRequestAddr)
emu.addMemoryCallback(function(_,value)
    if frame<=1000 then return end
    if value==0x88 then
        entranceRoars=entranceRoars+1
        roarAt=roarAt or frame
    elseif roarAt and value==0x98 then
        drainedAt=drainedAt or frame
    elseif drainedAt and value==0x10 then
        completedAt=completedAt or frame
    end
end,emu.callbackType.write,0x5EE)

emu.addEventCallback(function()
    local buttons=newGameInput(frame)
    if lockedAt and not movedAt then
        buttons.right=true
        buttons.a=(frame%4<2)
    elseif frame>1000 and not lockedAt then
        buttons.right=not centeredAt
        buttons.left=centeredAt~=nil
        -- Hop up the approach ledges, then take the high jump off the lava.
        buttons.a=r(0x3B)*256+r(0x4D)>=0xDA and frame%36<27
    end
    -- Wait for Lava Link to fire a sword beam first, then hop/aim at Lava Link's head.
    if sawSpear and bossSlot~=nil then
        local bx=r(0x4E+bossSlot)
        local by=r(0x2A+bossSlot)
        local px=r(0x4D)
        local py=r(0x29)
        if bx<px-16 then buttons.left=(frame%8<3)
        elseif bx>px+16 then buttons.right=(frame%8<3) end
        buttons.a=buttons.a or (py>by+8 and frame%40<20)
        buttons.b=(math.abs(py-by)<=20 and frame%10<3)
    end
    emu.setInput(buttons,0)
end,emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        w(0x707,4);w(0x706,2);w(0x769,4);w(0x561,0x3A)
        w(0x568,5);w(0x56B,6);w(0x56C,1);w(0x701,0);w(0x75C,0);w(0x704,0)
        w(0x736,0);w(0x73D,0);w(0x726,1)
        w(0x774,255);w(0x784,8);w(0x777,8);w(0x778,8)
    end
    if frame>1200 then
        if frame%60==0 then w(0x774,255) end
        for slot=0,5 do
            local eid=r(0xA1+slot)
            if r(0xB6+slot)>0 and (eid==0x21 or eid==0x22) then
                sawBoss=true
                bossSlot=slot
                local hp=r(0xC2+slot)
                if bossStartHp==nil and hp>0 and hp<255 then bossStartHp=hp end
                if hp<bossMinHp then bossMinHp=hp end
            end
        end
        for p=0,5 do
            local kind=r(0x87+p)
            if kind==0x05 then
                sawSpear=true
                if not shotBeamPng then
                    shotBeamPng=true
                    screenshot('link_boss_beam')
                    neckPieces=0
                    for o=0,63 do
                        local b=0x200+o*4
                        local y,tl,at,x=r(b),r(b+1),r(b+2),r(b+3)
                        if y<0xEF and (at%4)==3 then
                            if tl==0xA1 then neckPieces=neckPieces+1 end
                            report:write(string.format('oam%02d y=%3d x=%3d tile=%02X attr=%02X',o,y,x,tl,at)..string.char(10))
                        end
                    end

                end
            elseif kind==0x04 then
                sawFlame=true
            end
        end
        if r(0x0499)>=2 then
            local c1,c2,c3=emu.read(0x1D,pal),emu.read(0x1E,pal),emu.read(0x1F,pal)
            if c1==0x18 and c2==0x36 and c3==0x2A then
                bossPaletteOk=true
            end
            local p1a,p1b,p1c=emu.read(0x15,pal),emu.read(0x16,pal),emu.read(0x17,pal)
            if p1a~=0x16 or p1b~=0x27 or p1c~=0x30 then
                pal1Ok=false
            end
        end
    end
    if frame>1000 and r(0x736)==11 and r(0x728)~=0 and not risingAt then
        local x,y=r(0x3B)*256+r(0x4D),r(0x29)
        local grounded=r(0x0479)==0
        if not cameraLockedAt then
            cameraLockedAt,cameraLockY=frame,y
            airborneAtCameraLock=not grounded
        end
        if grounded then landedAt=landedAt or frame end
        if not landedAt then
            keptClimbing=keptClimbing or y<=cameraLockY-16
            smoothDescent=smoothDescent and (not lastY or y-lastY<=6)
        end
        lastY=y
        if x==platformX and not centeredAt then
            centeredAt,centeredInAir=frame,not grounded
        end
        if centeredAt then heldCenter=heldCenter and x==platformX end
        if not lockedAt and r(0x728)==2 then
            lockedAt,lockedX,lockedY=frame,x,y
            screenshot('link_boss_platform')
        end
        if lockedAt then
            heldPosition=heldPosition and x==lockedX and y==lockedY
            if r(0x728)==1 then releasedAt=releasedAt or frame end
            if not roarRequestedAt then
                settledOnLanding=settledOnLanding and grounded and r(0x64FA)==0 and shakeOffset()==0
            end
        end
        if not sampled then
            if r(0x5F0)~=0 then roarAt=roarAt or frame
            elseif roarAt then completedAt=completedAt or frame end
        end
        if r(0x499)~=0 then risingAt=frame end
        if roarAt then
            if sampled and r(0x5EE)&0x88==0x88 and r(0x5FA)==72 and r(0x220)<0xF0 then
                local y=r(0x218)
                local near=trailSlots().near
                roarTrailSeen=roarTrailSeen or r(0x6518)==y and r(0x6519)==0x35 and near~=nil and r(near)==y
            end
            local offset=shakeOffset()
            if offset~=0 then
                firstShakeAt=firstShakeAt or frame
                lastShakeAt=frame
                shakeFrames=shakeFrames+1
                shakeLeft=shakeLeft or offset<0
                shakeRight=shakeRight or offset>0
                matchedBands=matchedBands and math.abs(offset)<=4 and r(0x64D7)==2
                    and r(0x64DC)==r(0x64DD) and r(0x64E0)==r(0x64E1)
                local pixels=emu.getScreenBuffer()
                local hudMatches=hudReference~=nil
                local hudMoves=false
                for y=2,26 do
                    for x=16,239 do
                        local i=y*256+x+1
                        hudMatches=hudMatches and pixels[i]==hudReference[i+offset]
                        hudMoves=hudMoves or (hudReference and pixels[i]~=hudReference[i])
                    end
                end
                if hudMatches and hudMoves then hudShakeFrames=hudShakeFrames+1 end
                local spritesMatch=#dmaSprites>=4
                local oam=emu.memType.nesSpriteRam
                for _,sprite in ipairs(dmaSprites) do
                    local o,y,tile,attr,x=table.unpack(sprite)
                    spritesMatch=spritesMatch and emu.read(o,oam)==y and emu.read(o+1,oam)==tile
                        and emu.read(o+2,oam)==attr and emu.read(o+3,oam)==x-offset
                end
                if spritesMatch then spriteShakeFrames=spriteShakeFrames+1 end
            elseif shakeFrames==0 then
                hudReference=emu.getScreenBuffer()
            else
                quietFrames=quietFrames+1
            end
        end
    end
    -- VBlank has already latched the scroll and sprites when the boss logic
    -- releases control. The first rendered rise uses the next frame's scroll.
    if risingAt and frame==risingAt+1 then settledAtRise=shakeOffset()==0 end
    if cameraLockedAt then
        if r(0x07FB)==0x08 then musicAt=musicAt or frame end
        if releasedAt and (r(0x3B)*256+r(0x4D)~=lockedX or r(0x29)~=lockedY) then
            movedAt=movedAt or frame
        end
    end
    if frame==1600 then
        screenshot('link_boss_rising')
    end
    if frame==2500 then
        local c1,c2,c3=emu.read(0x1D,pal),emu.read(0x1E,pal),emu.read(0x1F,pal)
        local p1a,p1b,p1c=emu.read(0x15,pal),emu.read(0x16,pal),emu.read(0x17,pal)
        report:write(string.format('sp_pal3=%02X %02X %02X sp_pal1=%02X %02X %02X hp_start=%s hp_min=%d\n',
            c1,c2,c3,p1a,p1b,p1c,tostring(bossStartHp),bossMinHp))
        check(sawBoss,'Palace 6 boss (0x21) spawned')
        check(bossPaletteOk,'Sprite palette 3 switched to Link (18 36 2A)')
        report:write(string.format('intro camera=%s center=%s land=%s lock=%s roar=%s drain=%s complete=%s release=%s rise=%s music=%s move=%s shake=%s-%s (%d frames)\n',
            tostring(cameraLockedAt),tostring(centeredAt),tostring(landedAt),tostring(lockedAt),tostring(roarAt),
            tostring(drainedAt),tostring(completedAt),tostring(releasedAt),
            tostring(risingAt),tostring(musicAt),tostring(movedAt),
            tostring(firstShakeAt),tostring(lastShakeAt),shakeFrames))
        check(airborneAtCameraLock and keptClimbing and smoothDescent and landedAt and landedAt==lockedAt,
            'Barba follows the normal vertical arc of the high lava jump and freezes on landing')
        check(centeredInAir and heldCenter and lockedAt and centeredAt<lockedAt and lockedY==0xA0,
            'Barba holds the platform center against Left input while airborne and lands on the stone')
        check(lockedAt and settledOnLanding and roarRequestedAt and roarRequestedAt-lockedAt==6,
            string.format('Barba stays grounded with the screen settled for six frames before starting the roar (request=%s, settled=%s)',
                tostring(roarRequestedAt),tostring(settledOnLanding)))
        -- A sampled audio write occurs before endFrame advances the frame counter.
        local playbackAt=roarAt and roarAt+(sampled and 1 or 0)
        check(playbackAt and roarRequestedAt and playbackAt>=roarRequestedAt and playbackAt-roarRequestedAt<=2,
            'the entrance roar plays after the landing beat')
        check(lastShakeAt and risingAt and risingAt-lastShakeAt==30 and quietFrames==30,
            'Lava Link waits through 30 settled frames after the roar before rising')
        check(heldPosition and releasedAt and releasedAt==risingAt,
            'walk and jump inputs cannot move Barba before the rise')
        check(movedAt and releasedAt and playerUpdateAt==releasedAt+1 and movedAt-releasedAt<=6,
            string.format('Barba moves again as soon as the fight starts (player update=%s)',tostring(playerUpdateAt)))
        check(musicAt and releasedAt and musicAt>=releasedAt and musicAt-releasedAt<=2,
            'boss theme waits until Lava Link rises')
        check(firstShakeAt and roarAt and firstShakeAt>=roarAt and firstShakeAt-roarAt<=2
            and completedAt and lastShakeAt==completedAt+1 and shakeFrames==lastShakeAt-firstShakeAt+1,
            'shake covers the full entrance roar and ends before the pause')
        check(shakeLeft and shakeRight and matchedBands and settledAtRise,
            'both playfield bands shake together and stay settled as Lava Link rises')
        check(hudShakeFrames==shakeFrames and spriteShakeFrames==shakeFrames,
            string.format('the rendered HUD and Barba sprites move with the playfield (HUD %d, sprites %d)',
                hudShakeFrames,spriteShakeFrames))
        check(scopedShake and shakeWrites==shakeFrames,'full-screen shake runs only during the Palace 6 entrance roar')
        check(not sampled or entranceRoars==1,'Barba roars once before Lava Link and never during later rises')
        check(not sampled or roarTrailSeen,'entrance roar draws the rounded bend and lowered tail')
        check(pal1Ok,'Sprite palette 1 preserved for health/fireballs (16 27 30)')
        check(sawSpear,'Lava Link spawned Spear/sword-beam projectile (05)')
        check(neckPieces~=nil and neckPieces>=1 and neckPieces<=5,'Lava Link neck stops at the lava (1-5 pieces, got '..tostring(neckPieces)..')')
        check(not sawFlame,'Lava Link did not spawn Barba flame (04)')
        check(bossStartHp~=nil and bossMinHp<bossStartHp,'Barba fireballs damaged Lava Link')
        check(bossHits>0 and hurtSfx==bossHits,'Link hurt sound once per boss hit (hits '..bossHits..', sounds '..hurtSfx..')')
        check(lavaIrqCount>0 and lavaIrqMin==207 and lavaIrqMax==207,
            string.format('lava red-emphasis IRQ stays on scanline 207 during fight (count=%d, min=%d, max=%d)',
                lavaIrqCount,lavaIrqMin,lavaIrqMax))
        report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
        report:close()
        stopScenario(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
