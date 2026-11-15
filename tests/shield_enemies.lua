-- Shielded enemies (e.g. Orange Ironknuckle $18): high shield blocks
-- standing breath and yields to crouching breath; low shield blocks
-- crouching breath and yields to standing breath.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local frame,age,phase,errors=0,0,0,0
local base,pending=nil,false
local slot=1
local f=assert(io.open(OUTPUT_DIR..'/shield_enemies.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
local phases={
    {name='high shield blocks standing shot',sh=1,duck=false,ex=156,expectHit=false},
    {name='high shield yields to crouching shot',sh=1,duck=true,ex=156,expectHit=true},
    {name='low shield blocks crouching shot',sh=0,duck=true,ex=156,expectHit=false},
    {name='low shield yields to standing shot',sh=0,duck=false,ex=156,expectHit=true},
}
local hitSeen,clinkSeen=false,false

local function setupPhase()
    emu.loadSavestate(base)
    local p=phases[phase]
    age=0;hitSeen=false;clinkSeen=false
    for s=0,5 do if r(0xB6+s)==1 and r(0xA1+s)~=0x02 then w(0xB6+s,0) end end
    w(0xB6+slot,1);w(0xA1+slot,0x18)
    w(0x4E+slot,p.ex);w(0x3C+slot,0);w(0x2A+slot,176)
    w(0xC2+slot,0x10);w(0x0444+slot,p.sh);w(0x60+slot,1)
    w(0x040E+slot,0);w(0x71+slot,0)
    w(0x4D,120);w(0x3B,0);w(0x29,176);w(0x9F,1);w(0x5F,1)
    w(0x76F,0x10);w(0x777,4)
    w(0x8D,0);w(0x8E,0)
end

emu.addEventCallback(function()
    local b=newGameInput(frame)
    if base and phase>0 and phases[phase] then
        local p=phases[phase]
        b={start=false,select=false,a=false,b=age>=5 and age<8,up=false,down=p.duck,left=false,right=false}
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)

emu.addMemoryCallback(function()
    if not pending then return end
    pending=false
    if not base then base=emu.createSavestate() end
    phase=phase+1
    if not phases[phase] then
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close()
        stopScenario(errors==0 and 0 or 1);return
    end
    setupPhase()
end,emu.callbackType.exec,0xC07B)

emu.addEventCallback(function()
    frame=frame+1
    if not base then
        if frame==1000 then
            w(0x707,3);w(0x706,0);w(0x769,3);w(0x561,5)
            w(0x701,0);w(0x75C,0);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1)
        end
        if frame==1150 then pending=true end
        return
    end
    if pending or not phases[phase] then return end
    age=age+1
    local p=phases[phase]
    -- Keep enemy stationary and shield locked to the phase's test position
    -- so Ironknuckle AI doesn't mirror Link's stance mid-flight.
    w(0x4E+slot,p.ex);w(0x71+slot,0);w(0x0444+slot,p.sh)
    if r(0xC2+slot)<0x10 or r(0xB6+slot)==0 or r(0x040E+slot)>0 then hitSeen=true end
    if r(0x8D)>=0xF2 or r(0x8E)>=0xF2 then clinkSeen=true end
    if age==35 then
        if p.expectHit then
            check(hitSeen,p.name..' (hp='..r(0xC2+slot)..')')
        else
            check(not hitSeen and clinkSeen,p.name..' (clinked='..tostring(clinkSeen)..')')
        end
        pending=true
    end
end,emu.eventType.endFrame)
