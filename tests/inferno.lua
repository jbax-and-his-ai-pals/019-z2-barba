-- Verify True INFERNO Dragon Spell: roar, extended flash, and multi-wave
-- multi-directional firestorm barrage without HUD/split issues.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/inferno.txt','w'))
local errors=0
local frame=0
local castFrame=nil
local sawRoar,sawTimer,sawFlash=false,false,false
local sawRight,sawLeft,sawUp,sawDown=false,false,false,false
local maxLive=0

local function check(ok,msg)
    report:write((ok and 'PASS ' or 'FAIL ')..msg..'\n')
    if not ok then errors=errors+1 end
end

local function input()
    local b=newGameInput(frame)
    if castFrame and frame==castFrame then
        b.select=true
    end
    emu.setInput(b,0)
end

local function inspectPool()
    local live=0
    for slot=0,1 do
        local s=r(0x8D+slot)
        if s>0 and s<128 then
            live=live+1
            local d=r(0x6D+slot)
            local v=r(0x05FC+slot)
            if d==1 then sawRight=true elseif d==2 then sawLeft=true end
            if (v&0x40)~=0 then sawUp=true else sawDown=true end
        end
    end
    if r(0x5FF)==1 then
        for base=0x6400,0x6420,0x10 do
            local s=r(base)
            if s>0 and s<128 then
                live=live+1
                local d=r(base+5)
                local v=r(base+9)
                if d==1 then sawRight=true elseif d==2 then sawLeft=true end
                if (v&0x40)~=0 then sawUp=true else sawDown=true end
            end
        end
    end
    if live>maxLive then maxLive=live end
end

local function tick()
    frame=frame+1
    if not castFrame and frame>700 and r(0x0736)==0x0B and r(0x074C)==0 and r(0x0524)==0 and r(0xDE)==0 then
        w(0x0782,1)    -- learn INFERNO
        w(0x0749,7)    -- select INFERNO
        w(0x074A,0)
        w(0x0773,0xFF) -- full MP
        castFrame=frame+1
    end
    if castFrame and frame>castFrame then
        if r(0x05F0)>0 then sawRoar=true end
        if r(0x6470)>0 then sawTimer=true end
        if r(0x074B)>0 then sawFlash=true end
        inspectPool()
        if frame==castFrame+18 then screenshot('inferno-barrage') end
        if frame==castFrame+70 then
            check(sawRoar,'INFERNO activates roar timer ($05F0)')
            check(sawTimer,'INFERNO activates multi-wave firestorm timer ($6470)')
            check(sawFlash,'INFERNO triggers screen/decor flash ($074B)')
            check(sawRight and sawLeft,'INFERNO fires both right and left fireballs')
            check(sawUp and sawDown,'INFERNO fires both upward and downward fireballs')
            check(maxLive>=4,'INFERNO fills multi-slot firestorm pool (maxLive='..maxLive..')')
            report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
            report:close()
            stopScenario(errors==0 and 0 or 1)
        end
    end
    if frame==2000 then
        check(false,'entered side-view to cast INFERNO')
        report:write('RESULT FAIL\n'); report:close(); stopScenario(1)
    end
end

emu.addEventCallback(input,emu.eventType.inputPolled)
emu.addEventCallback(tick,emu.eventType.endFrame)
