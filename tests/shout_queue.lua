-- Native PPU command append bounds, deferral and erasure, with no live NMI.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local cases={
    {name='empty queue',count=0,wrote=true},
    {name='last safe queue size',count=9,wrote=true},
    {name='busy queue',count=10,wrote=false},
    {name='other native queue',count=0,queue=1,wrote=false},
    {name='existing dialogue',count=0,dialog=2,wrote=false},
    {name='erase subtitle',count=0,request=255,wrote=true},
    {name='outside town',count=0,world=0,wrote=false},
    {name='changed room',count=0,room=2,wrote=false}
}
local frame,index,errors=0,0,0
local ready,running=false,false
local f=assert(io.open(OUTPUT_DIR..'/shout-queue.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
local function advance()
    index=index+1;local c=cases[index]
    if not c then f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close();running=false;stopScenario(errors==0 and 0 or 1);return end
    w(0x5EA,1);w(0x6460,0);w(0x6461,0);w(0x6462,c.request or 1)
    w(0x6463,c.world or 1);w(0x6464,1);w(0x6466,0)
    w(0x707,c.world or 1);w(0x561,c.room or 1);w(0x736,11)
    w(0x74C,c.dialog or 0);w(0xDE,0);w(0x726,0);w(0x725,c.queue or 0);w(0xF7,0)
    for a=0x302,0x361 do w(a,0xCC)end
    w(0x301,c.count);w(0x362,0x77)
    local entry=LABELS.BarbaShouts
    local program={0x20,0xC5,0xFF,0x20,entry%256,math.floor(entry/256),0x4C,6,6}
    for i,v in ipairs(program)do w(0x5FF+i,v)end
    emu.setState({['cpu.pc']=0x600,['cpu.sp']=0xFD,['cpu.x']=3,['cpu.y']=9,['cpu.ps']=0x24})
end
emu.addMemoryCallback(function()
    if not running then return end
    local c=cases[index]
    check(r(0x301)==c.count+(c.wrote and 23 or 0),c.name..': correct queue length')
    check(r(0x362)==0x77 and r(0x74C)==(c.dialog or 0) and r(0xDE)==0,c.name..': protects adjacent queue and control state')
    local prefix=true
    for a=0x302,0x301+c.count do if r(a)~=0xCC then prefix=false end end
    check(prefix,c.name..': preserves queued native commands')
    if c.wrote then
        local a=0x302+c.count
        check(r(a)==0x20 and r(a+1)==6 and r(a+2)==20 and r(a+23)==255,c.name..': correct top-row packet and terminator')
        if c.request==255 then
            local blank=true;for b=a+3,a+22 do if r(b)~=0xF4 then blank=false end end
            check(blank,'erase fills only the subtitle span with native blank glyphs')
        end
    end
    check(emu.getState()['cpu.x']==3 and emu.getState()['cpu.y']==9,c.name..': preserves caller indexes')
    advance()
end,emu.callbackType.exec,0x606)
emu.addEventCallback(function()frame=frame+1;if frame==120 then ready=true end end,emu.eventType.endFrame)
emu.addMemoryCallback(function()
    if ready then ready=false;running=true;w(0x2000,r(0xFF)&0x7F);advance()end
end,emu.callbackType.exec,0xC07B)
