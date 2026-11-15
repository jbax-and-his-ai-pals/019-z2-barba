-- Shout word sprites follow the shouting villager, then clean up on expiry,
-- doorway, burn, scene change, Up-talk and the pause menu.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local WORD,SLOT,TIMER=0x6467,0x6465,0x6468
local OAM=0x2E0
local frame,age,phase,errors=0,0,0,0
local base,slot,pending=nil,nil,false
local f=assert(io.open(OUTPUT_DIR..'/shout-follow.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
local oamSlots={0x2DC,0x2E0,0x2E4,0x2E8,0x2EC,0x2F0,0x2F4}
local lengths={8,8,4,6,7,5,8,3,6}
local words={
    {0,1,3,4,5,6,7},   -- 1 OH SHIT!
    {0,1,3,4,5,6,7},   -- 2 OH FUCK!
    {0,1,2,3},         -- 3 RUN!
    {0,1,3,4,5},       -- 4 OH NO!
    {0,1,3,4,5,6},     -- 5 OH GOD!
    {0,1,2,3,4},       -- 6 HELP!
    {0,1,2,3,5,6,7},   -- 7 SAVE ME!
    {0,1,2},           -- 8 NO!
    {0,1,2,3,4,5},     -- 9 BARBA!
}
local function glyphsVisible()
    local n=0
    for _,a in ipairs(oamSlots) do if r(a)<0xEF then n=n+1 end end
    return n
end
-- Actor's own sprite box from its native OAM block this same frame.
local function actorBox()
    local base=r(0x91+slot)
    local minX,minY,n=999,999,0
    for i=0,5 do
        local a=0x200+base+i*4
        if r(a)<0xEF then
            n=n+1
            if r(a)<minY then minY=r(a) end
            if r(a+3)<minX then minX=r(a+3) end
        end
    end
    return n,minX,minY
end
local function anyHiddenBreak()
    return glyphsVisible()==0
end
-- Phase state
local seen,firstAt,firstWord,rotatedWord,tracked,maxErr,scrolled,startScroll=false,nil,nil,nil,0,0,false,nil
local expired,hiddenAfter=false,true
local doorX,doorNt,despawnHidden,despawned,doorSeen,doorOpened,doorClosed=nil,nil,false,false,false,false,false
local placedAt=nil
local glyphBg=false
-- Background tiles replaced by the bank-7 glyph pairs (odd bytes) and the
-- relocated town fire flame/char tiles (bank 7 singles).
local replaced={}
for _,pair in ipairs({0x32,0x7E,0x80,0x84,0x86,0x88,0x8A,0x8C,0x92,0x94,0x9C,0x9E,0xA0,0xA2,0xA8,0xAA,0xBA,0xBC,0xBE}) do
    replaced[pair]=true;replaced[pair+1]=true
end
for _,t in ipairs({0x34,0xA4,0xAC,0xC0,0xC1}) do replaced[t]=true end
-- Fire char tiles must not appear in the native spell-menu pane.
local menuFire={[0x35]=true,[0xA7]=true,[0xC2]=true}
local menuFireSeen={}
function menuFireOnScreen()
    local p=emu.memType.nesPpuMemory
    for a=0x2000,0x27BF do
        local t=emu.read(a,p)
        if (a%0x400)<0x3C0 and menuFire[t] then menuFireSeen[t]=true end
    end
end
function glyphTilesOnScreen()
    local p=emu.memType.nesPpuMemory
    for a=0x2000,0x27BF do
        if (a%0x400)<0x3C0 and replaced[emu.read(a,p)] then return true end
    end
    return false
end
local function playerX() return r(0x4D)+256*r(0x3B) end
local burned,burnHidden=false,false
local sceneHidden=false
local talkStarted,talkHidden,talkFrames=false,true,0
local menuOpened,menuHidden,menuFrames=false,true,0
local function setup()
    emu.loadSavestate(base);age=0
    w(0x4D,80);w(0x3B,0);w(0x29,176);w(0x57D,0);w(0x479,0)
    w(0x8D,0);w(0x8E,0);w(0x5F8,0);w(0x5FE,0);w(0x400,0);w(0x76F,0)
    for x=0,5 do if r(0xA1+x)==0x23 or x~=slot then w(0xB6+x,0) end end
    w(0xB6+slot,1);w(0xBC+slot,255);w(0xA1+slot,0x1B)
    w(0x4E+slot,112);w(0x3C+slot,0);w(0x2A+slot,176)
    w(0xAF+slot,0);w(0x71+slot,0);w(0x5C3+slot,0)
    w(0x5EA,0)
    for a=0x6460,0x6468 do w(a,0) end
    if phase==3 then
        -- Doorway: put the villager just left of a real closed door,
        -- fleeing right, with the player nearby so both are on screen.
        doorX=nil
        for page=0,3 do
            local baseAddress=0x6000+page*0xD0
            for column=0,15 do
                if not doorX and r(baseAddress+0xA0+column)==0x8B then
                    doorX=page*256+column*16
                    doorNt=((page%2==1) and 0x2400 or 0x2000)+0x280+column*2
                end
            end
        end
        check(doorX~=nil,'door phase: native street has a closed doorway')
        -- Barba walks toward the door so the camera scrolls there; the
        -- villager is placed once he arrives.
        w(0xB6+slot,0);placedAt=nil
    end
end
emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then
        b={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
        if base then
            if phase==1 then b.right=age>=20 and age<80 end
            if phase==3 then b.right=doorX~=nil and not placedAt and playerX()<doorX-100 end
            if phase==4 then b.b=age>=8 and age<11 end
            if phase==6 then b.up=age>=10 and age<40 end
            if phase==7 then b.start=age>=10 and age<13 end
            if phase==7 and age>=60 and age<63 then b.start=true end
        end
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addMemoryCallback(function()
    if not pending then return end
    pending=false
    if not base then
        base=emu.createSavestate()
        check(r(0x707)==1 and r(0x561)==1,'native Rauru street loaded')
    end
    phase=phase+1
    if phase>9 then
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
    if not base or pending then return end
    age=age+1
    local word=r(WORD)
    local vis=glyphsVisible()
    if phase==1 then
        -- Panic, flee, follow; then expiry.
        if word~=0 and vis>0 then
            if not seen then seen=true;firstAt=age;firstWord=word end
            local n,ax,ay=actorBox()
            if n==4 and r(0xB6+slot)==1 then
                local len=lengths[word]
                local cols=words[word]
                local left=ax+8-4*len
                local err=0
                for idx,col in ipairs(cols) do
                    local a=oamSlots[idx]
                    local gx=left+8*col
                    if gx>=4 and gx<252 then
                        err=math.max(err,math.abs(r(a)-(ay-32)),math.abs(r(a+3)-gx))
                        if (r(a+1)%2~=1 and r(a+1)~=0x7C) or r(a+2)~=2 then err=999 end
                    end
                end
                for idx=#cols+1,#oamSlots do if r(oamSlots[idx])<0xEF then err=999 end end
                if err>maxErr then maxErr=err;f:write(string.format('note new max error=%d age=%d ax=%d ay=%d g0=%d,%d\n',err,age,ax,ay,r(OAM+3),r(OAM))) end
                tracked=tracked+1
                if not startScroll then startScroll=r(0x72C) end
                if r(0x72C)~=startScroll then scrolled=true end
            end
            if age==40 then screenshot('shout-follow')end
        end
        if seen and word==0 and not expired then expired=true end
        if expired and word==0 and vis>0 then hiddenAfter=false end
        if expired and word~=0 and not rotatedWord then rotatedWord=word end
        if age==170 then
            check(seen and firstAt<=4,'word appears within four frames of the panic (frame '..tostring(firstAt)..')')
            check(tracked>=40 and maxErr<=2,'word tracks the fleeing villager in the same frame ('..tracked..' frames, max error '..maxErr..')')
            check(scrolled,'tracking holds while the screen scrolls')
            check(expired and hiddenAfter,'word hides itself when its timer expires')
            check(rotatedWord~=nil and rotatedWord~=firstWord,'word rotates on next shout ('..tostring(firstWord)..'->'..tostring(rotatedWord)..')')
            check(r(0x736)==11,'town remains playable')
            pending=true
        end
    elseif phase==2 then
        -- Offscreen: the villager leaves the screen with the word live.
        if age==2 then w(WORD,1);w(SLOT,slot);w(TIMER,100);w(0xAF+slot,0x80);w(0x71+slot,0x10) end
        if age==6 then check(vis>0,'forced word draws while villager is on screen') end
        if age==7 then w(0x4E+slot,(r(0x72C)+20)%256);w(0x3C+slot,(r(0x72A)+1)%256) end
        if age==9 then
            check(vis==0,'word hides while the villager is offscreen')
            pending=true
        end
    elseif phase==3 then
        if not placedAt and playerX()>=doorX-100 then
            placedAt=age
            local vx=doorX-24
            w(0xB6+slot,1);w(0xBC+slot,255);w(0xA1+slot,0x1B);w(0x2A+slot,176)
            w(0x4E+slot,vx%256);w(0x3C+slot,math.floor(vx/256));w(0x60+slot,1)
            w(0xAF+slot,0x80);w(0x71+slot,0x10);w(0x5C3+slot,0)
            w(WORD,1);w(SLOT,slot);w(TIMER,100);w(0x6461,0xB4)
        end
        if placedAt and age>placedAt+1 then
            if doorNt then
                local tile=emu.read(doorNt+0x20,emu.memType.nesPpuMemory)
                if tile==0xFF then doorOpened=true end
                if doorOpened and tile==0x40 then doorClosed=true end
            end
            if vis>0 and not despawned then
                doorSeen=true
                if age==placedAt+6 then screenshot('shout-follow-door') end
            end
            if r(0xB6+slot)==0 and not despawned then
                despawned=true;despawnHidden=(vis==0) and word==0
            end
        end
        if (placedAt and age==placedAt+120) or age==700 then
            check(doorSeen,'word is drawn above the villager running for the door')
            check(despawned and despawnHidden,'word vanishes the same frame the villager enters a doorway')
            check(doorOpened and doorClosed,'house door opens and closes in PPU nametable')
            pending=true
        end
    elseif phase==4 then
        -- A real fireball burns the villager while its word is live.
        if age==2 then w(WORD,3);w(SLOT,slot);w(TIMER,100);w(0x6461,0xB4) end
        if r(0xAF+slot)>=0xC0 and not burned then burned=true;burnHidden=(vis==0) and word==0 end
        if age==90 then
            check(burned and burnHidden,'word vanishes the same frame the villager ignites')
            pending=true
        end
    elseif phase==5 then
        if age==2 then w(WORD,1);w(SLOT,slot);w(TIMER,100);w(0x6461,0xB4) end
        if age==6 then check(vis>0,'word visible before the scene change');w(0x561,2) end
        -- Only the room identity changes here, so judge the very next frame.
        if age==7 then sceneHidden=(r(WORD)==0 and vis==0) end
        if age==8 then
            check(sceneHidden,'scene change drops the word without writing new-scene OAM')
            pending=true
        end
    elseif phase==6 then
        -- Up-talk mid-shout: the native frame skips its OAM clear while talking.
        if age==2 then w(WORD,2);w(SLOT,slot);w(TIMER,100);w(0x6461,0xB4) end
        if r(0x74C)~=0 then talkStarted=true;talkFrames=talkFrames+1;if vis>0 then talkHidden=false end end
        if r(0x74C)~=0 and age%8==0 and glyphTilesOnScreen() then glyphBg=true end
        if age==60 then screenshot('shout-follow-talk') end
        if age==200 then
            check(talkStarted and talkFrames>20,'Up still opens the panic conversation')
            check(talkHidden,'word stays hidden for the whole conversation')
            check(r(WORD)==0,'conversation cancels the word')
            pending=true
        end
    elseif phase==7 then
        if age==2 then w(WORD,4);w(SLOT,slot);w(TIMER,100);w(0x6461,0xB4) end
        if age>12 and age<60 then
            if r(0x736)~=11 or r(0x74C)~=0 or r(0x524)~=0 then menuOpened=true end
            if age>16 then menuFrames=menuFrames+1;if vis>0 then menuHidden=false end end
        end
        if age>12 and age<60 and age%8==0 and glyphTilesOnScreen() then glyphBg=true end if age>12 and age<60 and age%8==0 then menuFireOnScreen() end
        if age==30 then screenshot('shout-follow-menu') end
        if age==130 then
            check(menuOpened,'Start opens the pause menu mid-shout')
            check(menuHidden,'word is not drawn while the pause menu is open')
            check(not glyphBg,'dialogue and menu backgrounds never use the replaced glyph pairs')
            check(menuFireSeen[0x35]==nil and menuFireSeen[0xA7]==nil and menuFireSeen[0xC2]==nil,'pause menu never draws fire-char tiles')
            check(r(0x736)==11,'town playable after the menu')
            pending=true
        end
    elseif phase==8 or phase==9 then
        -- Edges: villager 6 px past the left edge, or at screen X 236.
        local sx=phase==8 and -6 or 236
        if age==2 then
            local wx=r(0x72C)+256*r(0x72A)+sx
            w(0x4E+slot,wx%256);w(0x3C+slot,math.floor(wx/256)%256)
            w(0xAF+slot,0x80);w(0x71+slot,0)
            w(WORD,1);w(SLOT,slot);w(TIMER,100);w(0x6461,0xB4)
        end
        if age==4 then
            local ok=true
            local left=sx+8-4*lengths[1]
            for idx,col in ipairs(words[1]) do
                local a=oamSlots[idx]
                local gx=left+8*col
                if gx<0 or gx>255 then
                    if r(a)<0xEF then ok=false end
                elseif r(a)~=r(0x2A+slot)-32 or r(a+3)~=gx then ok=false end
            end
            check(ok and r(WORD)==1,(phase==8 and 'left' or 'right')..' edge clips glyphs one by one without wraparound')
            pending=true
        end
    end
end,emu.eventType.endFrame)
