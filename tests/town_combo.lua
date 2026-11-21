-- Unreal Tournament town combo banner: tiers, escalation, pause hide, decay.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local oamSlots={0xDC,0xE0,0xE4,0xE8,0xEC,0xF0,0xF4,0xFC,0x34,0x64,0xAC,0x94,0x00,0x28,0x2C,0x30}
local counterSlots={0x00,0x28,0x2C,0x30}
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

local function counterMatches(y,tiles)
    for i,o in ipairs(counterSlots) do
        local a=0x200+o
        if tiles[i] then
            if r(a)~=y or r(a+1)~=tiles[i] then return false end
        elseif r(a)<0xF0 then return false end
    end
    return true
end

local function counterSurvives(y,tiles)
    local firstX
    for s=0x6500,0x65FC,4 do
        if r(s)==y and r(s+1)==(tiles[1]~1) then firstX=r(s+3);break end
    end
    if not firstX then return false end
    for line=y+1,y+16 do
        local sprites,glyphs=0,0
        for s=0x6500,0x65FC,4 do
            if r(s)<line and line<=r(s)+16 then
                sprites=sprites+1
                local x=r(s+3)-firstX
                local tile=tiles[x//8+1]
                if sprites<=8 and r(s)==y and x%8==0 and tile and r(s+1)==(tile~1) then
                    glyphs=glyphs+1
                end
            end
        end
        if sprites<=8 or glyphs~=#tiles then return false end
    end
    return true
end

local frame,age,errors=0,0,0
local active=false
local f=assert(io.open(OUTPUT_DIR..'/town_combo.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end

local t0Ok,t1Ok,t2Ok,t4Ok,t5Ok,t5FlamesOk,t5NoCloudsOk,t3dOk,pauseHideOk,blinkOffOk,decayOk=false,false,false,false,false,false,false,false,false,false,false
local t4Pal1,t4Pal2=false,false
local t1Crowded,t3Crowded,t5Crowded=false,false,false
local wantPause=false

-- Seed town traffic on the counter's scanlines, away from the text in X.
-- These entries all follow the dedicated counter slots but precede the old $D8 slot.
emu.addMemoryCallback(function()
    if age~=9 and age~=28 and age~=48 then return end
    local y=r(0x2DC)+(age==48 and 0x10 or 0x20)
    for i=0,7 do
        local a=0x268+i*4
        w(a,y);w(a+1,0x04);w(a+2,0);w(a+3,8+i*8)
    end
end,emu.callbackType.exec,0xC18B) -- gameplay NMI jumps to NmiRng6 to copy the OAM shadow

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
        local y,tiles=r(0x2DC)+0x20,{0x6C,0x78,0x7A}
        t1Ok=(r(0x646E)==1 and n==13 and p2==13 and p1==0 and counterMatches(y,tiles))
        t1Crowded=counterSurvives(y,tiles)
    end
    -- Tier 2: +12 pts = 24 pts (MEGA KILL! + X24 = 12 sprites, palette 1 fire)
    if age==15 then w(0x646C,12) end
    if age==20 then
        local n,p1,p2=countBanner()
        t2Ok=(r(0x646E)==2 and n==12 and p1==12 and p2==0 and counterMatches(r(0x2DC)+0x20,{0x6C,0x7A,0x9E}))
    end
    -- Tier 3: +16 pts = 40 pts (ULTRA KILL! + X40).
    if age==25 then w(0x646C,16) end
    if age==29 then
        t3Crowded=r(0x646E)==3 and counterSurvives(r(0x2DC)+0x20,{0x6C,0x9E,0x9F})
    end
    -- Tier 4: +20 pts = 60 pts (MONSTER KILL! + X60 = 15 sprites, strobe pal1/pal2)
    if age==32 then w(0x646C,20) end
    if age>=34 and age<=39 then
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
        t5Ok=(r(0x646E)==5 and n==13 and flameY==row1Y+3 and counterMatches(row1Y+0x10,{0x6C,0xA6,0xA0}))
        t5FlamesOk=(flames==2)
        local clouds=0
        for o=0x68,0xFC,4 do
            local y=r(0x6500+o)
            local t=r(0x6501+o)
            if y<0xF0 and (t==0x89 or t==0x8B or t==0x8D) then clouds=clouds+1 end
        end
        t5NoCloudsOk=(clouds>=4)
    end
    -- 3-digit counter: +20 pts = 105 pts (GODLIKE! + 2 flames + X105 = 14 sprites)
    if age==47 then w(0x646C,20) end
    if age==49 then
        local n=countBanner()
        local y,tiles=r(0x2DC)+0x10,{0x6C,0x78,0x9F,0xA0}
        t3dOk=(r(0x646D)==105 and n==14 and counterMatches(y,tiles))
        t5Crowded=counterSurvives(y,tiles)
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
        check(t1Crowded,'MULTI KILL! keeps X12 on every crowded scanline')
        check(t2Ok,'Tier 2 MEGA KILL! + X24 draws 12 sprites in fire palette 1')
        check(t3Crowded,'ULTRA KILL! keeps X40 on every crowded scanline')
        check(t4Ok and t4Pal1 and t4Pal2,'Tier 4 MONSTER KILL! + X60 draws 15 sprites and strobes pal 1/2')
        check(t5Ok and t5FlamesOk and t5NoCloudsOk,'Tier 5 GODLIKE! + X85 draws 8 letters + 2 flames + counter while keeping clouds')
        check(t3dOk,'3-digit combo counter X105 draws 14 sprites with exact digits')
        check(t5Crowded,'GODLIKE! keeps X105 on every crowded scanline')
        check(pauseHideOk,'Pause menu hides all 16 combo OAM slots')
        check(blinkOffOk,'Combo banner blinks during decay warning window')
        check(decayOk,'Combo resets score/tier and clears OAM when timer expires')
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close();stopScenario(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
