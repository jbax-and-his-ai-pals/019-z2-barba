-- West Hyrule Desert Geldarm ($20): standing, crouching, left-facing,
-- and extra-slot fireballs hit its full 12x64 body+head hurtbox. HP is 4, so
-- one attack-4 hit kills; the worm sinks to its base (HP 0, still slot state 1)
-- before the native death explosion, which then starts at the sand line.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local frame,age,phase,errors=0,0,0,0
local base,pending,done=nil,false,false
local slot=0
local f=assert(io.open(OUTPUT_DIR..'/geldarm.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
local phases={
    {name='standing fireball hits full-height Geldarm',dir=1,duck=false,dx=68,busy=false},
    {name='crouching fireball hits full-height Geldarm',dir=1,duck=true,dx=68,busy=false},
    {name='left-facing fireball hits full-height Geldarm',dir=2,duck=false,dx=-44,busy=false},
    {name='extra-slot fireball hits full-height Geldarm',dir=1,duck=false,dx=68,busy=true},
    {name='attack-1 fireball wounds Geldarm (4 -> 2 HP)',dir=1,duck=false,dx=68,busy=false,atk=1},
}
local hitSeen=false
local sankY,minY,deathY,hp0=nil,999,nil,false

local function setupPhase()
    emu.loadSavestate(base)
    local p=phases[phase]
    age=0;hitSeen=false;sankY=nil;minY=999;deathY=nil;hp0=false
    for s=0,5 do w(0xB6+s,0) end
    local bx=r(0x3B)*256+r(0x4D)
    local gx=bx+p.dx
    w(0xB6+slot,1);w(0xA1+slot,0x20)
    w(0x4E+slot,gx%256);w(0x3C+slot,math.floor(gx/256))
    w(0x2A+slot,144);w(0x81+slot,144+0x3F)
    w(0xAF+slot,1);w(0x60+slot,0);w(0xC2+slot,4);w(0x040E+slot,0)
    w(0x1A+slot,1);w(0xA8+slot,0)
    w(0x9F,p.dir);w(0x5F,p.dir)
    w(0x777,p.atk or 4)
    w(0x8D,0);w(0x8E,0)
    w(0x05F8,0);w(0x05FC,0);w(0x05FD,0)
    if p.busy then
        -- Keep native projectile slots occupied with far-away dummy shots so the new shot uses EXTRA_BASE.
        w(0x8D,1);w(0x36,24);w(0x5A,0);w(0x48,0);w(0x7D,0)
        w(0x8E,1);w(0x37,24);w(0x5B,0);w(0x49,0);w(0x7E,0)
    end
end

emu.addEventCallback(function()
    if done then return end
    local b=newGameInput(frame)
    if frame>=1000 then
        b={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
        if base and not pending and phases[phase] then
            local p=phases[phase]
            b.left=(p.dir==2 and age>=1 and age<3)
            b.right=(p.dir==1 and age>=1 and age<3)
            b.down=p.duck
            b.b=(age>=4 and age<16)
        end
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)

emu.addMemoryCallback(function()
    if done or not pending then return end
    pending=false
    if not base then
        base=emu.createSavestate()
        check(r(0x707)==0 and r(0x769)==1 and r(0x736)==11,'West Hyrule bank 1 side-view loaded')
        check(r(0x6D41)==4,string.format('Geldarm max HP is 4 (got %d)',r(0x6D41)))
    end
    phase=phase+1
    if not phases[phase] then
        done=true
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close()
        local stop=emu.exit or emu.stop
        stop(errors==0 and 0 or 1)
        return
    end
    setupPhase()
end,emu.callbackType.exec,0xC07B)

emu.addEventCallback(function()
    if done then return end
    frame=frame+1
    if not base then
        if frame==1000 then
            w(0x707,0);w(0x706,0);w(0x769,1);w(0x561,0x1D)
            w(0x701,0);w(0x75C,1);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1)
        end
        if frame==1170 then pending=true end
        if frame>1500 then
            done=true
            f:write('FAIL timeout loading desert battle\nRESULT FAIL\n');f:close()
            local stop=emu.exit or emu.stop
            stop(1)
        end
        return
    end
    if pending or not phases[phase] then return end
    age=age+1
    if r(0xB6+slot)==0 or r(0x040E+slot)~=0 then hitSeen=true end
    local st=r(0xB6+slot)
    if st==1 and r(0xC2+slot)==0 then
        hp0=true
        if r(0x2A+slot)<minY then minY=r(0x2A+slot) end
        sankY=r(0x2A+slot)
    elseif st~=1 and hp0 and not deathY then
        deathY=r(0x2A+slot)
    end
    if age>=70 then
        local p=phases[phase]
        if p.atk==1 then
            check(hitSeen and r(0xB6+slot)==1 and r(0xC2+slot)==2 and not hp0 and r(0x2A+slot)<144+0x20,
                string.format('%s (hit=%s alive=%d hp=%d y=%d)',p.name,tostring(hitSeen),r(0xB6+slot),r(0xC2+slot),r(0x2A+slot)))
            pending=true
            return
        end
        check(hitSeen and r(0xB6+slot)~=1,string.format('%s (hit=%s alive=%d hp=%d bx=%d gx=%d)',
            p.name,tostring(hitSeen),r(0xB6+slot),r(0xC2+slot),r(0x3B)*256+r(0x4D),r(0x3C+slot)*256+r(0x4E+slot)))
        check(hp0 and deathY~=nil and deathY==144+0x3F and sankY and sankY>=144+0x3F-2 and minY<144+0x20,
            string.format('%s sinks before dying (hp0=%s minY=%d lastY=%s deathY=%s)',
            p.name,tostring(hp0),minY,tostring(sankY),tostring(deathY)))
        pending=true
    end
end,emu.eventType.endFrame)
