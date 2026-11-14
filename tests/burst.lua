-- Deterministic CPU regression for the bounded Fire scheduler. Native Fire
-- allocation and shared muzzle geometry execute unchanged. Projectile motion
-- is parked at the update entry so slot lifetime cannot hide repeated shots.
-- Run with: python tools/emulator_test.py tests/burst.lua
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/burst.txt','w'))
local errors,allocations,slotOneUpdates=0,0,0
local steps,current={},0
local running,ready=false,false
local frame=0
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n');report:flush()
    if not ok then errors=errors+1 end
end
local function step(name,entry,setup,verify)
    steps[#steps+1]={name=name,entry=entry,setup=setup,verify=verify}
end
local function base(level)
    allocations=0;slotOneUpdates=0
    w(0x769,0);w(0x736,11);w(0xB5,1);w(0x76F,0x10)
    w(0x74C,0);w(0x524,0);w(0x726,0);w(0x13,0);w(0xDE,0)
    w(0x777,level);w(0x784,4);w(0x774,80) -- damaged health must still emit Fire
    w(0x400,2);w(0x495,1);w(0x50A,5);w(0x17,0);w(0x80,6)
    w(0x9F,1);w(0xCC,100);w(0x29,100)
    w(0x4D,100);w(0x3B,0);w(0x72C,0);w(0x72A,0)
    w(0x8D,0);w(0x8E,0);w(0x5F7,0);w(0x5F8,0)
    w(0x5FC,0);w(0x5FD,0);w(0x5FE,0);w(0x9D,0x38);w(0x9E,0x40)
end
local function fire(name,setup,verify)
    step(name,LABELS.BarbaFireSpell,setup,verify)
end
local function update(name,setup,verify)
    step(name,LABELS.BarbaProjectiles,setup,verify)
end
for _,level in ipairs({1,4})do
    local label='Attack '..level
    fire(label..' initial',function()base(level)end,function()
        check(allocations==1 and r(0x5F7)==8 and r(0x5F8)==1,
            label..': initial Fire arms exactly one eight-frame follow-up')
        local slot=level<4 and 0 or 1
        check(r(0x8D+slot)==1 and r(0x5CA+slot)==0,
            label..': native allocator retains Fire vulnerability class')
    end)
    for tick=1,8 do
        update(label..' delay '..tick,nil,function()
            check(allocations==(tick==8 and 2 or 1),label..': allocation count at tick '..tick)
            if tick==8 then
                check(r(0x8D)==1 and r(0x8E)==1 and r(0x5F8)==2,
                    label..': exactly two live slots after follow-up')
                if level==1 then check(slotOneUpdates==8,'Attack 1: extra native slot updated every tick')end
                if level==4 then check(slotOneUpdates==0,'Attack 4: no duplicate slot-1 update')end
            end
        end)
    end
    -- Keep the native emission gate eligible and B-like attack state held,
    -- while freeing slots: a broken queue cannot pass merely by filling up.
    for tick=1,24 do
        fire(label..' held '..tick,function()w(0x8D,0);w(0x8E,0)end,nil)
        update(label..' held update '..tick,nil,function()
            if allocations~=2 then
                report:write(string.format('TRACE %s held=%d allocations=%d state=%d delay=%d mode=%d attack=%d gate=%d HP=%d max=%d slots=%d,%d flags=%d,%d\n',
                    label,tick,allocations,r(0x5F8),r(0x5F7),r(0x5FE),r(0x400),r(0x50A),r(0x774),r(0x784),r(0x8D),r(0x8E),r(0x5FC),r(0x5FD)))
            end
            if tick==24 then check(allocations==2,label..': held attack cannot restart burst after slots free')end
        end)
    end
    update(label..' release',function()w(0x400,0)end,function()
        check(r(0x5F8)==0 and r(0x5F7)==0,label..': attack end clears latch')
    end)
end

fire('full pool setup',function()base(1)end,nil)
update('full pool follow-up',function()
    w(0x8D,1);w(0x8E,1);w(0x5F7,1)
end,function()
    check(allocations==1 and r(0x5F8)==2,'full two-slot pool drops follow-up without allocation')
end)
for tick=1,12 do
    update('full pool no retry '..tick,function()w(0x8D,0);w(0x8E,0)end,function()
        if tick==12 then check(allocations==1,'dropped follow-up never retries after a slot becomes free')end
    end)
end

local cancelCases={
    {name='scene fade',address=0x726,value=1},
    {name='new scene mode',address=0x736,value=10,normal=11},
    {name='spell menu',address=0x524,value=1},
    {name='level-up dialog',address=0x74C,value=1},
    {name='death',address=0xB5,value=2,normal=1},
    {name='wyrmling form',address=0x13,value=1},
    {name='Fire disabled',address=0x76F,value=0,normal=0x10},
    {name='scripted freeze',address=0xDE,value=1},
}
for _,test in ipairs(cancelCases)do
    fire(test.name..' setup',function()base(4)end,nil)
    update(test.name..' cancellation',function()
        w(0x5F7,1);w(test.address,test.value)
    end,function()
        check(allocations==1 and r(0x5F8)==0 and r(0x5F7)==0,
            test.name..': pending shot cancelled before allocation')
    end)
    -- Resume without a new attack. No queued shot may leak into the next room
    -- or emerge when the menu/form/death state clears.
    for tick=1,10 do
        update(test.name..' resume '..tick,function()
            w(test.address,test.normal or 0);w(0x400,0)
        end,function()
            if tick==10 then check(allocations==1,test.name..': no delayed shot after returning')end
        end)
    end
end

-- Full-life volleys start even without spell dispatch. Fire empowers their
-- damage class; ordinary full-life fireballs keep the original beam class.
for _,level in ipairs({1,4})do
    for _,direction in ipairs({1,2})do
        for _,spell in ipairs({0,0x10})do
            local name=string.format('full-life Attack %d facing %d Fire=%d',level,direction,spell)
            local initial=level<4 and 0 or 1
            update(name..' initial',function()
                base(level);w(0x774,127);w(0x76F,spell);w(0x9F,direction)
                -- Cross a world-page boundary to exercise screen-to-world carry.
                w(0x72C,240);w(0x72A,1)
            end,function()
                check(allocations==1 and r(0x5FE)==1 and r(0x5F8)==1,
                    name..': projectile hook starts full-life mode without spell dispatch')
                check(r(0x5FC+initial)==1 and r(0x5CA+initial)==(spell==0 and 0xD2 or 0),
                    name..': Fire spell controls diagonal fireball vulnerability class')
                check(r(0x7D+initial)==(direction==1 and 0x20 or 0xE0),
                    name..': horizontal velocity follows facing')
                check(r(0x36+initial)==r(0x5F3)+2,
                    name..': first update descends two pixels')
                local world=r(0x5A+initial)+256*r(0x48+initial)
                check(world==r(0x5F2)+240+256,name..': shared muzzle preserves world-page carry')
                local oam=r(0x9D+initial)
                check(r(0x201+oam)==0x84 and r(0x202+oam)%4==1,
                    name..': volley renders as orange dragon fire')
            end)
            for tick=1,7 do
                update(name..' continuation '..tick,nil,function()
                    if tick==7 then
                        check(allocations==2 and r(0x5F8)==2 and r(0x5FC)==1 and r(0x5FD)==1,
                            name..': exactly two flagged fireballs after eight updates')
                        check(r(0x36+initial)==r(0x5F3)+16 and r(0x36+1-initial)==r(0x5F3)+2,
                            name..': both fireballs descend independently')
                    end
                end)
            end
            update(name..' bottom boundary',function()
                w(0x36,0xDF);w(0x37,0xDF)
            end,function()
                check(r(0x8D)==0 and r(0x8E)==0 and r(0x5FC)==0 and r(0x5FD)==0,
                    name..': fireballs and flags clear before wrapping below screen')
            end)
        end
    end
end
update('full-life damage cancellation setup',function()
    base(4);w(0x774,127);w(0x76F,0)
end,nil)
update('full-life damage cancellation',function()w(0x774,126)end,function()
    check(allocations==1 and r(0x5F8)==0 and r(0x5F7)==0,
        'taking damage cancels pending full-life follow-up without Fire')
end)

local function nextStep()
    current=current+1
    local test=steps[current]
    if not test then
        running=false
        report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');report:close()
        stopScenario(errors==0 and 0 or 1);return
    end
    if test.setup then test.setup()end
    w(0x769,0)
    local entry=test.entry
    local program={0x20,0xC9,0xFF,0x20,entry%256,math.floor(entry/256),0x4C,0x06,0x06,0x60}
    for i,v in ipairs(program)do w(0x5FF+i,v)end
    emu.setState({['cpu.pc']=0x600,['cpu.sp']=0xFD,['cpu.ps']=0x24})
end
emu.addMemoryCallback(function()
    if running then
        allocations=allocations+1
        report:write(string.format('ALLOC %s count=%d state=%d delay=%d mode=%d slots=%d,%d X=%d bank=%d\n',
            steps[current].name,allocations,r(0x5F8),r(0x5F7),r(0x5FE),r(0x8D),r(0x8E),
            emu.getState()['cpu.x'],emu.getState()['mapper.prgReg']))
    end
end,emu.callbackType.exec,0x981B)
-- Replace updater execution with RTS without modifying ROM. The scheduler
-- still selects its native update paths, which are counted separately.
emu.addMemoryCallback(function()
    if running then emu.setState({['cpu.pc']=0x609})end
end,emu.callbackType.exec,0x9878)
emu.addMemoryCallback(function()
    if running then slotOneUpdates=slotOneUpdates+1;emu.setState({['cpu.pc']=0x609})end
end,emu.callbackType.exec,0x9888)
emu.addMemoryCallback(function()
    if running then
        local test=steps[current]
        if test.verify then test.verify()end
        nextStep()
    end
end,emu.callbackType.exec,0x606)
dofile(TEST_DIR..'/newgame.lua')
emu.addEventCallback(function()frame=frame+1;if frame==120 then ready=true end end,emu.eventType.endFrame)
emu.addMemoryCallback(function()
    if ready and not running then ready=false;running=true;nextStep()end
end,emu.callbackType.exec,0xC07B)
