-- Rauru street: lasting fires on buildings and ground.
-- Buildings and ground keep their metatiles (collision). Flames stay lit for ~10s
-- before turning to char, cap at 16 active fires (oldest evicts to char), and clear
-- when leaving the room.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local p=emu.memType.nesPpuMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local WALK=150 -- frames of walking right from the entrance to stand before the brick house
local BG_FLAME={[0x34]=true,[0xA4]=true,[0xAC]=true,[0xC0]=true}
local CHAR={[0xC1]=true,[0x35]=true,[0xA7]=true,[0xC2]=true}
local SCORCH_OAM={0x28,0x2C,0x30,0x34,0x60,0x64,0x78,0x7C,0x90,0xA8,0xC0,0xFC,0xDC,0xE0,0xE4,0xE8,0xEC,0xF0,0xF4}
local frame,age,phase,errors=0,0,0,0
local pending,wantLoad,base=false,false,nil
local metatiles,nametable=nil,nil
local maxFlame,maxBgFlame,maxChar,blanked,foreign=0,0,0,0,0
local flameSeenAt,charSeenAt,flameAt180=nil,nil,0
local sawFlip0,sawFlip1=false,false
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
            if BG_FLAME[t] then fl=fl+1 elseif CHAR[t] then ch=ch+1 end
        end
    end
    return fl,ch
end
local function spriteFlames()
    local n,f0,f1=0,false,false
    for _,oam in ipairs(SCORCH_OAM) do
        local y=r(0x200+oam)
        local t=r(0x201+oam)
        local attr=r(0x202+oam)
        if y<0xF8 and t==0x84 and (attr%4)==1 then
            n=n+1
            if (attr%128)>=0x40 then f1=true else f0=true end
        end
    end
    return n,f0,f1
end
local function liveSlots()
    local n=0
    for x=0,15 do if r(0x64B0+x)~=0 then n=n+1 end end
    return n
end
emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then
        b={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
        if phase==1 then
            b.right=age<WALK
            if age>=WALK+30 then
                local t=age-WALK-30
                b.a=t<18
                b.b=t>=10 and t<13
            end
        elseif phase==2 then
            -- Stay within one screen: crouch-breathe on the street, then walk right in steps
            -- and crouch/jump-breathe to ignite >16 on-screen fires.
            if age>=10 and age<40 then
                b.down=true; b.b=(age%6)<3
            elseif age>=45 and age<120 then
                b.right=true
            elseif age>=125 and age<160 then
                b.down=true; b.b=(age%6)<3
            elseif age>=165 and age<205 then
                local t=age-165
                b.a=t<18; b.b=(t>=10 and t<13)
            elseif age>=210 and age<270 then
                b.right=true
            elseif age>=275 and age<310 then
                b.down=true; b.b=(age%6)<3
            elseif age>=315 and age<355 then
                local t=age-315
                b.a=t<18; b.b=(t>=10 and t<13)
            end
        end
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addMemoryCallback(function()
    if wantLoad then
        wantLoad=false
        emu.loadSavestate(base)
        w(0x8D,0);w(0x8E,0);w(0x5F8,0);w(0x5FE,0);w(0x400,0);w(0x76F,0)
        for x=0,5 do w(0xB6+x,0) end
        phase=2;age=0;metatiles=snapMeta();nametable=snapNT()
        return
    end
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
    if phase==1 then
        if age==WALK+29 then metatiles=snapMeta();nametable=snapNT();screenshot('town-fire-before')end
        if age>=WALK+30 then
            local bgFl,ch=counts()
            local spFl,f0,f1=spriteFlames()
            if spFl>maxFlame then maxFlame=spFl end
            if bgFl>maxBgFlame then maxBgFlame=bgFl end
            if ch>maxChar then maxChar=ch end
            if spFl>0 and not flameSeenAt then flameSeenAt=age end
            if f0 then sawFlip0=true end
            if f1 then sawFlip1=true end
            if ch>0 and not charSeenAt then charSeenAt=age end
            if spFl>0 and age-(flameSeenAt or age)==6 then screenshot('town-fire-flame')end
            if age==WALK+210 then flameAt180=spFl end
        end
        if age==WALK+700 then
            screenshot('town-fire-after')
            local now=snapMeta();local same=true
            for i=1,#now do if now[i]~=metatiles[i] then same=false end end
            for a=0x2000,0x27BF do
                if (a%0x400)<0x3C0 then
                    local t=emu.read(a,p);local old=nametable[a]
                    if t~=old then
                        if t==0xF4 then blanked=blanked+1
                        elseif not CHAR[t] then foreign=foreign+1 end
                    end
                end
            end
            local bgFl,ch=counts()
            local spFl=spriteFlames()
            f:write(string.format('p1 maxFlame=%d maxBgFlame=%d flameAt180=%d maxChar=%d flameAt=%s charAt=%s endFlame=%d endChar=%d blanked=%d foreign=%d\n',
                maxFlame,maxBgFlame,flameAt180,maxChar,tostring(flameSeenAt),tostring(charSeenAt),spFl,ch,blanked,foreign))
            check(same,'room metatiles (collision) are unchanged after the attack')
            check(maxFlame>=2,'fireballs ignite at least one 16x16 sprite flame on the building')
            check(maxBgFlame==0,'active town flames use OAM sprites instead of BG flame tiles')
            check(flameAt180>=2,'building flames stay lit for at least 180 frames')
            check(sawFlip0 and sawFlip1,'burning sprite flames animate between frames')
            check(ch>=4,'flames eventually expire into char marks')
            check(spFl==0,'no sprite flames remain once the ~10s timer expires')
            check(blanked==0,'no building tile is blanked to sky')
            check(foreign==0,'no other nametable tile changed')
            check(liveSlots()<=16,'scorch ring stays bounded')
            -- Phase 2: reload base street and test ground fires + 16-fire eviction + room-leave clear.
            wantLoad=true
        end
    elseif phase==2 then
        if age==50 then
            local spFl=spriteFlames()
            screenshot('town-fire-ground')
            check(spFl>=2,'crouching breath ignites the village ground ('..spFl..' flame sprites)')
        end
        if age==400 then
            local _,ch=counts()
            local spFl=spriteFlames()
            local live=liveSlots()
            f:write(string.format('p2 spFl=%d ch=%d live=%d mode=%d room=%d sroom=%d page=%02X x=%02X\n',
                spFl,ch,live,r(0x736),r(0x561),r(0x646A),r(0x3B),r(0x4D)))
            check(spFl>=6,'multiple lasting sprite fires stay lit across the street')
            check(live<=16,'active fire ring never exceeds 16 slots ('..live..')')
            check(ch>=4,'exceeding 16 fires evicts the oldest fire to char ('..ch..' char tiles)')
            -- Simulate leaving the room ($0561 change) and verify ring clears on next update.
            w(0x561,2)
        end
        if age==405 then
            local spFl=spriteFlames()
            f:write(string.format('p2_end live=%d spFl=%d mode=%d room=%d sroom=%d\n',
                liveSlots(),spFl,r(0x736),r(0x561),r(0x646A)))
            check(liveSlots()==0 and spFl==0,'leaving the room clears all active fire slots and sprite flames')
            f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close()
            stopScenario(errors==0 and 0 or 1)
        end
    end
end,emu.eventType.endFrame)
