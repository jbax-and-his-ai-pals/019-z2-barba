-- Native Rauru room/generator, then controlled actor positions for reactions.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local frame,age,phase,errors=0,0,0,0
local base,slot,pending=nil,nil,false
local fled,burned,flame,dialog,closed=false,false,false,false,false
local startX=0
local doorAddress=nil
local enteredDoor=false
local f=assert(io.open(OUTPUT_DIR..'/town.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
local function setup()
    emu.loadSavestate(base);age=0
    w(0x4D,80);w(0x3B,0);w(0x29,176);w(0x57D,0);w(0x479,0)
    w(0x8D,0);w(0x8E,0);w(0x5F8,0);w(0x5FE,0);w(0x400,0);w(0x76F,0)
    w(0xB6+slot,1);w(0x4E+slot,112);w(0x3C+slot,0);w(0x2A+slot,176)
    w(0xAF+slot,phase==1 and 0 or 0x80);w(0x71+slot,0);w(0x5C3+slot,0)
    if phase==3 then w(0xBC+slot,5);w(0xAF+slot,0)end
    if phase==4 then w(0xA1+slot,0x19)end
    for x=0,5 do if r(0xA1+x)==0x23 then w(0xB6+x,0)end end
    if phase==5 then
        for page=0,3 do
            local baseAddress=0x6000+page*0xD0
            for column=0,15 do
                if not doorAddress and r(baseAddress+0xA0+column)==0x8B then
                    doorAddress=baseAddress+0xB0+column
                    local worldX=page*256+column*16-14
                    w(0x4E+slot,worldX%256);w(0x3C+slot,math.floor(worldX/256)%256)
                    w(0xAF+slot,0x80);w(0x60+slot,1)
                end
            end
        end
        check(doorAddress~=nil,'native street contains a closed refuge doorway')
    end
    startX=r(0x4E+slot)
end
emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then
        b={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
        if phase==2 or phase==3 then b.b=age>=8 and age<11 end
        if phase==4 then b.up=age>=8 and age<11;b.b=age>=400 and age<403 end
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addMemoryCallback(function()
    if phase==4 then
        local pointer=LABELS.TownFearPointers+(r(0xA1+slot)-0x19)*2
        if r(0x569)+256*r(0x56A)==r(pointer)+256*r(pointer+1) then dialog=true end
    end
end,emu.callbackType.exec,0xB614)
emu.addMemoryCallback(function()
    if not pending then return end
    pending=false
    if not base then
        base=emu.createSavestate();check(r(0x707)==1 and r(0x561)==0,'native Rauru street loaded')
        check(r(0xBC+slot)==255,'native generator supplied the random wanderer')
    end
    phase=phase+1
    if phase>5 then
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close();stopScenario(errors==0 and 0 or 1);return
    end
    setup()
end,emu.callbackType.exec,0xC07B)
emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        w(0x707,1);w(0x706,0);w(0x769,3);w(0x561,0)
        w(0x701,0);w(0x75C,0);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1)
    end
    if not base and frame>1150 then
        for x=0,5 do
            if r(0xB6+x)==1 and r(0xBC+x)==255 and r(0xA1+x)>=0x19 and r(0xA1+x)<=0x1C then slot=x;pending=true;break end
        end
        if frame==1800 then check(false,'native wanderer spawned');f:close();stopScenario(1)end
        return
    end
    if not base then return end
    age=age+1
    if phase==1 and r(0xAF+slot)==0x80 and r(0x4E+slot)>startX then fled=true end
    if phase==2 then
        if r(0xAF+slot)>=0xC0 then
            burned=true
            local oam=r(0x91+slot)
            if r(0x201+oam)==0x84 then flame=true end
            if age==30 then screenshot('town-burning')end
        end
    end
    if phase==4 then
        if age==380 then screenshot('town-fear-dialogue')end
        if dialog and age>405 and r(0x74C)==0 and r(0xDE)==0 then closed=true end
    end
    if phase==5 and r(0xAF+slot)>0 and r(0xAF+slot)<0x42 then enteredDoor=true end
    local limit=phase==4 and 460 or 90
    if age==limit then
        if phase==1 then check(fled,'random outdoor wanderer flees from Barba');screenshot('town-fleeing')end
        if phase==2 then
            check(burned and flame,'real player fireball ignites random wanderer using native OAM')
            check(r(0xB6+slot)==0,'burning ends by despawning the random wanderer')
        end
        if phase==3 then check(r(0xB6+slot)==1 and r(0xAF+slot)<0xC0,'same walking type with scripted origin survives fire')end
        if phase==4 then check(dialog,'Up conversation selects fear text only for generated wanderer');check(closed,'fear dialogue closes and restores gameplay')end
        if phase==5 then
            check(enteredDoor and r(0xB6+slot)==0,'wanderer enters a real doorway, closes it and stays inside')
        end
        check(r(0x736)==11 and r(0x774)>0,'town remains playable after phase '..phase)
        pending=true
    end
end,emu.eventType.endFrame)
