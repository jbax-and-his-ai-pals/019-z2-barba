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
for _,pose in ipairs({5,7,8,9})do
    add('projectile-only rendering pose '..pose,'display',function()
        for address=0x6000,0x633F do w(address,0x42)end
        for address=0x200,0x23F,4 do w(address,0xF8)end
        w(0x769,4);w(0x707,4);w(0x13,0);w(0x80,pose)
        w(0x17,pose==7 and 0 or 1);w(0x479,pose>=8 and 2 or 0)
        w(0xCC,0x50);w(0x4D,0x48);w(0x3B,0);w(0x29,0x90);w(0x9F,1)
        w(0x72A,0);w(0x72C,0);w(0xC8,0);w(0x48D,0);w(0x50C,0)
        w(0x70E,0);w(0x752,0);w(0x480,0x80);w(0x47E,0x60)
    end,function()
        if pose==9 then
            -- Native $F27D derives screen X=$48 from the world coordinate.
            check(r(0x480)==0xAC and r(0x47E)==0x53,'downstab preserves the existing foot hitbox')
            check(r(0x220)==0x70 and r(0x224)==0x70 and r(0x221)==0x08 and r(0x225)==0x06,
                'downstab draws a second torso chunk at the top')
        else
            check(r(0x480)==0xF8,'pose '..pose..' disables native sword/thrust collision')
            check(r(0x220)==0xF8 and r(0x224)==0xF8,'pose '..pose..' hides both attached-flame sprites')
        end
        check(r(0x80)==pose,'renderer preserves native attack pose')
        check(emu.getState()['mapper.prgReg']==0,'renderer retains player PRG bank')
    end)
end

for group=0,5 do
    add('hazard group '..group,'lava',function()
        w(0x707,group);w(0xB5,1);w(0xA7,2);w(0xE9,7);w(0x50C,0);w(0x769,4)
    end,function()
        if group==0 or group>=3 then
            check(r(0xB5)==1 and r(0xA7)==6,'encounter/palace hazard sets floor without entering death state')
            check(r(0x50C)==0 and r(0xE9)==7,'encounter/palace hazard does not trigger injury or hazard flag')
        else
            check(r(0xB5)==2 and r(0x50C)==16 and r(0xE9)==1,'town water retains original death state')
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
    local entry=nil
    if phase=='display' then entry=LABELS.BarbaDisplay end
    if phase=='lava' then entry=0xE0A4 end
    if phase=='inferno' then entry=LABELS.BarbaInferno end
    if phase=='update' then entry=LABELS.BarbaUpdate end
    assert(entry,'missing routine entry for '..phase)
    -- Display/update/spells run in player PRG0; hazards use the area bank.
    local swap=phase=='lava' and 0xC9 or 0xC5
    local program={0x20,swap,0xFF,0x20,entry%256,math.floor(entry/256),0x4C,0x06,0x06}
    for i,value in ipairs(program) do w(0x5FF+i,value) end
    emu.setState({['cpu.pc']=0x0600,['cpu.sp']=0xFD,['cpu.x']=3,['cpu.ps']=0x24})
end

-- The palace path deliberately continues to normal horizontal collision.
-- Observe it before that unrelated code runs, then return to the harness.
emu.addMemoryCallback(function()
    if phase=='lava' and (r(0x707)==0 or r(0x707)>=3) then
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
    if ready and phase=='idle' then ready=false;w(0x2000,0);nextTest() end
end,emu.callbackType.exec,0xC07B)
