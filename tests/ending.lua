-- Verify the Barba Edition ending sequence:
-- 1) 24x48 Barba (no Link chimera tiles $E0-$E6) + Zelda OAM sprites
-- 2) Updated Zelda wake-up dialogue ("BARBA? HOLY SHIT! THE FUCK ARE YOU DOING HERE?")
-- 3) 20-entry credits including BARBA EDITION / JERBTRUNDLES and LAVA RECLAIMED.
-- 4) Pressing Start on the final screen starts New Game+ ($07A0 == 1)
-- 5) Both behind-curtain fireball poses reach Zelda, then disappear as she turns to ash.
dofile(TEST_DIR..'/newgame.lua')
local frame=0
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/ending.txt','w'))
local errors=0
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..string.char(10))
    if not ok then errors=errors+1 end
end

local triggered=false
local sawBarbaWait=false
local sawBarbaAndZelda=false
local endingTrailInFront,endingTrailBehind=false,false
local sawNoLinkTiles=true
local sawCleanPaletteInS2=true
local sawFireballPose={}
local fireballReachedZelda=false
local sawZeldaAsh=false
local sawNoCloserStep=true
local maxCreditsIndex=0
local sawReplayWait=false
local sawNewGamePlus=false
local finished=false

emu.addEventCallback(function()
    local buttons=newGameInput(frame)
    if sawReplayWait and r(0x0761)==12 then
        buttons.start=true
    end
    emu.setInput(buttons,0)
end,emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 and not triggered then
        triggered=true
        w(0x0736,0x08)
        w(0x076C,0x03)
        w(0x0761,0x00)
        w(0x0033,0x00)
        w(0x0037,0x00)
    end
    if triggered and not finished then
        local s=r(0x0761)
        if s>=1 and s<=8 then
            local trail=true
            for i,tile in ipairs({0x15,0x3F,0x45,0x31}) do
                local slot=0x6548+4*(i-1)
                trail=trail and r(slot)==0xC0 and r(slot+1)==tile
                    and r(slot+2)==r(0x6526) and r(slot+3)==0x60-i*8
            end
            if s<6 then endingTrailInFront=endingTrailInFront or trail and r(0x6526)==0x40 end
            if s>=6 then endingTrailBehind=endingTrailBehind or trail and r(0x6526)==0x60 end
        end
        if s>=1 and s<=5 then
            for i=4,15 do
                local t=r(0x0201+i*4)
                if t==0xE0 or t==0xE2 or t==0xE4 or t==0xE6 then
                    sawNoLinkTiles=false
                end
            end
            if r(0x0211)==0x04 and r(0x0215)==0x02 and r(0x0219)==0x00 then
                sawBarbaWait=true
            end
            if s==2 and r(0x0211)==0x04 then
                local f=assert(io.open(OUTPUT_DIR..'/ending_s2.png','wb'))
                f:write(emu.takeScreenshot());f:close()
            end
            if s==5 and r(0x0231)==0xD8 and r(0x0235)==0xDA and r(0x0239)==0xDC and r(0x023D)==0xDE then
                sawBarbaAndZelda=true
                if r(0x0033)==0x00 then
                    local f=assert(io.open(OUTPUT_DIR..'/ending_text.png','wb'))
                    f:write(emu.takeScreenshot());f:close()
                end
            end
        elseif s>=6 and s<=8 then
            if r(0x0213)~=0x60 or r(0x0217)~=0x68 or r(0x021B)~=0x70 then
                sawNoCloserStep=false
            end
            local tail=r(0x0241)
            local x,y=r(0x0243),r(0x0240)
            if r(0x05F8)==1 and (tail==0xE0 or tail==0xE2) and r(0x0245)==tail+4
                and r(0x0242)==0x20 and r(0x0246)==0x20 and r(0x0247)==x+8
                and r(0x0244)==y and y==x+0x43 then
                sawFireballPose[tail]=true
                if x+15>=r(0x0233) and y>=0xB6 then fireballReachedZelda=true end
                if x==0x72 then
                    local f=assert(io.open(OUTPUT_DIR..'/ending_fire.png','wb'))
                    f:write(emu.takeScreenshot());f:close()
                end
            end
            if s==8 and r(0x0230)==0xF8 and r(0x0234)==0xF8 and r(0x0239)==0x5E and r(0x023D)==0x62
                and r(0x0240)==0xF8 and r(0x0244)==0xF8 and not sawZeldaAsh then
                sawZeldaAsh=true
                local f=assert(io.open(OUTPUT_DIR..'/ending_ash.png','wb'))
                f:write(emu.takeScreenshot());f:close()
            end
        elseif s==11 then
            local idx=r(0x0054)
            if idx>maxCreditsIndex then maxCreditsIndex=idx end
            -- Fast-forward credit wait timer after observing each entry so the test finishes quickly.
            if r(0x0037)>2 then w(0x0037,2) end
        elseif s==12 then
            if not sawReplayWait then
                sawReplayWait=true
                local f=assert(io.open(OUTPUT_DIR..'/ending_replay.png','wb'))
                f:write(emu.takeScreenshot());f:close()
            end
        end
        if sawReplayWait and r(0x07A0)==1 then
            sawNewGamePlus=true
        end
        if sawNewGamePlus or frame>=6000 then
            finished=true
            report:write(string.format('end frame=%d s=%d 76C=%d 7A0=%d 33=%02X 37=%02X 27=%02X 28=%02X 5F8=%02X 5F9=%02X\n',
                frame,s,r(0x076C),r(0x07A0),r(0x0033),r(0x0037),r(0x0027),r(0x0028),r(0x05F8),r(0x05F9)))
            check(sawBarbaWait,'Ending renders 24x48 Barba OAM sprites')
            check(sawBarbaAndZelda,'Ending renders Barba alongside woken Zelda')
            check(endingTrailInFront and endingTrailBehind,'Ending torso and tail follow the curtain priority')
            check(sawNoLinkTiles,'Ending OAM contains zero Link tiles ($E0-$E6)')
            check(sawNoCloserStep,'Barba stays in place without stepping closer to Zelda')
            check(sawFireballPose[0xE0] and sawFireballPose[0xE2],'Both fireball poses draw with the two halves aligned behind the curtain')
            check(fireballReachedZelda,'Fireball reaches Zelda before impact')
            check(sawZeldaAsh,'Both fireball sprites disappear and Zelda turns into ash before credits')
            check(maxCreditsIndex>=19,'Ending credits roll all 20 entries (max index '..maxCreditsIndex..')')
            check(sawReplayWait,'Ending reaches LAVA RECLAIMED / PUSH START TO REPLAY')
            check(sawNewGamePlus,'Pressing Start on ending enters New Game+ ($07A0 == 1)')
            report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..string.char(10))
            report:close()
            stopScenario(errors==0 and 0 or 1)
        end
    end
end,emu.eventType.endFrame)
