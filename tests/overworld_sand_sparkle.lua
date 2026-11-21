-- Verify Overworld Sand Sparkle:
-- On the overworld ($0736 == 5, $0726 == 0) near Desert ($04) tiles,
-- sparse 8x16 glint sprites ($D1 dim, $D3 peak) appear in $6500-$65FF OAM,
-- never exceed 3 active slots, stay below the HUD (Y >= 32), and track
-- scroll deltas when walking.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/overworld-sand-sparkle.txt','w'))
local errors=0
local frame=0
local worldAt=nil
local seenDim,seenPeak=0,0
local maxActive=0
local badY=0
local scrollTracked=false
local prevScrollX,prevScrollY=nil,nil
local prevSpk={}

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
        -- Walk right then down past Rauru into the desert, stand still to
        -- observe sparkles, then walk left to test scroll tracking.
        -- Stand still in Parapa Desert to observe sparkles, then walk left to test scroll tracking.
        if dt>=230 and dt<320 then
            b.left=true
        end
    end
    emu.setInput(b,0)
end

local function tick()
    frame=frame+1
    if frame>1250 and worldAt==nil and r(0x0736)==5 and r(0x0726)==0 then
        worldAt=frame
        w(0x73,0x28); w(0x74,0x28); w(0x736,2)
    end
    if worldAt and frame>=worldAt+30 and frame<worldAt+330 then
        if r(0x0736)==5 and r(0x0726)==0 then
            local active=0
            local cur={}
            for i=0,2 do
                local t=r(0x6436+i)
                if t>=1 and t<=28 then
                    cur[i]={x=r(0x6430+i),y=r(0x6433+i),t=t}
                end
            end
            for off=0x20,0xFC,4 do
                local y=r(0x6500+off)
                local tile=r(0x6501+off)
                if y<0xF0 and (tile==0xD1 or tile==0xD3) then
                    active=active+1
                    if tile==0xD1 then seenDim=seenDim+1 else seenPeak=seenPeak+1 end
                    if y<0x1E or y>=0xD8 then badY=badY+1 end
                end
            end
            if active>maxActive then maxActive=active end
            local sx,sy=r(0x00FD),r(0x00FC)
            if prevScrollX~=nil then
                local dx=(sx-prevScrollX)
                if dx>128 then dx=dx-256 elseif dx<-128 then dx=dx+256 end
                if dx~=0 then
                    for i=0,2 do
                        if prevSpk[i] and cur[i] and prevSpk[i].t>1 then
                            if cur[i].x==(prevSpk[i].x-dx)%256 then
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
    if worldAt and frame==worldAt+340 then
        check(r(0x0736)==5,'remained on overworld ($0736 == 5)')
        check(seenDim>0,'observed 1x1 white sand dot sprites ($D1, count='..seenDim..')')
        check(seenPeak>0,'observed 3x3 white sand twinkle sprites ($D3, count='..seenPeak..')')
        check(maxActive>=1 and maxActive<=3,'at most 3 concurrent sparkles (max='..maxActive..')')
        check(badY==0,'all sparkles stayed below HUD and inside playfield (badY='..badY..')')
        check(scrollTracked,'active sparkle X shifted opposite camera scroll when walking')
        report:write(string.format('RESULT overworld_sand_sparkle dim=%d peak=%d max=%d errors=%d\n',
            seenDim,seenPeak,maxActive,errors))
        report:close()
        emu.stop(errors==0 and 0 or 1)
    end
end

emu.addEventCallback(input,emu.eventType.inputPolled)
emu.addEventCallback(tick,emu.eventType.endFrame)
