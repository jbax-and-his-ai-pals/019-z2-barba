-- Deterministic CPU checks for the finite five-shot scheduler. Native slot
-- allocation and shared geometry run unchanged. Park only native projectile
-- movement: BarbaAdvanceVolley still expires slots, so the pool is recycled.
-- Run sequentially: python tools/emulator_test.py tests/burst.lua
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/burst.txt','w'))
local errors,shots,maxSlots=0,0,0
local steps,current={},0
local running,ready=false,false
local frame=0
local expectedClass=0
local updateNumber,shotFrames=0,{}
local allocatingExtra=false
local function active(v)return v>0 and v<128 end
local function poolCount()
    local count=0
    for slot=0,1 do if active(r(0x8D+slot))then count=count+1 end end
    if r(0x5FF)==1 then
        for record=0x6400,0x6420,0x10 do if active(r(record))then count=count+1 end end
    end
    return count
end
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n');report:flush()
    if not ok then errors=errors+1 end
end
local function step(name,entry,setup,verify)
    steps[#steps+1]={name=name,entry=entry,setup=setup,verify=verify}
end
local function update(name,setup,verify)step(name,LABELS.BarbaProjectiles,setup,verify)end
local function fire(name,setup,verify)step(name,LABELS.BarbaFireSpell,setup,verify)end
local function base(level,health,spell)
    shots=0;maxSlots=0;updateNumber=0;shotFrames={};allocatingExtra=false
    expectedClass=spell==0 and 0xD2 or 0
    w(0x769,0);w(0x736,11);w(0xB5,1);w(0x76F,spell)
    w(0x74C,0);w(0x524,0);w(0x726,0);w(0x13,0);w(0xDE,0)
    w(0x777,level);w(0x784,4);w(0x774,health)
    w(0x400,2);w(0x495,1);w(0x50A,5);w(0x17,0);w(0x80,6)
    w(0xF7,0x40);w(0x9F,1);w(0xCC,100);w(0x29,100)
    w(0x4D,100);w(0x3B,0);w(0x72C,240);w(0x72A,1)
    w(0x8D,0);w(0x8E,0);w(0x5CA,0);w(0x5CB,0)
    w(0x5F1,0);w(0x5F7,0);w(0x5F8,0)
    w(0x5FC,0);w(0x5FD,0);w(0x5FE,0);w(0x9D,0x38);w(0x9E,0x40)
    w(0x5FF,0)
    for a=0x6400,0x642F do w(a,0)end
end
for _,level in ipairs({1,4})do
    for _,health in ipairs({80,127})do
        for _,spell in ipairs({0,0x10})do
            local name=string.format('Attack=%d HP=%d Fire=%d',level,health,spell)
            update(name..' initial',function()base(level,health,spell)end,function()
                check(shots==1 and r(0x5FE)==4 and r(0x5F8)==1,name..': one initial shot plus four pending')
            end)
            for tick=2,100 do
                update(name..' update '..tick,function()
                    -- The dragon remains free to move/finish its animation.
                    if tick==10 then w(0x400,0)end
                end,function()
                    if tick==9 then check(shots==2,name..': second shot eight updates after first')end
                    if tick==33 then
                        check(shots==5 and shotFrames[1]==1 and shotFrames[2]==9 and shotFrames[3]==17
                            and shotFrames[4]==25 and shotFrames[5]==33,name..': all five shots have uniform eight-update spacing')
                    end
                    if tick==80 then
                        check(shots==5 and r(0x5FE)==0 and r(0x5F8)==2,
                            name..': finite five-shot volley finishes after attack animation ends')
                    end
                    if tick==100 then
                        check(shots==5 and maxSlots==5,name..': held B cannot restart; five logical slots retain full range')
                    end
                end)
            end
        end
    end
end

-- Explicitly hold an occupied native pool forever. This isolates the global
-- deadline from both projectile lifetime and collision clearing a slot.
fire('blocked pool setup',function()base(1,80,0)end,nil)
for tick=1,120 do
    update('blocked pool '..tick,function()
        w(0x8D,1);w(0x8E,1);w(0x5FC,255);w(0x5FD,255)
        w(0x36,100);w(0x37,100);w(0x5FF,1)
        for index=0,2 do
            local a=0x6400+index*16
            w(a,1);w(a+1,100);w(a+2,100);w(a+3,0);w(a+6,1)
            w(a+7,0xD2);w(a+9,255);w(a+10,({0x3C,0x44,0x48})[index+1])
        end
    end,function()
        if tick==119 then check(shots==1 and r(0x5F8)==1,'blocked pool remains bounded pending until deadline')end
        if tick==120 then
            check(shots==1 and r(0x5F8)==2 and r(0x5FE)==0 and r(0x5F1)==0,
                'blocked pool cancels all pending shots at 120 updates')
        end
    end)
end
for tick=1,20 do
    update('expired pool cleared '..tick,function()
        w(0x8D,0);w(0x8E,0)
        for a=0x6400,0x6420,0x10 do w(a,0)end
    end,function()
        if tick==20 then check(shots==1,'deadline cancellation never retries after slots become free')end
    end)
end
update('release B and finish animation',function()w(0xF7,0);w(0x400,0)end,function()
    check(r(0x5F8)==0,'release plus idle attack re-arms scheduler')
end)
update('new B attack',function()w(0xF7,0x40);w(0x400,2);w(0x50A,5)end,function()
    check(shots==2 and r(0x5FE)==4 and r(0x5F8)==1,'fresh attack starts a new finite volley')
end)
update('mid-slash cannot re-arm when B released',function()w(0x5F8,2);w(0x5FE,0);w(0xF7,0);w(0x400,2);w(0x50A,6)end,function()
    check(r(0x5F8)==2,'mid-slash $0400==2 stays latched')
end)
update('release B during standing recovery $0400==4',function()w(0xF7,0);w(0x400,4);w(0x50A,20)end,function()
    check(r(0x5F8)==0,'release plus standing recovery $0400==4 re-arms scheduler')
end)
update('standing cancel-slash B attack',function()w(0xF7,0x40);w(0x400,2);w(0x50A,5)end,function()
    check(shots==3 and r(0x5FE)==4 and r(0x5F8)==1,'standing cancel-slash starts a new finite volley')
end)

local nativeFields={0x8D,0x36,0x5A,0x48,0x7D,0x6D,0x26,0x5CA,0x3E3,0x5FC,0x9D}
local nativeBefore={}
fire('occupied natives initial extra allocation',function()
    base(1,80,0)
    local values={1,90,0x55,2,0xE0,2,1,0xD2,0x7B,20,0x38}
    for i,a in ipairs(nativeFields)do w(a,values[i]);nativeBefore[i]=values[i]end
    w(0x8E,1)
    for a=0x238,0x23B do w(a,a%256)end
end,function()
    check(shots==1 and r(0x6400)==1 and r(0x5FE)==4,
        'an occupied native pool starts a new attack in the first extra record')
    local preserved=true
    for i,a in ipairs(nativeFields)do if r(a)~=nativeBefore[i]then preserved=false end end
    for a=0x238,0x23B do if r(a)~=a%256 then preserved=false end end
    check(preserved and r(0x8E)==1,'extra initial allocation preserves native slot zero, slot one and OAM')
end)

local cancellations={
    {name='scene fade',address=0x726,value=1},
    {name='new scene mode',address=0x736,value=10,normal=11},
    {name='spell menu',address=0x524,value=1},
    {name='level-up dialog',address=0x74C,value=1},
    {name='death',address=0xB5,value=2,normal=1},
    {name='wyrmling',address=0x13,value=1},
    {name='scripted interaction freeze',address=0xDE,value=1},
}
for _,test in ipairs(cancellations)do
    fire(test.name..' setup',function()base(4,127,0x10)end,nil)
    update(test.name..' cancellation',function()w(0x5F7,1);w(test.address,test.value)end,function()
        check(shots==1 and r(0x5FE)==0 and r(0x5F7)==0 and r(0x5F1)==0,
            test.name..': cancels pending volley before emission')
    end)
    for tick=1,12 do
        update(test.name..' resume '..tick,function()
            w(test.address,test.normal or 0);w(0x400,0)
        end,function()
            if tick==12 then check(shots==1,test.name..': held B cannot emit a stale follow-up on return')end
        end)
    end
end

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
        shots=shots+1
        shotFrames[#shotFrames+1]=updateNumber
        local count=poolCount()
        -- During extra allocation, the new shot occupies alias slot zero;
        -- its original live occupant resides temporarily in the save record.
        if allocatingExtra and active(r(0x6440))then count=count+1 end
        maxSlots=math.max(maxSlots,count)
        local slot=emu.getState()['cpu.x']
        check(r(0x5CA+slot)==expectedClass,'shot '..shots..': spell selects vulnerability class')
        check((r(0x5FC+slot)%128)==33 and r(0x7D+slot)==0x20,'shot '..shots..': finite lifetime and diagonal speed')
        local world=r(0x5A+slot)+256*r(0x48+slot)
        check(world==r(0x5F2)+496 and r(0x36+slot)==r(0x5F3),
            'shot '..shots..': shared muzzle carries across world page')
    end
end,emu.callbackType.exec,LABELS.BarbaVolleyPlaced)
emu.addMemoryCallback(function()if running then updateNumber=updateNumber+1 end end,
    emu.callbackType.exec,LABELS.BarbaProjectiles)
emu.addMemoryCallback(function()if running then allocatingExtra=false end end,
    emu.callbackType.exec,LABELS.BarbaEmitOne)
emu.addMemoryCallback(function()if running then allocatingExtra=true end end,
    emu.callbackType.exec,LABELS.BarbaExtraAllocate)
-- Native updates are parked without changing the ROM. Our real lifetime and
-- vertical movement still execute before this update-only native tail.
emu.addMemoryCallback(function()
    if running then emu.setState({['cpu.pc']=0x609})end
end,emu.callbackType.exec,0x9878)
emu.addMemoryCallback(function()
    if running then emu.setState({['cpu.pc']=0x609})end
end,emu.callbackType.exec,0x9888)
emu.addMemoryCallback(function()
    if running then
        maxSlots=math.max(maxSlots,poolCount())
        local test=steps[current]
        if test.verify then test.verify()end
        nextStep()
    end
end,emu.callbackType.exec,0x606)
dofile(TEST_DIR..'/newgame.lua')
emu.addEventCallback(function()frame=frame+1;if frame==120 then ready=true end end,emu.eventType.endFrame)
emu.addMemoryCallback(function()
    if ready and not running then
        ready=false;running=true
        -- This long CPU harness replaces the NMI before native code disables
        -- it; prevent another PPU NMI from entering midway through the steps.
        w(0x2000,r(0xFF)&0x7F)
        nextStep()
    end
end,emu.callbackType.exec,0xC07B)
