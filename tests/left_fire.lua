-- Left-facing emissions at screen/world boundaries and with occupied slots.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local frame,age,index,errors=0,0,0,0
local base,pending=nil,false
local shots={}
local cases={
    {x=32,page=0,scroll=0,occupied=false},
    {x=112,page=0,scroll=0,occupied=true},
    {x=16,page=1,scroll=128,occupied=false},
    {x=16,page=1,scroll=128,occupied=true}
}
local f=assert(io.open(OUTPUT_DIR..'/left-fire.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
emu.addMemoryCallback(function()
    if not base or not cases[index]then return end
    local slot=emu.getState()['cpu.x']
    shots[#shots+1]={age=age,world=r(0x5A+slot)+256*r(0x48+slot),dir=r(0x6D+slot)}
end,emu.callbackType.exec,LABELS.BarbaVolleyPlaced)
emu.addMemoryCallback(function()
    if not pending then return end
    pending=false
    if not base then base=emu.createSavestate()end
    if index>0 then
        local even=#shots==5
        for n=2,#shots do if shots[n].age-shots[n-1].age~=8 then even=false end end
        check(even,'left case '..index..' emits five evenly spaced shots')
        local good=#shots==5
        for _,s in ipairs(shots)do if s.dir~=2 then good=false end end
        check(good,'left case '..index..' preserves left-facing projectile direction')
        check(r(0x736)==11 and r(0xB5)==1,'left case '..index..' remains playable')
    end
    index=index+1
    if not cases[index]then f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close();stopScenario(errors==0 and 0 or 1);return end
    emu.loadSavestate(base);age=0;shots={}
    local c=cases[index]
    for a=0xB6,0xBB do w(a,0)end
    w(0x4D,c.x);w(0x3B,c.page);w(0x72C,c.scroll);w(0x72A,0)
    w(0xCC,c.x+c.page*256-c.scroll);w(0x29,176);w(0x57D,0);w(0x479,0)
    w(0x5F,2);w(0x9F,2);w(0x70,0);w(0x76F,0);w(0x5F8,0);w(0x5FF,0)
    if c.occupied then
        for slot=0,1 do
            w(0x8D+slot,1);w(0x5A+slot,180);w(0x48+slot,c.page)
            w(0x36+slot,64);w(0x7D+slot,0);w(0x6D+slot,1)
            w(0x5FC+slot,33);w(0x5CA+slot,0)
        end
    end
end,emu.callbackType.exec,0xC07B)
emu.addEventCallback(function()
    local b=newGameInput(frame)
    if base then b={start=false,select=false,a=false,b=age>=12 and age<15,up=false,down=false,left=false,right=false}end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if not base then if frame==1000 then pending=true end;return end
    age=age+1;if age==120 then pending=true end
end,emu.eventType.endFrame)
