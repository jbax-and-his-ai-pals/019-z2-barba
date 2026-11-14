-- Real game-loop, controller-driven five-shot volley regression.
-- Run sequentially: python tools/emulator_test.py tests/projectile_only.lua
-- Each case restores a fresh castle snapshot; no enemies/old shots survive.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local frame,age,index,errors=0,0,0,0
local base,pending=nil,false
local cases={}
local shots,tracked={},{}
local poseSeen,meleeHidden,attachedHidden=false,true,true
local movingX,movingY,classStable=false,false,true
local report=assert(io.open(OUTPUT_DIR..'/projectile-only.txt','w'))
for _,fire in ipairs({false,true})do
    for _,full in ipairs({false,true})do
        for _,dir in ipairs({1,2})do
            for _,duck in ipairs({false,true})do
                cases[#cases+1]={fire=fire,full=full,dir=dir,duck=duck}
            end
        end
    end
end
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n');report:flush()
    if not ok then errors=errors+1 end
end
local function label()
    local c=cases[index]
    return string.format('case %d Fire=%s HP=%s facing=%d crouch=%s',
        index,tostring(c.fire),c.full and 'full' or 'damaged',c.dir,tostring(c.duck))
end
local function finishCase()
    local name=label();local aligned,classified=0,0
    for _,shot in ipairs(shots)do
        if shot.aligned then aligned=aligned+1 end
        if shot.classified then classified=classified+1 end
    end
    check(#shots==5,name..': held B emits exactly five shots, count='..#shots)
    check(aligned==5,name..': all five shots originate at current mouth, count='..aligned)
    check(classified==5 and classStable,name..': Fire class 0 or ordinary class D2 retained')
    check(movingX and movingY,name..': shots move forward and downward')
    check(poseSeen,name..': standing/crouching attack pose exercised')
    check(meleeHidden,name..': native horizontal melee origin stays hidden')
    check(attachedHidden,name..': no attached flame sprites in OAM 220/224')
    check(r(0x736)==11 and r(0xB5)==1,name..': remains alive in side-view castle')
end
local function nextCase()
    if index>0 then finishCase()end
    index=index+1
    if not cases[index]then
        report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
        report:close();stopScenario(errors==0 and 0 or 1);return
    end
    assert(emu.loadSavestate(base),'fresh castle snapshot restores')
    local c=cases[index]
    age=0;shots={};tracked={}
    poseSeen=false;meleeHidden=true;attachedHidden=true
    movingX=false;movingY=false;classStable=true
    w(0x5F,c.dir);w(0x9F,c.dir);w(0x70,0)
    w(0x76F,c.fire and 0x10 or 0);w(0x784,4);w(0x774,c.full and 127 or 100)
    w(0x777,index%2==0 and 4 or 1)
    for _,address in ipairs({0x5F1,0x5F7,0x5F8,0x5FC,0x5FD,0x5FE})do w(address,0)end
    for address=0xB6,0xBB do w(address,0)end
    report:write('BEGIN '..label()..' Attack='..r(0x777)..'\n');report:flush()
end
-- Successful-placement hook counts emissions even when a slot is recycled
-- between end-frame observations; position/class are sampled before movement.
assert(LABELS and LABELS.BarbaVolleyPlaced,'build must export BarbaVolleyPlaced')
emu.addMemoryCallback(function()
    if index==0 or not cases[index]then return end
    local s=emu.getState()
    if s['mapper.prgReg']~=0 then return end
    local slot=s['cpu.x']
    if slot>1 then return end
    local c=cases[index]
    local screenX=r(0x5A+slot)+256*r(0x48+slot)-r(0x72C)-256*r(0x72A)
    local y=r(0x36+slot);local class=r(0x5CA+slot)
    local shot={age=age,slot=slot,
        aligned=screenX==r(0x5F2) and y==r(0x5F3),
        classified=class==(c.fire and 0 or 0xD2)}
    shots[#shots+1]=shot;tracked[slot]=nil
    report:write(string.format('SHOT %d age=%d slot=%d xy=%d,%d mouth=%d,%d class=%02X\n',
        #shots,age,slot,screenX,y,r(0x5F2),r(0x5F3),class))
end,emu.callbackType.exec,LABELS.BarbaVolleyPlaced)
-- Native updater entry samples live trajectories and collision classes.
emu.addMemoryCallback(function()
    if index==0 or not cases[index]then return end
    local s=emu.getState()
    if s['mapper.prgReg']~=0 then return end
    local slot=s['cpu.x'];if slot>1 then return end
    local active=r(0x8D+slot)>0 and r(0x8D+slot)<0x80
    if not active then tracked[slot]=nil;return end
    local c=cases[index]
    local x=r(0x5A+slot)+256*r(0x48+slot)
    local y=r(0x36+slot);local class=r(0x5CA+slot)
    local old=tracked[slot]
    if old then
        local dx=x-old.x;local dy=y-old.y
        if (c.dir==1 and dx>0 and dx<16)or(c.dir==2 and dx<0 and dx> -16)then movingX=true end
        if dy>0 and dy<=3 then movingY=true end
    end
    if c.fire and class~=0 then classStable=false end
    if not c.fire and class==0 then classStable=false end
    tracked[slot]={x=x,y=y}
end,emu.callbackType.exec,0x9888)
emu.addMemoryCallback(function()
    if not pending then return end
    pending=false
    if not base then
        check(r(0x736)==11,'fresh new game reaches castle')
        base=emu.createSavestate()
    end
    nextCase()
end,emu.callbackType.exec,0xC07B)
emu.addEventCallback(function()
    local buttons=newGameInput(frame)
    if index>0 and cases[index]then
        buttons={start=false,select=false,a=false,b=age>=12 and age<175,
            up=false,down=cases[index].duck,left=false,right=false}
    end
    emu.setInput(buttons,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if not base then if frame==1000 then pending=true end;return end
    age=age+1
    local c=cases[index];if not c then return end
    if r(0x80)==(c.duck and 7 or 5)then
        poseSeen=true
        if r(0x480)~=0xF8 then meleeHidden=false end
    end
    if age>=3 and(r(0x220)~=0xF8 or r(0x224)~=0xF8)then attachedHidden=false end
    if age==24 and(index==1 or index==9)then screenshot('projectile-only-case-'..index)end
    if age==180 then pending=true end
end,emu.eventType.endFrame)
