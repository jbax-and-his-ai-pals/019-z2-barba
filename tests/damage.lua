-- Controlled native Bot fixtures; controller attacks and original damage code.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local frame,age,index,errors=0,0,0,0
local base,pending,hit=nil,false,false
local cases={{fire=false,dir=1},{fire=false,dir=2},{fire=true,dir=1},{fire=true,dir=2}}
local f=assert(io.open(OUTPUT_DIR..'/damage.txt','w'))
emu.addMemoryCallback(function()
    if not pending then return end
    pending=false
    if not base then base=emu.createSavestate()end
    if index>0 then
        f:write((hit and 'PASS ' or 'FAIL ')..'projectile damages Bot Fire='..tostring(cases[index].fire)..' facing='..cases[index].dir..'\n')
        if not hit then errors=errors+1 end
    end
    index=index+1
    if not cases[index]then f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close();stopScenario(errors==0 and 0 or 1);return end
    emu.loadSavestate(base);age=0;hit=false
    local c=cases[index]
    w(0x5F,c.dir);w(0x9F,c.dir);w(0x70,0);w(0x774,100);w(0x784,4);w(0x777,1)
    w(0x76F,c.fire and 16 or 0);w(0x5F8,0);w(0x400,0);w(0x8D,0);w(0x8E,0)
    for a=0xB6,0xBB do w(a,0)end
    w(0xB6,1);w(0xA1,4);w(0xC2,8);w(0xA8,0);w(0x1A,1)
    w(0x444,0);w(0x40E,0);w(0x518,0)
end,emu.callbackType.exec,0xC07B)
emu.addEventCallback(function()
    local b=newGameInput(frame)
    if base then b={start=false,select=false,a=false,b=age>=20 and age<23,up=false,down=false,left=false,right=false}end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if not base then if frame==1000 then pending=true end;return end
    age=age+1
    if not cases[index]then return end
    local x=r(0x4D)+256*r(0x3B)+(cases[index].dir==1 and 44 or -28)
    w(0x4E,x%256);w(0x3C,math.floor(x/256)%256);w(0x2A,r(0x29)+4);w(0x71,0);w(0x57E,0)
    if r(0xC2)<8 or r(0x40E)>0 then hit=true end
    if age==120 then pending=true end
end,emu.eventType.endFrame)
