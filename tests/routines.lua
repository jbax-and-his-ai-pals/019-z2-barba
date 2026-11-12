-- Execute the assembled 6502 routines in Mesen, with real MMC1 bank switching.
-- This is a controlled CPU harness, separate from controller-driven playtests.
local mem=emu.memType.nesMemory
local frame=0
local report=assert(io.open(OUTPUT_DIR..'/routines.txt','w'))
local failures=0
local current=0
local phase='idle'
local tests={}
local noiseVolume=nil
local noiseWrites=0
local ready=false
local function r(address) return emu.read(address,mem) end
local function w(address,value) emu.write(address,value,mem) end
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n')
    if not ok then failures=failures+1 end
end
local function add(name,kind,setup,verify)
    tests[#tests+1]={name=name,kind=kind,setup=setup,verify=verify}
end
local function box(pose,origin,x,y,width,height,bank)
    add('hitbox pose '..pose..' origin '..origin..' bank '..bank,'hitbox',function()
        w(0x80,pose);w(0x47E,origin);w(0x480,y-(pose==5 and 3 or 0));w(0xCC,100)
        w(0x769,bank)
    end,function()
        check(r(0)==x and r(1)==y and r(2)==width and r(3)==height,
            string.format('box %d,%d %dx%d',r(0),r(1),r(2),r(3)))
        check(emu.getState()['mapper.prgReg']==bank,'enemy PRG bank restored')
        check(emu.getState()['cpu.x']==3,'enemy slot X preserved')
    end)
end
box(5,124,116,83,22,10,4)
box(5,92,84,83,22,10,3)
box(5,4,0,83,18,10,1)
box(5,250,242,83,13,10,5)
box(8,112,104,76,14,3,4)
box(9,92,94,117,14,3,5)

for group=0,5 do
    add('hazard group '..group,'lava',function()
        w(0x707,group);w(0xB5,1);w(0xA7,2);w(0xE9,7);w(0x50C,0);w(0x769,4)
    end,function()
        if group>=3 then
            check(r(0xB5)==1 and r(0xA7)==6,'palace lava sets floor without entering death state')
            check(r(0x50C)==0 and r(0xE9)==7,'lava does not trigger injury or hazard flag')
        else
            check(r(0xB5)==2 and r(0x50C)==16 and r(0xE9)==1,'water retains original death state')
        end
    end)
end

add('Inferno starts roar and retains original spell handler','inferno',function()
    w(0x76F,0x80);w(0x769,0)
    for address=0xB6,0xBB do w(address,0) end
end,function()
    check(r(0x5F0)==48 and r(0x76F)==0,'roar starts; Thunder state is consumed')
end)
for i=1,48 do
    add('roar update '..i,'update',function()
        w(0x769,0);w(0x400,0);w(0x777,1);w(0x784,1);w(0x774,0)
        w(0x8D,0);w(0x8E,0)
    end,function()
        if i==48 then
            check(r(0x5F0)==0 and noiseVolume==0x30,'roar finishes with zero-volume override')
            check(noiseWrites>=48,'noise channel receives the synthesized roar envelope')
        end
    end)
end

local function nextTest()
    current=current+1
    local test=tests[current]
    if not test then
        report:write('RESULT '..(failures==0 and 'PASS' or 'FAIL')..'\n')
        report:close();phase='done';stopScenario(failures==0 and 0 or 1);return
    end
    phase=test.kind
    report:write('START '..test.name..'\n');report:flush()
    test.setup()
    local entry=0xE9A2
    if phase=='lava' then entry=0xE0A4 end
    if phase=='inferno' then entry=LABELS.BarbaInferno end
    if phase=='update' then entry=LABELS.BarbaUpdate end
    -- Area-bank switch, call, then park at $0606 until the exec callback.
    local program={0x20,0xC9,0xFF,0x20,entry%256,math.floor(entry/256),0x4C,0x06,0x06}
    for i,value in ipairs(program) do w(0x5FF+i,value) end
    emu.setState({['cpu.pc']=0x0600,['cpu.sp']=0xFD,['cpu.x']=3,['cpu.ps']=0x24})
end

-- The palace path deliberately continues to normal horizontal collision.
-- Observe it before that unrelated code runs, then return to the harness.
emu.addMemoryCallback(function()
    if phase=='lava' and r(0x707)>=3 then
        emu.setState({['cpu.pc']=0x0606})
    end
end,emu.callbackType.exec,0xE12B)
emu.addMemoryCallback(function()
    if phase~='idle' and phase~='done' then
        local test=tests[current]
        if current<=13 or current==#tests then report:write(test.name..'\n') end
        test.verify();nextTest()
    end
end,emu.callbackType.exec,0x0606)
emu.addMemoryCallback(function(address,value)
    if address==0x400C then noiseVolume=value end
    if address==0x400E then noiseWrites=noiseWrites+1 end
end,emu.callbackType.write,0x400C,0x400F)
dofile(TEST_DIR..'/newgame.lua')
emu.addEventCallback(function()
    frame=frame+1
    if frame==120 then ready=true end
end,emu.eventType.endFrame)
emu.addMemoryCallback(function()
    if ready and phase=='idle' then ready=false;nextTest() end
end,emu.callbackType.exec,0xC07B)
