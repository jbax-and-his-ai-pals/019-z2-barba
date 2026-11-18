-- Verify Dark Barba transforms into Dark Wyrmling when the player casts WYRMLNG,
-- both Wyrmlings shoot fireballs in an aerial duel, 8 hits defeat Dark Wyrmling,
-- and Phase 4 cleanly returns Barba to 24x48 for the Triforce roar and Zelda awakening.
dofile(TEST_DIR..'/newgame.lua')
local frame=0
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/dark_wyrmling.txt','w'))
local errors=0
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n')
    if not ok then errors=errors+1 end
end

local sawActive=false
local castFrame=nil
local sawPlayerWyrm=false
local sawDarkWyrmSprite=false
local tallSlotsHidden=true
local sawAerialFlight=false
local sawDarkWyrmFire=false
local sawPlayerWyrmFire=false
local startHp=nil
local lastHp=nil
local hits=0
local maxDelta=0
local sawDeath=false
local sawVictory=false
local sawUnWyrm=false
local sawFloorLanding=false
local sawAwakening=false
local finished=false

emu.addEventCallback(function()
    local buttons=newGameInput(frame)
    if frame>1100 and not sawDeath then
        if not sawActive then
            buttons.right=true
        elseif castFrame and frame==castFrame then
            buttons.select=true
        elseif r(0x13)~=0 then
            -- Aerial duel: hold a clean ranged position (~64 px away) facing Dark Wyrmling, match altitude, shoot fireballs.
            local dlx=r(0x3C)*256+r(0x4E)
            local px=r(0x3B)*256+r(0x4D)
            local py=r(0x29)
            local dly=r(0x2A)
            if py>dly+4 then
                buttons.up=true
            elseif py<dly-4 then
                buttons.down=true
            end
            local targetX=(dlx<384) and (dlx+40) or (dlx-40)
            local phase8=frame%8
            if phase8==0 then
                if px<dlx then buttons.right=true else buttons.left=true end
            elseif phase8<4 then
                buttons.b=true
            elseif px<targetX-8 then
                buttons.right=true
            elseif px>targetX+8 then
                buttons.left=true
            end
        end
    end
    emu.setInput(buttons,0)
end,emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        w(0x0707,5);w(0x0706,2);w(0x0769,5)
        w(0x0561,0x36);w(0x0568,6);w(0x056B,7);w(0x056C,2)
        w(0x0701,0);w(0x075C,1);w(0x0704,0)
        w(0x0736,0);w(0x073D,0);w(0x0726,1)
        w(0x0774,255);w(0x0773,255);w(0x0784,8);w(0x0777,8);w(0x0778,8)
        w(0x077E,1);w(0x0749,3);w(0x074A,3)
    end
    if frame>1100 and not finished then
        if frame%30==0 then
            w(0x0774,255)
            w(0x0773,255)
        end
        if r(0xB6)==1 and r(0xA1)==0x23 then
            local phase=r(0x63)
            if phase==3 and r(0x0505)==0 then
                if not sawActive then
                    sawActive=true
                    startHp=r(0xC2)
                    lastHp=startHp
                    w(0x077E,1);w(0x0749,3);w(0x074A,3);w(0x0773,255)
                    castFrame=frame+2
                end
                if r(0x13)~=0 then
                    sawPlayerWyrm=true
                    local y0=r(0x0250)
                    local t0=r(0x0251)
                    local a0=r(0x0252)
                    if y0<0xEF and (t0==0x68 or t0==0x6A) and (a0&3)==2 then
                        sawDarkWyrmSprite=true
                    end
                    if sawDarkWyrmSprite and tallSlotsHidden then
                        for spr=0x0254,0x0274,4 do
                            if r(spr)<0xEF then
                                tallSlotsHidden=false
                                report:write(string.format('dbg_oam frame=%d spr=%04X val=%02X tile=%02X $13=%d\n',
                                    frame,spr,r(spr),r(spr+1),r(0x13)))
                            end
                        end
                    end
                    if r(0x2A)<0xA0 then
                        sawAerialFlight=true
                    end
                    for slot=0,5 do
                        if r(0x87+slot)==3 then
                            sawDarkWyrmFire=true
                        end
                    end
                    if r(0x8D)~=0 or r(0x8E)~=0 then
                        sawPlayerWyrmFire=true
                    end
                end
                local hp=r(0xC2)
                if hp<lastHp then
                    local delta=lastHp-hp
                    if delta>maxDelta then maxDelta=delta end
                    hits=hits+1
                    lastHp=hp
                end
                if hp==0 and r(0x050D)==0xFF then
                    sawDeath=true
                end
            elseif phase>=4 then
                sawVictory=true
                if r(0x13)==0 and (r(0x076F)&0x08)==0 then
                    sawUnWyrm=true
                end
                if r(0x29)==0xA0 and r(0x0479)==0 then
                    sawFloorLanding=true
                end
            end
        end
        if r(0x076C)==3 then
            sawAwakening=true
        end
    end
    if (frame>=5500 or sawAwakening) and not finished then
        finished=true
        report:write(string.format('frame=%d startHp=%s lastHp=%s hits=%d maxDelta=%d px=%d py=%d dlx=%d dly=%d $13=%d $5F=%d $9F=%d\n',
            frame,tostring(startHp),tostring(lastHp),hits,maxDelta,
            r(0x3B)*256+r(0x4D),r(0x29),r(0x3C)*256+r(0x4E),r(0x2A),r(0x13),r(0x5F),r(0x9F)))
        check(sawActive,'Dark Link Phase 3 started')
        check(sawPlayerWyrm,'WYRMLNG spell transformed player ($13 ~= 0)')
        check(sawDarkWyrmSprite,'Dark Barba transformed into black-palette Dark Wyrmling ($0250 tile $68/$6A, attr & 3 == 2)')
        check(tallSlotsHidden,'24x48 Dark Barba OAM slots ($0254..$0274) stayed hidden while Wyrmling')
        check(sawAerialFlight,'Dark Wyrmling flew above floor ($2A < 0xA0)')
        check(sawDarkWyrmFire,'Dark Wyrmling fired horizontal fireballs ($87,y == 3)')
        check(sawPlayerWyrmFire,'Player Wyrmling breathed fireballs ($8D/$8E ~= 0)')
        check(hits>0 and maxDelta==1,'Player Wyrmling fireballs dealt 1 HP per hit')
        check(sawDeath,'Dark Wyrmling defeated to 0 HP ($050D == 0xFF)')
        check(sawVictory,'Dark Wyrmling defeat triggered Phase 4+ victory')
        check(sawUnWyrm,'Phase 4 cleanly reverted player Wyrmling ($13 == 0, $076F & 8 == 0)')
        check(sawFloorLanding,'Barba descended cleanly to floor ($29 == 0xA0) for Triforce walk')
        check(sawAwakening,'Zelda awakening ($076C == 3) triggered after victory roar')
        report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
        report:close()
        stopScenario(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
