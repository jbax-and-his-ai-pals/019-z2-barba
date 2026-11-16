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
-- Flame and char share their lower-half tiles ($A7/$C2); only the top halves tell them apart.
local FLAME={[0xAC]=true,[0xA4]=true}
local CHAR={[0xC1]=true,[0xC0]=true}
local SHARED={[0xA7]=true,[0xC2]=true}
local frame,age,phase,errors=0,0,0,0
local pending,wantLoad,base=false,false,nil
local metatiles,nametable=nil,nil
local maxFlame,maxChar,blanked,foreign=0,0,0,0
local flameSeenAt,charSeenAt,flameAt180=nil,nil,0
local animAddr,saw02,saw04=nil,false,false
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
            local fl,ch=counts()
            if fl>maxFlame then maxFlame=fl end
            if ch>maxChar then maxChar=ch end
            if fl>0 and not flameSeenAt then
                flameSeenAt=age
                for a=0x2000,0x27BF do
                    if (a%0x400)<0x3C0 and emu.read(a,p)==0xAC then animAddr=a; break end
                end
            end
            if animAddr then
                local t=emu.read(animAddr,p)
                if t==0xAC then saw02=true elseif t==0xA4 then saw04=true end
            end
            if ch>0 and not charSeenAt then charSeenAt=age end
            if fl>0 and age-(flameSeenAt or age)==6 then screenshot('town-fire-flame')end
            if age==WALK+210 then flameAt180=fl end
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
                        elseif not FLAME[t] and not CHAR[t] and not SHARED[t] then foreign=foreign+1 end
                    end
                end
            end
            local fl,ch=counts()
            f:write(string.format('p1 maxFlame=%d flameAt180=%d maxChar=%d flameAt=%s charAt=%s endFlame=%d endChar=%d blanked=%d foreign=%d\n',
                maxFlame,flameAt180,maxChar,tostring(flameSeenAt),tostring(charSeenAt),fl,ch,blanked,foreign))
            check(same,'room metatiles (collision) are unchanged after the attack')
            check(maxFlame>=4,'fireballs ignite at least one 2x2 flame on the building')
            check(flameAt180>=4,'building flames stay lit for at least 180 frames')
            check(saw02 and saw04,'burning flame tiles animate between frames')
            check(ch>=4,'flames eventually expire into char marks')
            check(fl==0,'no flame tiles remain once the ~10s timer expires')
            check(blanked==0,'no building tile is blanked to sky')
            check(foreign==0,'no other nametable tile changed')
            check(liveSlots()<=16,'scorch ring stays bounded')
            -- Phase 2: reload base street and test ground fires + 16-fire eviction + room-leave clear.
            wantLoad=true
        end
    elseif phase==2 then
        if age==50 then
            local fl,_=counts()
            screenshot('town-fire-ground')
            check(fl>=4,'crouching breath ignites the village ground ('..fl..' flame tiles)')
        end
        if age==400 then
            local fl,ch=counts()
            local live=liveSlots()
            f:write(string.format('p2 fl=%d ch=%d live=%d mode=%d room=%d sroom=%d page=%02X x=%02X\n',
                fl,ch,live,r(0x736),r(0x561),r(0x646A),r(0x3B),r(0x4D)))
            check(fl>=16,'multiple lasting fires stay lit across the street')
            check(live<=16,'active fire ring never exceeds 16 slots ('..live..')')
            check(ch>=4,'exceeding 16 fires evicts the oldest fire to char ('..ch..' char tiles)')
            -- Simulate leaving the room ($0561 change) and verify ring clears on next update.
            w(0x561,2)
        end
        if age==405 then
            f:write(string.format('p2_end live=%d mode=%d room=%d sroom=%d\n',
                liveSlots(),r(0x736),r(0x561),r(0x646A)))
            check(liveSlots()==0,'leaving the room clears all active fire slots')
            f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close()
            stopScenario(errors==0 and 0 or 1)
        end
    end
end,emu.eventType.endFrame)
