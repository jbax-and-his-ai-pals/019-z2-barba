-- Controlled CPU regression for projectile contact with native breakable stone.
-- The real bank-4 handler E1DD/E1E6 and glove gate run without interception.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local frame,current,errors=0,0,0
local ready,running=false,false
local report=assert(io.open(OUTPUT_DIR..'/combat.txt','w'))
local blockTile=emu.read(4*0x4000+0x051E,emu.memType.nesPrgRom)
assert(blockTile==0x4C,'guarded bank-4 $851E breakable code must be $4C')
local cases={
    {name='live shot without glove',glove=0,active=1,slot=0,broken=false},
    {name='slot zero shot with glove',glove=1,active=1,slot=0,broken=true},
    {name='slot one shot with glove',glove=1,active=1,slot=1,broken=true},
    {name='inactive shot with glove',glove=1,active=0,slot=0,broken=false},
    {name='disintegrating shot with glove',glove=1,active=0x80,slot=0,broken=false},
    {name='offscreen shot with glove',glove=1,active=1,slot=0,page=1,broken=false}
}
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n');report:flush()
    if not ok then errors=errors+1 end
end
local function setup(c)
    for address=0x6000,0x633F do w(address,0x42)end
    for address=0x41A,0x43C do w(address,0)end
    w(0x769,4);w(0x707,4);w(0x786,c.glove)
    w(0x80,5);w(0x47E,0xA6);w(0x480,0xF8);w(0x57D,0x37)
    w(0x4D,0xA0);w(0x3B,0);w(0xCC,0xA0);w(0x29,0x90)
    w(0x72C,0);w(0x72A,0);w(0x70,0x13);w(0xED,0)
    w(0x8D,0);w(0x8E,0)
    w(0x8D+c.slot,c.active);w(0x5A+c.slot,0x48)
    w(0x48+c.slot,c.page or 0);w(0x36+c.slot,0x90)
    -- Native probe: (shot X + 4)>>4 = 4; (shot Y+5+3-32)&F0 = 70.
    -- LEAC0[$1C]=$E0 supplies -32; horizontal table EAA0[$1C]=0.
    w(0x6074,blockTile)
    -- A second stone near the player's body must remain untouched.
    w(0x607A,blockTile)
end
local function verify(c)
    local name=c.name
    check(r(0x6074)==(c.broken and 0x42 or blockTile),name..': glove-gated tile result')
    check(r(0x607A)==blockTile,name..': player-body stone stays intact')
    local debris=0
    for address=0x41A,0x41E do if r(address)~=0 then debris=debris+1 end end
    check(debris==(c.broken and 1 or 0),name..': native debris allocation')
    if c.broken then check(r(0xED)==4,name..': native block-break sound')end
    check(r(0x80)==5 and r(0x47E)==0xA6 and r(0x57D)==0x37,
        name..': player pose, origin X and vertical velocity restored')
    check(r(0x70)==0x13,name..': projectile contact does not recoil player')
    check(r(0x480)==0xF8,name..': melee origin remains disabled')
    check(emu.getState()['mapper.prgReg']==0,name..': player bank restored')
end
local function nextCase()
    current=current+1
    local c=cases[current]
    if not c then
        running=false
        report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
        report:close();stopScenario(errors==0 and 0 or 1);return
    end
    setup(c);report:write('CASE '..c.name..'\n');report:flush()
    local entry=assert(LABELS.BarbaBlocks,'missing BarbaBlocks label')
    local program={0x20,0xC5,0xFF,0x20,entry%256,math.floor(entry/256),0x4C,0x06,0x06}
    for i,value in ipairs(program)do w(0x5FF+i,value)end
    running=true
    emu.setState({['cpu.pc']=0x0600,['cpu.sp']=0xFD,['cpu.x']=3,['cpu.y']=9,['cpu.ps']=0x24})
end
emu.addMemoryCallback(function()
    if running then verify(cases[current]);nextCase()end
end,emu.callbackType.exec,0x0606)
emu.addMemoryCallback(function()
    if ready then ready=false;nextCase()end
end,emu.callbackType.exec,0xC07B)
emu.addEventCallback(function()
    frame=frame+1;if frame==120 then ready=true end
end,emu.eventType.endFrame)
