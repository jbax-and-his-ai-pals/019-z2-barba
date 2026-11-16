-- Single-area non-town and indoor NPCs stay put on approach, but burn on fireball hit.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local frame,age,phase,errors=0,0,0,0
local base,slot,pending=nil,nil,false
local burned,ashes=false,false
local f=assert(io.open(OUTPUT_DIR..'/town_nontown_burn.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
local cases={
    {world=1,room=0x30,kind=0x11,name='single-area room $30 type $11'},
    {world=1,room=0x2C,kind=0x0D,name='Knight/River Man room $2C type $0D'},
    {world=1,room=0x24,kind=0x0F,name='Wise Man room $24 type $0F'},
    {world=1,room=0x1C,kind=0x0E,name='indoor room $1C type $0E'},
    {world=1,room=0x1C,kind=0x10,name='auto-talker room $1C type $10'},
    {world=1,room=0x1E,kind=0x21,burn=false,name='invisible Mirror/Fountain trigger type $21'},
}
local function setup()
    emu.loadSavestate(base);age=0;burned=false;ashes=false
    local c=cases[phase]
    w(0x707,c.world);w(0x561,c.room)
    w(0x4D,80);w(0x3B,0);w(0x29,176);w(0x57D,0);w(0x479,0)
    w(0x8D,0);w(0x8E,0);w(0x5F8,0);w(0x5FE,0);w(0x400,0);w(0x76F,0)
    for x=0,5 do if x~=slot then w(0xB6+x,0)end end
    w(0xB6+slot,1);w(0xA1+slot,c.kind);w(0xBC+slot,c.burn~=false and 1 or 255)
    if c.burn~=false then local d6=r(0xD6)+r(0xD7)*256;w(d6+1,r(d6+1)|0x80)end
    w(0x4E+slot,128);w(0x3C+slot,0);w(0x2A+slot,176);w(0x60+slot,0)
    w(0xAF+slot,0);w(0x71+slot,0);w(0x5C3+slot,0)
end
emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then
        b={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
        b.b=age>=8 and age<11
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addMemoryCallback(function()
    if not pending then return end
    pending=false
    if not base then base=emu.createSavestate()end
    phase=phase+1
    if phase>#cases then
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
    local c=cases[phase]
    if not c then return end
    if age==10 then
        check(r(0xAF+slot)==0,c.name..' does not flee on approach')
    end
    if r(0xAF+slot)>=0xC0 then burned=true end
    if r(0xAF+slot)>=0xA0 and r(0xAF+slot)<0xC0 then ashes=true end
    if age==190 then
        if c.burn==false then
            check(not burned,c.name..' does not ignite')
            check(not ashes,c.name..' does not turn to ash')
            check(r(0xAF+slot)==0 and r(0xB6+slot)==1,c.name..' stays active')
        else
            local d6=r(0xD6)+r(0xD7)*256
            check(burned,c.name..' ignites on fireball hit')
            check(ashes,c.name..' turns to ash')
            check(r(0xB6+slot)==0,c.name..' ash expires cleanly')
            check(r(d6+1)<0x80,c.name..' room-table spawn bit cleared on ash expiry')
        end
        pending=true
    end
end,emu.eventType.endFrame)
