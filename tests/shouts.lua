-- Passive subtitle: real town actor, actual PPU queue, no input/dialogue lock.
dofile(TEST_DIR..'/newgame.lua')
local m,p=emu.memType.nesMemory,emu.memType.nesPpuMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local frame,age,errors=0,0,0
local slot=nil
local active=false
local visible,moved,cleared=false,false,false
local noLock=true
local firstAt=nil
local queueMax=0
local f=assert(io.open(OUTPUT_DIR..'/shouts.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
emu.addMemoryCallback(function(_,value)
    if active and value>queueMax then queueMax=value end
end,emu.callbackType.write,0x301)
emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then
        b={start=false,select=false,a=false,b=false,up=false,down=false,left=false,
            right=active and age>=30 and age<65}
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        w(0x707,1);w(0x706,0);w(0x769,3);w(0x561,1)
        w(0x701,0);w(0x75C,0);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1)
    end
    if not active and frame>1150 then
        for x=0,5 do
            if r(0xB6+x)==1 and r(0xBC+x)==255 and r(0xA1+x)>=0x19 and r(0xA1+x)<=0x1C then slot=x;break end
        end
        if slot then
            active=true;age=0
            w(0x4D,80);w(0x3B,0);w(0x70,0);w(0x29,176)
            w(0x4E+slot,112);w(0x3C+slot,0);w(0x2A+slot,176)
            w(0xAF+slot,0);w(0xA1+slot,0x19);w(0x5C3+slot,0)
            w(0x5EA,0)
            for a=0x6460,0x6466 do w(a,0)end
            for x=0,5 do if r(0xA1+x)==0x23 then w(0xB6+x,0)end end
        end
        if frame==1800 then check(false,'native wanderer spawned');f:close();stopScenario(1)end
        return
    end
    if not active then return end
    age=age+1
    if r(0x74C)~=0 or r(0xDE)~=0 or r(0x524)~=0 then noLock=false end
    if emu.read(0x2006,p)==0xE8 and emu.read(0x2007,p)==0xE1 then
        visible=true;if not firstAt then firstAt=age end
    end
    if age>=30 and r(0x70)~=0 and visible then moved=true end
    if age==20 then screenshot('town-passive-shout')end
    if age>115 then
        local blank=true
        for a=0x2006,0x2019 do if emu.read(a,p)~=0xF4 then blank=false end end
        if blank then cleared=true end
    end
    if age==155 then
        check(visible and firstAt<=6,'panic shout reaches real PPU within six frames')
        check(moved and noLock,'player keeps moving without any dialogue/menu lock')
        check(cleared,'subtitle clears itself with spaces after its timeout')
        check(queueMax<=0x20,'subtitle packet stays within the 32-byte queue budget')
        check(r(0x736)==11 and r(0x774)>0,'town remains playable')
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close();stopScenario(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
