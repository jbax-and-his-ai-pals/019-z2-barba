-- Isolated backed-projectile CPU checks. Native block and movement routines
-- run unchanged. Collision protocol tests intercept only the fixed native
-- helper entry to inspect aliasing, mutate a shot, and verify restoration.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/extra-fire.txt','w'))
local frame,index,errors=0,0,0
local ready,running=false,false
local cases={}
local helperCalls=0
local fields={0x8D,0x36,0x5A,0x48,0x7D,0x6D,0x26,0x5CA,0x3E3,0x5FC,0x9D}
local saved={}
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n');report:flush()
    if not ok then errors=errors+1 end
end
local function base()
    helperCalls=0
    w(0x769,4);w(0x707,4);w(0x5FF,1);w(0x645C,1);w(0x480,0xF8)
    w(0x72C,0);w(0x72A,0);w(0xCD,0x80);w(0x57D,0x37)
    w(0x10,3);w(0x11,0x79);w(0xB9,1);w(0x411,0)
    w(0x51,0);w(0x3F,1);w(0x2D,0x80) -- enemy slot 3 at world X=$100
    local values={1,0x66,0xAA,1,0xE0,2,1,0xD2,0x73,23,0x38}
    saved={}
    for i,a in ipairs(fields)do w(a,values[i]);saved[a]=values[i]end
    w(0x8E,1);saved[0x8E]=1
    for a=0x238,0x23B do w(a,a%256);saved[a]=a%256 end
    for a=0x6400,0x642F do w(a,0)end
    for slot=0,2 do
        local a=0x6400+16*slot
        local values2={1,0x80+slot*8,slot*8,1,0x20,1,1,0xD2,0,33,({0x3C,0x44,0x48})[slot+1]}
        for i,v in ipairs(values2)do w(a+i-1,v)end
    end
end
local function preserved(name)
    local ok=true
    for a,v in pairs(saved)do if r(a)~=v then ok=false end end
    check(ok,name..': native slot zero, slot one and OAM preserved')
