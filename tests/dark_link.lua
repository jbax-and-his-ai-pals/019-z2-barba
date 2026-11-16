-- Verify Dark Link in Great Palace ($36) takes 1-HP sword-like damage from fireballs
-- with proper hurt/death state ($0509/$050D) and can be defeated.
dofile(TEST_DIR..'/newgame.lua')
local frame=0
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/dark_link.txt','w'))
local errors=0
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..string.char(10))
    if not ok then errors=errors+1 end
end

local sawTrigger=false
local sawActive=false
local startHp=nil
local lastHp=nil
local hits=0
local maxDelta=0
local sawHurtTimer=false
local sawDeath=false
local sawTallDarkBarba=false
local sawShadowPalette=false
local sawVictory=false
local stompCheckFrame=nil
local stompSurvived=false
local finished=false

emu.addEventCallback(function()
    local buttons=newGameInput(frame)
    if frame>1100 then
        if not sawActive then
            -- Walk right past Thunderbird into Dark Link's trigger page.
            buttons.right=true
        elseif not sawDeath then
            -- Face Dark Link and fire volleys while keeping Barba alive.
            local dlx=r(0x4E)
            local px=r(0x4D)
            local dlPage=r(0x3C)
            local pPage=r(0x3B)
            local pWorld=pPage*256+px
            local dlWorld=dlPage*256+dlx
            if pWorld<dlWorld-24 then
                buttons.right=true
            elseif pWorld>dlWorld+24 then
                buttons.left=true
            end
            buttons.b=(frame%8<3)
        end
    end
    emu.setInput(buttons,0)
end,emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        -- Great Palace room $36 (same setup as great-palace checkpoint, starting on page 1 near Dark Link trigger)
        w(0x707,5);w(0x706,2);w(0x769,5)
        w(0x561,0x36);w(0x568,6);w(0x56B,7);w(0x56C,2)
        w(0x701,0);w(0x75C,1);w(0x704,0)
        w(0x736,0);w(0x73D,0);w(0x726,1)
        w(0x774,255);w(0x784,8);w(0x777,8);w(0x778,8)
    end
    if frame>1100 then
        if frame%30==0 then w(0x774,255) end
        if r(0xB6)==1 and r(0xA1)==0x23 then
            sawTrigger=true
            local phase=r(0x63)
            if phase==3 and r(0x0505)==0 then
                if not sawActive then
                    sawActive=true
                    startHp=r(0xC2)
                    lastHp=startHp
                end
                local hp=r(0xC2)
                if hp<lastHp then
                    local delta=lastHp-hp
                    if delta>maxDelta then maxDelta=delta end
                    hits=hits+1
                    lastHp=hp
                end
                if hp<=4 and hp>0 and not stompCheckFrame and r(0x0509)==0 and r(0x050D)==0 then
                    -- Position Barba descending onto Dark Barba to verify BarbaStomp does not kill him.
                    stompCheckFrame=frame
                    w(0x0479,1);w(0x057D,2)
                    w(0x29,(r(0x2A)-0x10)%256)
                    w(0x4D,r(0x4E));w(0x3B,r(0x3C))
                elseif stompCheckFrame and frame==stompCheckFrame+1 then
                    stompSurvived=(r(0xB6)==1 and r(0xA1)==0x23 and r(0xC2)>0)
                end
                if r(0x0509)>0 and r(0x050D)==0x18 then
                    sawHurtTimer=true
                end
                if hp==0 and r(0x050D)==0xFF then
                    sawDeath=true
                end
                if r(0x81)<6 and r(0x026C)==(r(0x2A)-0x10) then
                    sawTallDarkBarba=true
                    if r(0x0753)==2 and (r(0x0252)&3)==2 then
                        sawShadowPalette=true
                    end
                end
            elseif phase>=4 then
                sawVictory=true
            end
        end
    end
    if (frame==3200 or sawVictory) and not finished then
        finished=true
        local prg=emu.memType.nesPrgRom
        local tilesMatch=LABELS and LABELS.DarkBarbaTiles and LABELS.BarbaTallTiles
        if tilesMatch then
            for i=0,116 do
                local a=emu.read(5*0x4000+LABELS.DarkBarbaTiles-0x8000+i,prg)
                local b=emu.read(LABELS.BarbaTallTiles-0x8000+i,prg)
                if a~=b then tilesMatch=false break end
            end
        end
        report:write(string.format('frame=%d startHp=%s lastHp=%s hits=%d maxDelta=%d\n',
            frame,tostring(startHp),tostring(lastHp),hits,maxDelta))
        check(sawTrigger,'Dark Link (0x23) spawned in Great Palace')
        check(sawActive and startHp==8,'Dark Link fight started with 8 HP')
        check(hits>=1,'Fireballs damaged Dark Link')
        check(maxDelta==1,'Each fireball hit dealt exactly 1 HP damage (maxDelta='..maxDelta..')')
        check(sawHurtTimer,'Dark Link entered hurt state ($0509 > 0, $050D == 0x18)')
        check(sawDeath,'Dark Link reached 0 HP with death state ($050D == 0xFF)')
        check(stompSurvived,'Descending onto 4-HP Dark Barba does not stomp-kill him')
        check(sawTallDarkBarba,'Dark Barba renders 24x48 tall top row ($026C at Y - 16)')
        check(sawShadowPalette,'Dark Barba uses shadow palette 2 ($0753 == 2, OAM attr & 3 == 2)')
        check(tilesMatch,'DarkBarbaTiles matches BarbaTallTiles across all 117 tile bytes')
        check(sawVictory,'Dark Link defeat triggered victory phase ($63 >= 4)')
        report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..string.char(10))
        report:close()
        stopScenario(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
