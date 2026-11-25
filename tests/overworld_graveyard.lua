-- Verify Overworld Graveyard Wisp Motes:
-- On the overworld ($0736 == 5, $0726 == 0) in West Hyrule Graveyard ($08 tiles),
-- subtle 8x16 wisp sprites ($E1 dim gold, $E3 2px white+gold) appear in $6500-$65FF OAM,
-- drift slowly upward and sway horizontally, stay sparse on a screen full of crosses,
-- stay below the HUD (Y >= 32), and track scroll deltas when walking.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/overworld-graveyard.txt','w'))
local errors=0
local frame=0
local done=false
local worldAt=nil
local seenDim,seenPeak=0,0
local maxActive=0
local totalActive=0
local standFrames=0
local badY=0
local sawRise,sawSway=false,false
local scrollTracked=false
local prevScrollX,prevScrollY=nil,nil
local prevSpk={}
local firstPos={}

local function check(ok,msg)
    report:write((ok and 'PASS ' or 'FAIL ')..msg..'\n')
    if not ok then errors=errors+1 end
end

local function input()
    local b=newGameInput(frame)
    if frame>=1000 and worldAt==nil then
        b.right=(frame>=1250 and frame<2050)
    elseif worldAt then
        w(0x86,0); w(0x87,0); w(0x88,0); w(0x89,0)
        local dt=frame-worldAt
        if dt>=390 and dt<480 then
            b.left=true
        end
    end
    emu.setInput(b,0)
end

local function tick()
    if done then return end
    frame=frame+1
    if frame>1250 and worldAt==nil and r(0x0736)==5 and r(0x0726)==0 then
        worldAt=frame
        w(0x73,0x55); w(0x74,0x36); w(0x736,2)
    end
    if worldAt and frame>=worldAt+30 and frame<worldAt+480 then
        if r(0x0736)==5 and r(0x0726)==0 then
            local dt=frame-worldAt
            local active=0
            local cur={}
            for i=0,2 do
                local t=r(0x6436+i)
                local k=r(0x648C+i)
                if t>=1 and t<=48 and k==4 then
                    local x=r(0x6430+i)
                    local y=r(0x6433+i)
                    cur[i]={x=x,y=y,t=t}
                    if dt<390 then
                        if not firstPos[i] or t>(prevSpk[i] and prevSpk[i].t or 0) then
                            firstPos[i]={x=x,y=y}
                        else
                            if y<firstPos[i].y then sawRise=true end
                            if x~=firstPos[i].x then sawSway=true end
                        end
                    end
                end
            end
            for off=0x20,0xFC,4 do
                local y=r(0x6500+off)
                local tile=r(0x6501+off)
                local attr=r(0x6502+off)
                if y<0xF0 and (tile==0xE1 or tile==0xE3) and attr==0 then
                    active=active+1
                    if tile==0xE1 then seenDim=seenDim+1 else seenPeak=seenPeak+1 end
                    if y<32 or y>=0xD8 then badY=badY+1 end
                end
            end
            if dt<390 then
                standFrames=standFrames+1
                totalActive=totalActive+active
            end
            if active>maxActive then maxActive=active end
            local sx,sy=r(0xFD),r(0xFC)
            if prevScrollX and sy==prevScrollY then
                local dx=sx-prevScrollX
                if dx~=0 and math.abs(dx)<=8 then
                    for i=0,2 do
                        if cur[i] and prevSpk[i] and cur[i].t<prevSpk[i].t then
                            local spkDx=cur[i].x-prevSpk[i].x
                            -- Allow +-1px horizontal sway on top of scroll delta
                            if math.abs(spkDx-(-dx))<=1 then
                                scrollTracked=true
                            end
                        end
                    end
                end
            end
            prevScrollX,prevScrollY=sx,sy
            prevSpk=cur
        end
    end
    if worldAt and frame>=worldAt+480 then
        local avg=standFrames>0 and (totalActive/standFrames) or 0
        check(r(0x0736)==5,'remained on overworld ($0736 == 5)')
        check(seenDim>0,'observed dim gold graveyard spark ($E1, count='..seenDim..')')
        check(seenPeak>0,'observed 2px white+gold graveyard wisp ($E3, count='..seenPeak..')')
        check(sawRise,'graveyard wisp drifted upward')
        check(sawSway,'graveyard wisp swayed horizontally')
        check(maxActive>=1 and maxActive<=3,'at most 3 concurrent wisps (max='..maxActive..')')
        check(avg<2.0,string.format('subtle density on full cross screen (avg=%.2f)',avg))
        check(badY==0,'all wisps stayed below HUD and inside playfield (badY='..badY..')')
        check(scrollTracked,'active wisp X shifted opposite camera scroll when walking')
        report:write(string.format('RESULT overworld_graveyard dim=%d peak=%d max=%d avg=%.2f errors=%d\n',
            seenDim,seenPeak,maxActive,avg,errors))
        report:close()
        done=true
        stopScenario(errors==0 and 0 or 1)
    end
end

emu.addEventCallback(input,emu.eventType.inputPolled)
emu.addEventCallback(tick,emu.eventType.endFrame)
