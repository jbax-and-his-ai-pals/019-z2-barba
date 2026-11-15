-- Native Rauru room/generator, then controlled actor positions for reactions.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local frame,age,phase,errors=0,0,0,0
local base,slot,pending=nil,nil,false
local fled,burned,flame,dialog,closed=false,false,false,false,false
local ashes=false
local requests,fastComplete=0,false
local startX=0
local doorAddress=nil
local enteredDoor=false
local doorTiles=nil
local hiddenAtDoor=false
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
    if phase==3 then w(0xA1+slot,0x0F);w(0xBC+slot,5);w(0xAF+slot,0)end
    if phase==2 then
        w(0xAF+slot,0)
        for x=0,5 do if x~=slot then w(0xB6+x,0)end end
    end
    if phase==4 then w(0xA1+slot,0x19);w(0x4E+slot,112);w(0x71+slot,0x10)end
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
        doorTiles={}
        for a=0x6000,0x633F do doorTiles[#doorTiles+1]=r(a)end
    end
    startX=r(0x4E+slot)
end
emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then
        b={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
        if phase==2 or phase==3 then b.b=age>=8 and age<11 end
        if phase==4 then b.up=age<220;b.right=age<120;b.b=age>=180 and age<183 end
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addMemoryCallback(function()
    if phase==4 then
        requests=requests+1
        local actual=r(0x569)+256*r(0x56A)
        for idx=0,7 do
            local pointer=LABELS.TownFearPointers+idx*2
            if actual==r(pointer)+256*r(pointer+1) then dialog=true end
        end
    end
end,emu.callbackType.exec,LABELS.TownFastDialogReady)
emu.addMemoryCallback(function()
    if not pending then return end
    pending=false
    if not base then
        base=emu.createSavestate();check(r(0x707)==1 and r(0x561)==1,'native Rauru street loaded')
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
        w(0x707,1);w(0x706,0);w(0x769,3);w(0x561,1)
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
    if phase==1 and r(0xAF+slot)==0x80 and r(0x4E+slot)~=startX then fled=true end
    if phase==2 then
        if r(0xAF+slot)>=0xA0 and r(0xAF+slot)<0xC0 then
            if not ashes then screenshot('town-ash')end
            ashes=true
        end
        if r(0xAF+slot)>=0xC0 then
            burned=true
            local oam=r(0x91+slot)
            if r(0x201+oam)==0x84 then flame=true end
            if age==30 then screenshot('town-burning')end
        end
    end
    if phase==2 and age==110 then screenshot('town-ash')end
    if phase==4 then
        local pointer=r(0x569)+256*r(0x56A)
        if age<=150 and dialog and pointer>=0xB803 and pointer<0xBF70
            and emu.read(3*0x4000+pointer-0x8000,emu.memType.nesPrgRom)==0xFF then fastComplete=true end
        if age==130 then screenshot('town-fear-dialogue')end
        if dialog and age>230 and r(0x74C)==0 and r(0xDE)==0 then closed=true end
    end
    if phase==5 and r(0xB6+slot)==0 and not enteredDoor then
        enteredDoor=true;hiddenAtDoor=true
        local oam=r(0x91+slot)
        for offset=0,12,4 do if r(0x200+oam+offset)~=0xF8 then hiddenAtDoor=false end end
    end
    local limit=phase==4 and 280 or (phase==2 and 190 or 90)
    if age==limit then
        if phase==1 then check(fled,'random outdoor wanderer flees from Barba');screenshot('town-fleeing')end
        if phase==2 then
            check(burned and flame,'real player fireball ignites random wanderer using native OAM')
            check(ashes,'burning leaves a temporary ash pile')
            check(r(0xB6+slot)==0,'ash pile expires and releases its actor slot')
        end
        if phase==3 then check(r(0xB6+slot)==1 and r(0xAF+slot)<0xC0,'same walking type with scripted origin survives fire')end
        if phase==4 then
            check(dialog,'held Up catches a fleeing villager from outside the old talk radius')
            check(fastComplete,'complete panic message renders within 150 frames of approach')
            check(requests==1,'holding Up does not repeatedly reopen dialogue')
            check(closed,'fear dialogue closes and restores gameplay')
        end
        if phase==5 then
            check(enteredDoor and hiddenAtDoor,'wanderer despawns and hides at the real doorway')
            local unchanged=true
            for a=0x6000,0x633F do if r(a)~=doorTiles[a-0x6000+1]then unchanged=false end end
            check(unchanged,'refuge entry creates no doors or background collision changes')
        end
        check(r(0x736)==11 and r(0x774)>0,'town remains playable after phase '..phase)
        pending=true
    end
end,emu.eventType.endFrame)
