-- Outdoor eligibility and frame-varying panic/native dialogue selection.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local cases,current,failures={},0,0
local frame,ready,running=0,false,false
local f=assert(io.open(OUTPUT_DIR..'/town-safety.txt','w'))
local function add(world,room,kind,origin,alive)
    cases[#cases+1]={world=world,room=room,kind=kind,origin=origin,alive=alive or 1}
end
for kind=0,63 do for _,origin in ipairs({0,5,127,255})do add(1,0,kind,origin)end end
for room=0,63 do
    add(1,room,0x0C,255);add(2,room,0x0C,255)
    for kind=0x10,0x21 do add(1,room,kind,255);add(2,room,kind,255) end
end
for _,world in ipairs({0,3,4,5})do for kind=0x19,0x1C do add(world,0,kind,255)end end
for origin=0,254 do add(1,0,0x19,origin)end
add(1,0,0x19,255,0);add(1,0,0x19,255,2)
for _,c in ipairs({
    {world=1,room=0,kind=0x19,origin=255,fear=true},
    {world=1,room=0,kind=0x1A,origin=255,fear=true},
    {world=1,room=0,kind=0x1B,origin=255,fear=true},
    {world=2,room=0,kind=0x1C,origin=255,fear=true},
    {world=1,room=0,kind=0x19,origin=5,fear=true},
    {world=1,room=0x1C,kind=0x19,origin=255,fear=false},
    {world=1,room=0,kind=0x1D,origin=5,fear=true},
    {world=1,room=0,kind=0x17,origin=255,fear=false,text=LABELS.TownHealerText},
    {world=1,room=0,kind=0x18,origin=255,fear=false,text=LABELS.TownMagicText},
    {world=1,room=0,kind=0x0C,origin=255,fear=false},
    {world=1,room=0,kind=0x10,origin=255,fear=true},
    {world=1,room=0,kind=0x11,origin=255,fear=true},
    {world=1,room=0,kind=0x12,origin=255,fear=true},
    {world=1,room=0,kind=0x21,origin=255,fear=false},
    {world=1,room=0x1C,kind=0x11,origin=255,fear=false},
    {world=1,room=0,kind=0x0F,origin=255,fear=false},
    {world=1,room=0,kind=0x22,origin=255,fear=false},
    {world=2,room=0,kind=0x19,origin=5,fear=true}
})do c.alive=1;c.dialog=true;cases[#cases+1]=c end
-- All eight frame-dependent phrases, plus protected custom service text.
for phase=0,7 do
    for _,kind in ipairs({0x10,0x11,0x12,0x19,0x1A,0x1B,0x1C,0x1D,0x1E,0x1F,0x20}) do
        cases[#cases+1]={world=1,room=1,kind=kind,origin=5,alive=1,dialog=true,fear=true,phase=phase}
    end
end
for _,c in ipairs({
    {kind=0x0F,service=1,text=LABELS.TownWiseManText},
    {kind=0x17,text=LABELS.TownHealerText},
    {kind=0x18,text=LABELS.TownMagicText}
})do c.world=1;c.room=0x1C;c.origin=255;c.alive=1;c.dialog=true;cases[#cases+1]=c end
local function advance()
    current=current+1
    local c=cases[current]
    if not c then
        f:write(string.format('%d gate cases; %d failures\nRESULT %s\n',#cases,failures,failures==0 and 'PASS' or 'FAIL'))
        f:close();running=false;stopScenario(failures==0 and 0 or 1);return
    end
    w(0x707,c.world);w(0x561,c.room);w(0xB6,c.alive);w(0xBC,c.origin);w(0xA1,c.kind)
    w(0x48B,0);w(0x524,0);w(0x12,c.phase or 0x35);w(0x05,c.service or 0)
    local entry=c.dialog and LABELS.TownDialog or LABELS.TownEligible
    w(0x769,3)
    local program={0x20,0xC9,0xFF,0xA9,0x00,0x20,entry%256,math.floor(entry/256),0x4C,8,6}
    for i,v in ipairs(program)do w(0x5FF+i,v)end
    emu.setState({['cpu.pc']=0x600,['cpu.sp']=0xFD,['cpu.x']=0,['cpu.a']=0,['cpu.ps']=0x24})
end
emu.addMemoryCallback(function()
    if not running then return end
    local c=cases[current]
    if c.dialog then
        local pointer=LABELS.TownFearPointers+(((c.phase or 0x35) ~ c.kind)&7)*2
        local expected=c.fear and (r(pointer)+256*r(pointer+1)) or 0
        if not c.fear then
            local base=r(0xB421+c.world*2)+256*r(0xB422+c.world*2)
            expected=c.text or (r(base)+256*r(base+1))
        end
        if r(0x569)+256*r(0x56A)~=expected or r(0x524)~=1
            or (c.fear and (r(0x566)~=2 or r(0x489)~=0 or r(0x48A)~=0))
            or (c.text and r(0x566)~=0x2A) then
            failures=failures+1;f:write(string.format('FAIL dialogue case %d frame=%d kind=$%02X pointer=$%04X expected=$%04X ready=%d\n',current,frame,c.kind,r(0x569)+256*r(0x56A),expected,r(0x524)))
        end
        advance();return
    end
    local want=c.alive==1 and ((c.kind>=0x10 and c.kind<=0x12) or (c.kind>=0x19 and c.kind<=0x20))
        and (c.world==1 or c.world==2) and c.room<0x14 and c.room~=6
    local actual=(emu.getState()['cpu.ps']&1)~=0
    if want~=actual or emu.getState()['cpu.x']~=0 then
        failures=failures+1;f:write('FAIL gate case '..current..'\n')
    end
    advance()
end,emu.callbackType.exec,0x608)
emu.addEventCallback(function()frame=frame+1;if frame==120 then ready=true end end,emu.eventType.endFrame)
emu.addMemoryCallback(function()
    if ready then ready=false;running=true;w(0x2000,r(0xFF)&0x7F);advance()end
end,emu.callbackType.exec,0xC07B)
