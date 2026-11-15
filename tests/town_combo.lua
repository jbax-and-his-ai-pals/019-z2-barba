-- Unreal Tournament town combo banner: tiers, escalation, pause hide, decay.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local oamSlots={0xDC,0xE0,0xE4,0xE8,0xEC,0xF0,0xF4,0xFC,0x28,0x2C,0x30,0x34,0xD8,0xC4,0xAC,0x94}
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

local t0Ok,t1Ok,t2Ok,t4Ok,t5Ok,t5FlamesOk,t3dOk,pauseHideOk,blinkOffOk,decayOk=false,false,false,false,false,false,false,false,false,false
local t4Pal1,t4Pal2=false,false
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
    -- Below Tier 1: 11 pts stays inactive (no DOUBLE KILL!)
    if age==2 then w(0x646C,11) end
    if age==4 then
        local n=countBanner()
        t0Ok=(r(0x646D)==11 and r(0x646E)==0 and n==0)
    end
    -- Tier 1: +1 = 12 pts (MULTI KILL! + X12 = 13 sprites)
    if age==5 then w(0x646C,1) end
    if age==10 then
        local n,p1,p2=countBanner()
        local y0=r(0x200+oamSlots[11])
        local t0,t1,t2=r(0x200+oamSlots[11]+1),r(0x200+oamSlots[12]+1),r(0x200+oamSlots[13]+1)
        t1Ok=(r(0x646E)==1 and n==13 and p2==13 and p1==0 and y0==r(0x200+0xDC)+0x20 and t0==0x6C and t1==0x78 and t2==0x7A)
    end
    -- Tier 2: +12 pts = 24 pts (MEGA KILL! + X24 = 12 sprites, palette 1 fire)
    if age==15 then w(0x646C,12) end
    if age==20 then
        local n,p1,p2=countBanner()
        local t0,t1,t2=r(0x200+oamSlots[10]+1),r(0x200+oamSlots[11]+1),r(0x200+oamSlots[12]+1)
        t2Ok=(r(0x646E)==2 and n==12 and p1==12 and p2==0 and t0==0x6C and t1==0x7A and t2==0x9E)
    end
    -- Tier 4: +36 pts = 60 pts (MONSTER KILL! + X60 = 15 sprites, strobe pal1/pal2)
    if age==25 then w(0x646C,36) end
    if age>=28 and age<=38 then
        local n,p1,p2=countBanner()
        if r(0x646E)==4 and n==15 then t4Ok=true end
        if p1>0 then t4Pal1=true end
        if p2>0 then t4Pal2=true end
    end
    -- Tier 5: +25 pts = 85 pts (GODLIKE! + 2 flames + X85 = 13 sprites)
    if age==40 then w(0x646C,25) end
    if age==45 then
        local n,_,_,flames=countBanner()
        local row1Y=r(0x200+0xDC)
        local flameY
        for _,o in ipairs(oamSlots) do
            if r(0x200+o+1)==0x84 then flameY=r(0x200+o); break end
        end
        local cy,c0,c1,c2=r(0x200+oamSlots[11]),r(0x200+oamSlots[11]+1),r(0x200+oamSlots[12]+1),r(0x200+oamSlots[13]+1)
        t5Ok=(r(0x646E)==5 and n==13 and flameY==row1Y+3 and cy==row1Y+0x10 and c0==0x6C and c1==0xA6 and c2==0xA0)
        t5FlamesOk=(flames==2)
    end
    -- 3-digit counter: +20 pts = 105 pts (GODLIKE! + 2 flames + X105 = 14 sprites)
    if age==47 then w(0x646C,20) end
    if age==49 then
        local n=countBanner()
        local c0,c1,c2,c3=r(0x200+oamSlots[11]+1),r(0x200+oamSlots[12]+1),r(0x200+oamSlots[13]+1),r(0x200+oamSlots[14]+1)
        t3dOk=(r(0x646D)==105 and n==14 and c0==0x6C and c1==0x78 and c2==0x9F and c3==0xA0)
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
        if r(0x646E)==5 and n==0 then blinkOffOk=true end
        if r(0x646E)==0 and r(0x646D)==0 and n==0 then decayOk=true end
    end
    if age==300 then
        check(t0Ok,'11 pts stays at tier 0 with no banner (DOUBLE KILL dropped)')
        check(t1Ok,'Tier 1 MULTI KILL! + X12 draws 13 sprites in pale palette 2')
        check(t2Ok,'Tier 2 MEGA KILL! + X24 draws 12 sprites in fire palette 1')
        check(t4Ok and t4Pal1 and t4Pal2,'Tier 4 MONSTER KILL! + X60 draws 15 sprites and strobes pal 1/2')
        check(t5Ok and t5FlamesOk,'Tier 5 GODLIKE! + X85 draws 8 letters + 2 flames + counter')
        check(t3dOk,'3-digit combo counter X105 draws 14 sprites with exact digits')
        check(pauseHideOk,'Pause menu hides all 16 combo OAM slots')
        check(blinkOffOk,'Combo banner blinks during decay warning window')
        check(decayOk,'Combo resets score/tier and clears OAM when timer expires')
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close();stopScenario(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
