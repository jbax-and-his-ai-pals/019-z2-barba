-- Unreal Tournament town combo banner: tiers, escalation, pause hide, decay.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local oamSlots={0xDC,0xE0,0xE4,0xE8,0xEC,0xF0,0xF4,0xFC,0x28,0x2C,0x30,0x34}
local function countBanner()
    local n,pal1,pal2,flames=0,0,0,0
    for _,o in ipairs(oamSlots) do
        local y=r(0x200+o)
        if y>=0x20 and y<0xE0 then
            n=n+1
            local attr=r(0x200+o+2)&0x03
            if attr==1 then pal1=pal1+1 elseif attr==2 then pal2=pal2+1 end
            if r(0x200+o+1)==0x84 then flames=flames+1 end
        end
    end
    return n,pal1,pal2,flames
end

local frame,age,errors=0,0,0
local active=false
local f=assert(io.open(OUTPUT_DIR..'/town_combo.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end

local t1Ok,t3Ok,t5Ok,t6Ok,t6FlamesOk,pauseHideOk,blinkOffOk,decayOk=false,false,false,false,false,false,false,false
local t5Pal1,t5Pal2=false,false
local wantPause=false

emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then
        b={start=wantPause,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        w(0x707,1);w(0x706,0);w(0x769,3);w(0x561,1)
        w(0x701,0);w(0x75C,0);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1)
    end
    if not active and frame>1150 and r(0x736)==11 and r(0x726)==0 then
        active=true;age=0
    end
    if not active then return end
    age=age+1
    -- Tier 1: 2 kills = 6 pts (DOUBLE KILL!)
    if age==5 then w(0x646C,6) end
    if age==10 then
        local n,p1,p2=countBanner()
        t1Ok=(r(0x646E)==1 and n==11 and p2==11 and p1==0)
    end
    -- Tier 3: +6 pts = 12 pts (MEGA KILL!, palette 1 fire)
    if age==15 then w(0x646C,6) end
    if age==20 then
        local n,p1,p2=countBanner()
        t3Ok=(r(0x646E)==3 and n==9 and p1==9 and p2==0)
    end
    -- Tier 5: +6 pts = 18 pts (MONSTER KILL!, 12 sprites, strobe pal1/pal2)
    if age==25 then w(0x646C,6) end
    if age>=28 and age<=38 then
        local n,p1,p2=countBanner()
        if r(0x646E)==5 and n==12 then t5Ok=true end
        if p1>0 then t5Pal1=true end
        if p2>0 then t5Pal2=true end
    end
    -- Tier 6: +3 pts = 21 pts (GODLIKE!, 8 letters + 2 flanking flames = 10)
    if age==40 then w(0x646C,3) end
    if age==45 then
        local n,_,_,flames=countBanner()
        t6Ok=(r(0x646E)==6 and n==10)
        t6FlamesOk=(flames==2)
    end
    -- Pause hides OAM cleanly
    if age==50 then wantPause=true end
    if age==53 then wantPause=false end
    if age>=58 and age<=75 and (r(0x736)~=11 or r(0x74C)~=0 or r(0x524)~=0) then
        local n=countBanner()
        if n==0 then pauseHideOk=true end
    end
    if age==80 then wantPause=true end
    if age==83 then wantPause=false end
    -- Let combo decay from COMBO_TIMER (~180 unpaused frames -> expires ~age 255)
    if age>=200 and age<=295 then
        local n=countBanner()
        if r(0x646E)==6 and n==0 then blinkOffOk=true end
        if r(0x646E)==0 and r(0x646D)==0 and n==0 then decayOk=true end
    end
    if age==300 then
        check(t1Ok,'Tier 1 DOUBLE KILL! draws 11 sprites in pale palette 2')
        check(t3Ok,'Tier 3 MEGA KILL! draws 9 sprites in fire palette 1')
        check(t5Ok and t5Pal1 and t5Pal2,'Tier 5 MONSTER KILL! draws 12 sprites and strobes pal 1/2')
        check(t6Ok and t6FlamesOk,'Tier 6 GODLIKE! draws 8 letters + 2 flanking flames')
        check(pauseHideOk,'Pause menu hides all 12 combo OAM slots')
        check(blinkOffOk,'Combo banner blinks during decay warning window')
        check(decayOk,'Combo resets score/tier and clears OAM when timer expires')
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close();stopScenario(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
