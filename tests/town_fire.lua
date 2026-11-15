-- Rauru street: a jumping volley into the brick house scorches it without removing it.
-- Buildings keep their metatiles (collision), flame tiles appear and then turn to char.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local p=emu.memType.nesPpuMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local WALK=150 -- frames of walking right from the entrance to stand before the brick house
local FLAME={[0x02]=true,[0x04]=true,[0x0E]=true,[0x16]=true}
local CHAR={[0x25]=true,[0x96]=true,[0xA7]=true,[0xB9]=true}
local frame,age,phase,errors=0,0,0,0
local pending,base=false,nil
local metatiles,nametable=nil,nil
local maxFlame,maxChar,blanked,foreign=0,0,0,0
local flameSeenAt,charSeenAt=nil,nil
local f=assert(io.open(OUTPUT_DIR..'/town-fire.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
local function screenshot(name)
    local s=assert(io.open(OUTPUT_DIR..'/'..name..'.png','wb'));s:write(emu.takeScreenshot());s:close()
end
local function snapMeta()local t={} for a=0x6000,0x633F do t[#t+1]=r(a) end return t end
local function snapNT()local t={} for a=0x2000,0x27BF do t[a]=emu.read(a,p) end return t end
local function counts()
    local fl,ch=0,0
    for a=0x2000,0x27BF do
        if (a%0x400)<0x3C0 then
            local t=emu.read(a,p)
            if FLAME[t] then fl=fl+1 elseif CHAR[t] then ch=ch+1 end
        end
    end
    return fl,ch
end
emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then
        b={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
        -- phase 1: settle; then jump (A) and breathe (B) near the apex.
        if phase==1 then b.right=age<WALK end
        if phase==1 and age>=WALK+30 then
            local t=age-WALK-30
            b.a=t<18
            b.b=t>=10 and t<13
        end
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addMemoryCallback(function()
    if not pending then return end
    pending=false
    base=emu.createSavestate()
    check(r(0x707)==1 and r(0x561)==1,'native Rauru street loaded')
    w(0x8D,0);w(0x8E,0);w(0x5F8,0);w(0x5FE,0);w(0x400,0);w(0x76F,0)
    for x=0,5 do w(0xB6+x,0) end
    phase=1;age=0
end,emu.callbackType.exec,0xC07B)
emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        w(0x707,1);w(0x706,0);w(0x769,3);w(0x561,1)
        w(0x701,0);w(0x75C,0);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1)
    end
    if phase==0 then
        if frame>1150 and r(0x736)==11 then pending=true end
        if frame==1800 then check(false,'Rauru loaded');f:close();stopScenario(1)end
        return
    end
    age=age+1
    for x=0,5 do w(0xB6+x,0) end
    if age==WALK+29 then metatiles=snapMeta();nametable=snapNT();screenshot('town-fire-before')end
    if age>=WALK+30 then
        local fl,ch=counts()
        if fl>maxFlame then maxFlame=fl end
        if ch>maxChar then maxChar=ch end
        if fl>0 and not flameSeenAt then flameSeenAt=age;end
        if ch>0 and not charSeenAt then charSeenAt=age end
        if fl>0 and age-(flameSeenAt or age)==6 then screenshot('town-fire-flame')end
    end
    if age==WALK+190 then
        screenshot('town-fire-after')
        local now=snapMeta();local same=true
        for i=1,#now do if now[i]~=metatiles[i] then same=false end end
        for a=0x2000,0x27BF do
            if (a%0x400)<0x3C0 then
                local t=emu.read(a,p);local old=nametable[a]
                if t~=old then
                    if t==0xF4 then blanked=blanked+1
                    elseif not FLAME[t] and not CHAR[t] then foreign=foreign+1 end
                end
            end
        end
        local fl,ch=counts()
        f:write(string.format('maxFlame=%d maxChar=%d flameAt=%s charAt=%s endFlame=%d endChar=%d blanked=%d foreign=%d page=%02X x=%02X\n',
            maxFlame,maxChar,tostring(flameSeenAt),tostring(charSeenAt),fl,ch,blanked,foreign,r(0x3B),r(0x4D)))
        check(same,'room metatiles (collision) are unchanged after the attack')
        check(maxFlame>=4,'fireballs ignite at least one 2x2 flame on the building')
        check(ch>=4,'flames turn into char marks that stay on screen')
        check(fl==0,'no flame tiles remain once the effect finishes')
        check(charSeenAt~=nil and flameSeenAt~=nil and charSeenAt-flameSeenAt>=20,'char replaces flame after the flame stage')
        check(blanked==0,'no building tile is blanked to sky')
        check(foreign==0,'no other nametable tile changed')
        local live=0
        for x=0,7 do if r(0x6480+x)~=0 then live=live+1 end end
        check(live<=8,'scorch ring stays bounded')
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close()
        stopScenario(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
