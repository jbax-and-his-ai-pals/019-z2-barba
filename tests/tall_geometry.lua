-- Controlled CPU harness for raised-head clearance and extra OAM ownership.
-- Execute the real bank-4 solid predicate through TerrainBatch. Tile $42
-- is empty and $4C is solid in this area's native false-wall table.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local frame=0
local ready=false
local current=0
local failures=0
local running=false
local tests={}
local report=assert(io.open(OUTPUT_DIR..'/tall-geometry.txt','w'))
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n');report:flush()
    if not ok then failures=failures+1 end
end
local function add(name,entry,setup,verify)
    tests[#tests+1]={name=name,entry=entry,setup=setup,verify=verify}
end
local function baseline()
    for address=0x6000,0x633F do w(address,0x42)end
    for address=0x200,0x23F,4 do w(address,0xF8)end
    w(0x769,4);w(0x707,4);w(0x13,0);w(0x80,3);w(0x17,1)
    w(0xCC,0x50);w(0x4D,0x48);w(0x3B,0);w(0x29,0x90);w(0x9F,1)
    w(0x72A,0);w(0x72C,0);w(0xC8,0);w(0x48D,0);w(0x50C,0)
    w(0x70E,0);w(0x752,0);w(0x479,0);w(0x5F6,0)
end
local function geometry(name,setup,x,y,flags)
    add(name,'BarbaGeometry',setup,function()
        check(r(0x5F6)==flags,'geometry flags '..r(0x5F6)..' expected '..flags)
        if x then check(r(0x5F2)==x and r(0x5F3)==y,
            string.format('mouth %02X,%02X expected %02X,%02X',r(0x5F2),r(0x5F3),x,y))end
        local state=emu.getState()
        check(state['cpu.x']==7 and state['cpu.y']==9,'geometry preserves caller X and Y')
        check(state['mapper.prgReg']==0,'terrain probe restores player PRG bank')
    end)
end
geometry('standing right in open space',function()end,0x6C,0x84,1)
geometry('standing left in open space',function()w(0x9F,2)end,0x4C,0x84,1)
geometry('crouch keeps native low lane',function()w(0x17,0);w(0x80,6)end,0x6C,0x9A,1)
geometry('airborne low shield retains full-body mouth',function()
    w(0x17,0);w(0x80,6);w(0x479,2)
end,0x6C,0x84,1)
geometry('left head edge under actual solid tile',function()w(0x6064,0x4C)end,0x6C,0x94,3)
geometry('right head edge under actual solid tile',function()w(0x6066,0x4C)end,0x6C,0x94,3)
geometry('head bottom edge catches stone below its top row',function()
    w(0x29,0x88);w(0x6064,0x4C)
end,0x6C,0x8C,3)
geometry('right probe crosses a world-page boundary',function()
    w(0x4D,0xF0);w(0x6130,0x4C)
end,0x6C,0x94,3)
geometry('near top of screen tucks head safely',function()w(0x29,0x20)end,0x6C,0x24,3)
geometry('right screen edge invalidates wrapped muzzle',function()w(0xCC,0xF0)end,nil,nil,0)
geometry('left screen edge invalidates wrapped muzzle',function()w(0xCC,2);w(0x9F,2)end,nil,nil,0)
geometry('Fairy excludes tall geometry',function()w(0x13,8)end,nil,nil,0)
geometry('item pose excludes tall geometry',function()w(0x80,0x0C)end,nil,nil,0)

local extraHead={0x204,0x24C,0x2F8}
local function allHidden(addresses)
    for _,address in ipairs(addresses)do if r(address)~=0xF8 then return false end end
    return true
end
add('open-space idle displays raised head row','BarbaDisplay',function()end,function()
    local visible=0
    for _,address in ipairs(extraHead)do if r(address)==0x80 then visible=visible+1 end end
    check(visible>=2,'raised head uses extra OAM row at actor Y minus 16')
end)
add('ceiling tuck moves head down and hides middle row','BarbaDisplay',function()
    w(0x6064,0x4C)
end,function()
    local moved=0
    for _,address in ipairs(extraHead)do if r(address)==0x90 then moved=moved+1 end end
    check(moved>=2,'tucked head remains within native actor height')
    check(allHidden({0x208,0x20C,0x210}),'middle neck row is hidden while tucked')
end)
add('crouching does not leave a raised head ghost','BarbaDisplay',function()
    w(0x17,0);w(0x80,6)
end,function()check(allHidden(extraHead),'crouch hides all extra head sprites')end)
for _,facing in ipairs({1,2})do
    add('ascent displays full body facing '..facing,'BarbaDisplay',function()
        w(0x80,6);w(0x479,2);w(0x9F,facing)
    end,function()
        check(not allHidden(extraHead),'ascent retains the raised head')
        check(not allHidden({0x208,0x20C,0x210}),'ascent retains the middle body')
        check(not allHidden({0x214,0x218,0x21C}),'ascent retains the lower body')
        check(r(0x80)==6 and r(0x479)==2,'visual jump does not change native physics state')
    end)
end
add('airborne low attack retains full body','BarbaDisplay',function()
    w(0x80,7);w(0x17,0);w(0x479,2)
end,function()
    check(not allHidden(extraHead),'airborne low attack retains raised jaws')
    check(not allHidden({0x214,0x218,0x21C}),'airborne attack retains the lower body')
end)
add('Fairy does not leave extra head sprites','BarbaDisplay',function()
    w(0x13,8)
end,function()check(allHidden(extraHead),'Fairy owns no extra tall-head OAM')end)
add('item hold does not leave extra head sprites','BarbaDisplay',function()
    w(0x80,0x0C);w(0x49D,0)
end,function()check(allHidden(extraHead),'item hold owns no extra tall-head OAM')end)

local function nextTest()
    current=current+1
    local test=tests[current]
    if not test then
        running=false
        report:write('RESULT '..(failures==0 and 'PASS' or 'FAIL')..'\n');report:close()
        stopScenario(failures==0 and 0 or 1);return
    end
    baseline();test.setup()
    report:write('CASE '..test.name..'\n');report:flush()
    local entry=assert(LABELS[test.entry],'Missing assembled label '..test.entry)
    local program={0x20,0xC5,0xFF,0x20,entry%256,math.floor(entry/256),0x4C,0x06,0x06}
    for i,value in ipairs(program)do w(0x5FF+i,value)end
    running=true
    emu.setState({['cpu.pc']=0x0600,['cpu.sp']=0xFD,['cpu.x']=7,['cpu.y']=9,['cpu.ps']=0x24})
end
emu.addMemoryCallback(function()
    if running then tests[current].verify();nextTest()end
end,emu.callbackType.exec,0x0606)
emu.addEventCallback(function()
    frame=frame+1
    if frame==120 then ready=true end
end,emu.eventType.endFrame)
emu.addMemoryCallback(function()
    if ready then ready=false;nextTest()end
end,emu.callbackType.exec,0xC07B)
