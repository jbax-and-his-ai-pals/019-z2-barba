-- Outdoor town chimney smoke: detection, rising puffs, tail OAM, and combo/fire yield.
-- Run with the generated world/barba-test.nes so darunia.mss matches the ROM.
dofile(TEST_DIR..'/newgame.lua')
local folder=assert(emu.getRomInfo().path:match('^(.*)[/\\][^/\\]+$'))
local stateFile=assert(io.open(folder..'/darunia.mss','rb'),
    'Use --rom with the Towns and World test-pack ROM next to darunia.mss')
local state=stateFile:read('*a')
stateFile:close()

local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local f=assert(io.open(OUTPUT_DIR..'/town_smoke.txt','w'))
local errors=0
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end

local function findSmokePuffs()
    local puffs={}
    for s=0x6568,0x65FC,4 do
        local y=r(s)
        local tile=r(s+1)
        local attr=r(s+2)
        if y<0xF0 and attr==0x21 and (tile==0x8F or tile==0x91 or tile==0x93) then
            puffs[#puffs+1]={slot=s,y=y,tile=tile,x=r(s+3)}
        end
    end
    return puffs
end

local function anyForegroundSmoke()
    for s=0x6500,0x6564,4 do
        local y=r(s)
        local tile=r(s+1)
        local attr=r(s+2)
        if y<0xF0 and attr==0x21 and (tile==0x8F or tile==0x91 or tile==0x93) then
            return true
        end
    end
    return false
end

local stage,age=0,0
local seenTiles={}
local minY,maxY=255,0

emu.addMemoryCallback(function()
    if stage~=0 then return end
    assert(emu.loadSavestate(state),'Darunia F6 failed to load')
    stage=1
end,emu.callbackType.exec,0xC010)

emu.addEventCallback(function()
    local b={start=false,select=false,a=false,b=(stage==2 and age<=15 and (age%4<2)),up=false,down=false,left=false,right=(stage==1 and age<=30)}
    emu.setInput(b,0)
end,emu.eventType.inputPolled)

emu.addEventCallback(function()
    if stage==0 then return end
    age=age+1
    if stage==1 then
        local count=r(0x6342)
        local puffs=findSmokePuffs()
        for _,p in ipairs(puffs) do
            seenTiles[p.tile]=true
            if p.y<minY then minY=p.y end
            if p.y>maxY then maxY=p.y end
        end
        if age==2 then
            check(count>=1 and count<=4,'Darunia detects chimneys ('..count..')')
            check(not anyForegroundSmoke(),'Smoke never uses foreground OAM slots ($6500..$6564)')
        end
        if age==100 then
            check(seenTiles[0x8F] and seenTiles[0x91] and seenTiles[0x93],'Smoke cycles through all 3 puff stages')
            check(maxY-minY>=16,'Smoke puffs rise vertically ('..minY..'..'..maxY..')')
            stage=2
            age=0
            w(0x646C,12)
        end
    elseif stage==2 then
        if age==10 then
            local tier=r(0x646E)
            local puffs=findSmokePuffs()
            local highSmoke=false
            for _,p in ipairs(puffs) do
                if p.y<0x48 then highSmoke=true end
            end
            check(tier>=1,'Combo banner active (tier '..tier..')')
            check(not highSmoke,'Smoke yields in combo Y band (<$48) during active combo')
            check(not anyForegroundSmoke(),'Smoke stays out of foreground OAM during fire+combo')
            f:write(errors==0 and 'RESULT PASS\n' or 'RESULT FAIL\n');f:close()
            emu.stop(errors==0 and 0 or 1)
        end
    end
end,emu.eventType.endFrame)
