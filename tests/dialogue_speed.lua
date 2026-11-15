-- Fast panic typing must not change quest/service text timing or registers.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local cases={
    {kind='letter',room=1,origin=255,npc=0x19,delay=1},
    -- Scripted outdoor actors now share generated actors' panic timing.
    {kind='letter',room=1,origin=5,npc=0x19,delay=1},
    {kind='letter',room=0x1C,origin=255,npc=0x19,delay=5},
    {kind='letter',room=1,origin=255,npc=0x0F,delay=5},
    {kind='line',room=1,origin=255,npc=0x19,delay=1},
    {kind='line',room=1,origin=5,npc=0x19,delay=1},
    {kind='line',room=0x1C,origin=255,npc=0x19,delay=11},
    {kind='line',room=1,origin=255,npc=0x0F,delay=11}
}
local frame,current,errors=0,0,0
local ready,running=false,false
local f=assert(io.open(OUTPUT_DIR..'/dialogue-speed.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
local function advance()
    current=current+1
    local c=cases[current]
    if not c then f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close();running=false;stopScenario(errors==0 and 0 or 1);return end
    w(0x769,3);w(0x707,1);w(0x561,c.room);w(0x48B,0)
    w(0xB6,1);w(0xBC,c.origin);w(0xA1,c.npc)
    local entry=c.kind=='line' and LABELS.TownLineDelay or LABELS.TownLetterDelay
    local program={0x20,0xC9,0xFF,0xA9,0xA5,0xA2,3,0xA0,11,0x38,0x20,entry%256,math.floor(entry/256),0x4C,13,6}
    for i,v in ipairs(program)do w(0x5FF+i,v)end
    emu.setState({['cpu.pc']=0x600,['cpu.sp']=0xFD,['cpu.ps']=0x24})
end
emu.addMemoryCallback(function()
    if not running then return end
    local c=cases[current];local s=emu.getState()
    check(r(0x566)==c.delay,'case '..current..' selects correct panic/native delay')
    check(s['cpu.x']==3 and s['cpu.y']==11 and (s['cpu.ps']&1)==1,'case '..current..' preserves caller indexes and carry')
    check(s['cpu.a']==(c.kind=='line' and 0xA5 or c.delay),'case '..current..' retains native accumulator behavior')
    advance()
end,emu.callbackType.exec,0x60D)
emu.addEventCallback(function()frame=frame+1;if frame==120 then ready=true end end,emu.eventType.endFrame)
emu.addMemoryCallback(function()
    if ready then ready=false;running=true;w(0x2000,r(0xFF)&0x7F);advance()end
end,emu.callbackType.exec,0xC07B)
