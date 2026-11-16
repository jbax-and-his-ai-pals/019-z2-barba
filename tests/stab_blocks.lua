-- Downstab and upstab break glove-gated blocks in palaces.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/stab_blocks.txt','w'))
local errors,checks,frame,current=0,0,0,0
local running,ready=false,false
local steps={}
local function check(ok,msg)
    checks=checks+1
    report:write((ok and 'PASS ' or 'FAIL ')..msg..'\n')
    report:flush()
    if not ok then errors=errors+1 end
end
local function add(entry,setup,verify)
    steps[#steps+1]={entry=entry,setup=setup,verify=verify}
end
local function base(dir,tech,air,glove)
    for a=0x6000,0x633F do w(a,0x42)end
    for a=0x6400,0x642F do w(a,0)end
    for a=0x41A,0x43C do w(a,0)end
    for _,a in ipairs({0x8D,0x8E,0x72A,0x72C,0xED,0xEC})do w(a,0)end
    w(0x769,4);w(0x707,4);w(0x736,11);w(0xB5,1);w(0x777,4)
    w(0x786,glove);w(0x796,tech);w(0x479,air)
    w(0x9F,dir);w(0x5F,dir);w(0xCC,0x50);w(0x4D,0x50);w(0x3B,0);w(0x29,0x90)
end

-- Downstab ($80=9) breaks block below feet ($6095 at X=0x5F, Y=0xB4) only with glove.
for _,glove in ipairs({0,1})do
    add(LABELS.BarbaBlocks,function()
        base(1,0x10,2,glove)
        w(0x80,9);w(0x57D,0x04);w(0x6095,0x4C)
    end,function()
        check(r(0x6095)==(glove==1 and 0x42 or 0x4C),'downstab block glove='..glove)
        check(r(0x480)==0xAC and r(0x47E)==0x5B,'downstab preserves foot hitbox after block check glove='..glove)
        check(r(0x57D)==(glove==1 and 0 or 0x04),'downstab y-vel after block check glove='..glove)
        if glove==1 then check(r(0xED)==4,'downstab plays block-break sfx')end
    end)
end

-- Upstab ($80=8) breaks overhead block when rising with tech and glove (both facings).
for _,c in ipairs({
    {dir=1,tech=4,vel=0xFC,glove=1,addr=0x6086,expect=true,name='upstab right glove=1'},
    {dir=2,tech=4,vel=0xFC,glove=1,addr=0x6085,expect=true,name='upstab left glove=1'},
    {dir=1,tech=4,vel=0xFC,glove=0,addr=0x6086,expect=false,name='upstab right glove=0'},
    {dir=1,tech=0,vel=0xFC,glove=1,addr=0x6086,expect=false,name='upstab right no-tech'},
    {dir=1,tech=4,vel=0x02,glove=1,addr=0x6086,expect=false,name='upstab right falling'},
})do
    add(LABELS.BarbaBlocks,function()
        base(c.dir,c.tech,2,c.glove)
        w(0x80,8);w(0x57D,c.vel);w(0x29,0xB0);w(c.addr,0x4C)
    end,function()
        check(r(c.addr)==(c.expect and 0x42 or 0x4C),c.name)
        if c.expect then check(r(0x57D)==0 and r(0xED)==4,c.name..' stops rise + sfx')end
    end)
end

local function nextStep()
    current=current+1;local t=steps[current]
    if not t then
        running=false
        report:write('CHECKS '..checks..' FAILURES '..errors..'\nRESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
        report:close()
        stopScenario(errors==0 and 0 or 1)
        return
    end
    if t.setup then t.setup()end
    local e=t.entry
    local p={0x20,0xC5,0xFF,0xA2,0,0x20,e%256,e//256,0x4C,0x08,0x06}
    for i,v in ipairs(p)do w(0x5FF+i,v)end
    emu.setState({['cpu.pc']=0x600,['cpu.sp']=0xFD,['cpu.ps']=0x24})
end

emu.addMemoryCallback(function()
    if running then
        local t=steps[current]
        if t.verify then t.verify()end
        nextStep()
    end
end,emu.callbackType.exec,0x608)

emu.addEventCallback(function()
    frame=frame+1
    if frame==120 then ready=true end
end,emu.eventType.endFrame)

emu.addMemoryCallback(function()
    if ready and not running then
        ready=false;running=true;w(0x2000,0);nextStep()
    end
end,emu.callbackType.exec,0xC07B)
