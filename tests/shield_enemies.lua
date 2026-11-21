-- Test high/low shield coverage and a bank shot through to a second enemy.
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
    {name='airborne bank shot kills a Bot behind Barba',sh=1,duck=false,ex=156,bot=97,jump=true},
}
local hitSeen,launchY,peakY,fell,botKilled,airSlot,airShotEnded,bankShotHit
local botSlot=2
emu.addMemoryCallback(function()
    if phases[phase] and phases[phase].bot and r(0x0B)==1 and emu.getState()['cpu.x']==botSlot then
        bankShotHit=not airShotEnded and r(0x11)==airSlot and r(0x7D+airSlot)==0xC8
    end
end,emu.callbackType.exec,0xE726)

local function setupPhase()
    emu.loadSavestate(base)
    local p=phases[phase]
    age=0;hitSeen=false;launchY=nil;peakY=nil;fell=false;botKilled=false
    airSlot=nil;airShotEnded=false;bankShotHit=false
    for s=0,5 do if r(0xB6+s)==1 and r(0xA1+s)~=0x02 then w(0xB6+s,0) end end
    w(0xB6+slot,1);w(0xA1+slot,0x18)
    w(0x4E+slot,p.ex);w(0x3C+slot,0);w(0x2A+slot,176)
    w(0xC2+slot,0x10);w(0x0444+slot,p.sh);w(0x60+slot,1)
    w(0x040E+slot,0);w(0x71+slot,0)
    w(0x4D,120);w(0x3B,0);w(0x29,176);w(0x9F,1);w(0x5F,1)
    w(0x76F,0x10);w(0x777,4)
    w(0x8D,0);w(0x8E,0)
    if p.bot then
        w(0xB6+botSlot,1);w(0xA1+botSlot,4);w(0xC2+botSlot,4)
        w(0x4E+botSlot,p.bot);w(0x3C+botSlot,0);w(0x2A+botSlot,160)
        w(0x040E+botSlot,0);w(0x71+botSlot,0);w(0x1A+botSlot,1)
        w(0xA8+botSlot,0);w(0xAF+botSlot,0);w(0x057E+botSlot,0)
    end
end

emu.addEventCallback(function()
    local b=newGameInput(frame)
    if base and phase>0 and phases[phase] then
        local p=phases[phase]
        local attack=p.jump and 22 or 5
        b={start=false,select=false,a=p.jump and age>=1 and age<7,
            b=age>=attack and age<attack+3,up=false,down=p.duck,left=false,right=false}
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
    for fire=0,1 do
        if not airSlot and r(0x8D+fire)==1 and r(0x7D+fire)==0x20 and r(0x479)~=0 then airSlot=fire end
        if r(0x8D+fire)==1 and r(0x7D+fire)==0xC8 and (not p.bot or (fire==airSlot and not airShotEnded)) then
            local y=r(0x36+fire)
            if not launchY then launchY=y;peakY=y end
            peakY=math.min(peakY,y)
            if peakY<launchY and y>peakY then fell=true end
        end
    end
    if p.bot then
        w(0x4E+botSlot,p.bot);w(0x2A+botSlot,160);w(0x71+botSlot,0)
        if r(0xB6+botSlot)==2 and bankShotHit then botKilled=true end
        if airSlot and r(0x8D+airSlot)~=1 then airShotEnded=true end
    end
    if age==(p.bot and 75 or 35) then
        local rose=peakY~=nil and peakY<launchY
        if p.expectHit then
            check(hitSeen,p.name..' (hp='..r(0xC2+slot)..')')
        elseif p.bot then
            check(not hitSeen and airSlot~=nil and rose and fell and botKilled,
                p.name..' (airborne='..tostring(airSlot~=nil)..', rose='..tostring(rose)
                ..', fell='..tostring(fell)..', killed='..tostring(botKilled)..')')
        else
            check(not hitSeen and rose,p.name..' (rebounded='..tostring(rose)..')')
        end
        pending=true
    end
end,emu.eventType.endFrame)