end
local function add(name,kind,entry,setup,verify)
    cases[#cases+1]={name=name,kind=kind,entry=entry,setup=setup,verify=verify}
end
for _,kind in ipairs({'enemy','shield'})do
    add(kind..' alias and copy-back',kind,kind=='enemy' and LABELS.EnemyFireGateway or LABELS.BarbaShieldFire,
        function()base()end,function(name)
            local expectCalls=kind=='shield' and 3 or 4
            check(helperCalls==expectCalls,name..': expected native/extra helper calls ('..helperCalls..'/'..expectCalls..')')
            for slot=0,2 do
                local a=0x6400+slot*16
                check(r(a)==0 and r(a+1)==0x81+slot*8 and r(a+7)==0xD3 and r(a+8)==1,
                    name..': record '..slot..' receives native mutation')
            end
            preserved(name)
            local state=emu.getState()
            if kind=='shield' then
                check(r(0x10)==3 and r(0x11)==0x79,
                    name..': scratch preserved across gateway')
            else
                check(state['cpu.y']==0xA6 and state['cpu.x']==3 and r(0x10)==3 and r(0x11)==0x79,
                    name..': original helper Y/X/scratch preserved across gateway')
            end
        end)
end
add('shield gateway fast path with EXTRA_LIVE=0','enemy',LABELS.ShieldFireGateway,
    function()base();w(0x645C,0);w(0x51,0x80);w(0x3F,0);w(0x2D,0x80);w(0x447,0)end,
    function(name)
        check(helperCalls==0,name..': skips Bank 0 when EXTRA_LIVE==0')
        preserved(name)
    end)
local skips={
    {name='inactive EXTRA_LIVE guard',apply=function()w(0x645C,0)end},
    {name='inactive records',apply=function()for a=0x6400,0x6420,16 do w(a,0)end end},
    {name='disintegrating records',apply=function()for a=0x6400,0x6420,16 do w(a,0x80)end end},
    {name='inactive enemy',apply=function()w(0xB9,0)end},
    {name='far world X',apply=function()for a=0x6400,0x6420,16 do w(a+3,8)end end},
    {name='far Y',apply=function()w(0x2D,0xD0);for a=0x6400,0x6420,16 do w(a+1,0x10)end end},
    {name='enemy already injured',apply=function()w(0x411,0x30)end},
}
for _,c in ipairs(skips)do
    add(c.name,'enemy',LABELS.EnemyFireGateway,function()base();c.apply()end,function(name)
        -- Inactive or injured enemies skip the native helper in EnemyFireGateway too;
        -- others call $E498 exactly once without bank-swapping into Bank 0.
        local expected=(c.name=='inactive enemy' or c.name=='enemy already injured') and 0 or 1
        check(helperCalls==expected,name..': avoids all extra native bank round trips')
        preserved(name)
    end)
end
add('injury does not bypass shield checks','shield',LABELS.BarbaShieldFire,
    function()base();w(0x411,0x30)end,function(name)
        check(helperCalls==3,name..': all live extras still pass through shield helper')
        preserved(name)
    end)

-- Real native enemy overlap, damage and Fire-only vulnerability. Use native
-- box selector zero and place the backed shot at that box's center.
for _,test in ipairs({
    {name='ordinary Bot without Fire',class=0xD2,attr=0,hit=true},
    {name='Fire-only target without Fire',class=0xD2,attr=0x20,hit=false},
    {name='Fire-only target with Fire',class=0,attr=0x20,hit=true},
})do
    add(test.name,'damage',LABELS.EnemyFireGateway,function()
        base();w(0x8D,0);w(0x8E,0);saved[0x8D]=0;saved[0x8E]=0
        w(0x6410,0);w(0x6420,0)
        w(0xA4,4);w(0xC5,8);w(0xAB,0);w(0x1D,1);w(0x447,0);w(0x411,0)
        w(0x777,1);w(0x51,0x80);w(0x3F,0);w(0xCD,0x80);w(0x2D,0x80)
        w(0x6E21,0);w(0x6DD9,test.attr);w(0x6DFD,0)
        local x=(0x80+r(0xE8FA)+math.floor(r(0xE8FB)/2)-2)%256
        local y=(0x80+r(0xE8FC)+math.floor(r(0xE8FD)/2)-4)%256
        w(0x6401,y);w(0x6402,x);w(0x6403,0);w(0x6407,test.class)
    end,function(name)
        check(r(0xC5)==(test.hit and 6 or 8),name..': native damage/vulnerability result')
        check((r(0x411)>0)==test.hit,name..': native enemy injury state')
        preserved(name)
    end)
end

-- Real native movement/OAM update, including independent fractional/class
-- state. This part does not intercept the native projectile updater.
add('three independent movement slots','update',LABELS.BarbaExtraUpdate,function()
    base()
    for slot=0,2 do
        local a=0x6400+16*slot
        w(a+2,0x80+slot*8);w(a+3,0)
    end
end,function(name)
    for slot=0,2 do
        local a=0x6400+16*slot
        local oam=({0x3C,0x44,0x48})[slot+1]
        check(r(a)==1 and r(a+1)==0x82+slot*8 and r(a+2)==0x82+slot*8
            and r(a+7)==0xD3 and r(a+9)==32,
            name..': record '..slot..' moves diagonally with native timer')
        check(r(0x200+oam)==r(a+1) and r(0x203+oam)==r(a+2)
            and r(0x201+oam)==0x84 and r(0x202+oam)%4==1,
            name..': record '..slot..' has independent orange fireball OAM')
    end
    preserved(name)
    check(r(0x10)==3,name..': enemy index scratch restored')
end)
add('bottom edge cleanup','update',LABELS.BarbaExtraUpdate,function()
    base();for a=0x6400,0x6420,16 do w(a+1,0xDF)end
end,function(name)
    for slot=0,2 do
        local a=0x6400+16*slot
        local oam=({0x3C,0x44,0x48})[slot+1]
        check(r(a)==0 and r(a+9)==0 and r(0x200+oam)==0xF8,
            name..': clears record and hides OAM '..slot)
    end
    preserved(name)
end)

-- Real native block handler and glove gate at all three backed slots.
local blockTile=emu.read(4*0x4000+0x51E,emu.memType.nesPrgRom)
for slot=0,2 do
    for _,glove in ipairs({0,1})do
        add('extra '..slot..' glove '..glove,'blocks',LABELS.BarbaExtraBlocks,function()
            base()
            for a=0x6000,0x633F do w(a,0x42)end
            for a=0x41A,0x43C do w(a,0)end
            for a=0x6400,0x6420,16 do w(a,0)end
            local a=0x6400+slot*16
            w(a,1);w(a+1,0x90);w(a+2,0x48);w(a+3,0);w(0x12,slot)
            w(0x786,glove);w(0x80,5);w(0x47E,0xA6);w(0x70,0x13);w(0xED,0)
            w(0x6074,blockTile);w(0x607A,blockTile)
        end,function(name)
            check(r(0x6074)==(glove==1 and 0x42 or blockTile),name..': native glove-gated stone result')
            check(r(0x607A)==blockTile,name..': stone at player body remains intact')
            check(r(0x80)==5 and r(0x47E)==0xA6 and r(0x57D)==0x37 and r(0x70)==0x13
                and r(0x480)==0xF8,name..': no player recoil, pose or melee change')
            preserved(name)
        end)
    end
end

local function nextCase()
    index=index+1
    local c=cases[index]
    if not c then
        running=false;report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');report:close()
        stopScenario(errors==0 and 0 or 1);return
    end
    c.setup();report:write('CASE '..c.name..'\n');report:flush()
    local e=c.entry
    local p={0x20,0xC5,0xFF,0x20,e%256,math.floor(e/256),0x4C,0x06,0x06,0x60}
    for i,v in ipairs(p)do w(0x5FF+i,v)end
    emu.setState({['cpu.pc']=0x600,['cpu.sp']=0xFD,['cpu.x']=3,['cpu.y']=9,['cpu.ps']=0x24})
end
local function nativeHelper()
    local c=cases[index]
    if not running or (c.kind~='enemy' and c.kind~='shield')then return end
    helperCalls=helperCalls+1
    if c.kind=='shield' or helperCalls>1 then
        check(r(0x8E)==0 and emu.getState()['cpu.x']==3 and r(0x10)==3,
            c.name..': alias excludes real slot one and retains enemy index')
        w(0x8D,0);w(0x36,(r(0x36)+1)%256);w(0x5CA,(r(0x5CA)+1)%256)
        w(0x3E3,(r(0x3E3)+1)%256)
    end
    emu.setState({['cpu.pc']=0x609,['cpu.a']=0x5A,['cpu.y']=0xA6,['cpu.x']=3,['cpu.ps']=0x65})
end
emu.addMemoryCallback(nativeHelper,emu.callbackType.exec,0xE498)
emu.addMemoryCallback(nativeHelper,emu.callbackType.exec,LABELS.ExtraShieldOne0)
emu.addMemoryCallback(function()
    if running then local c=cases[index];c.verify(c.name);nextCase()end
end,emu.callbackType.exec,0x606)
emu.addEventCallback(function()frame=frame+1;if frame==120 then ready=true end end,emu.eventType.endFrame)
emu.addMemoryCallback(function()
    if ready and not running then
        ready=false;running=true;w(0x2000,r(0xFF)&0x7F);nextCase()
    end
end,emu.callbackType.exec,0xC07B)
