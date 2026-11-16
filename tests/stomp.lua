-- Jump-stomp kills easy unshielded enemies (HP 1..16) while sparing
-- shielded palace enemies ($18-$1A, $1F, $23) and high-HP (>16) enemies.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local frame,age,phase,errors=0,0,0,0
local base,pending=nil,false
local slot=1
local f=assert(io.open(OUTPUT_DIR..'/stomp.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
local phases={
    {name='palace Bot (HP 4)',world=3,id=0x04,hp=4,ey=176,expectKill=true},
    {name='palace Bago Bago (HP 8)',world=3,id=0x10,hp=8,ey=176,expectKill=true},
    {name='palace Rope (HP 12)',world=3,id=0x12,hp=12,ey=176,expectKill=true},
    {name='palace Moa (HP 16)',world=3,id=0x07,hp=16,ey=176,expectKill=true},
    {name='palace Red Stalfos shielded (HP 8)',world=3,id=0x1F,hp=8,ey=160,expectKill=false},
    {name='palace Orange Ironknuckle shielded (HP 16)',world=3,id=0x18,hp=16,ey=160,expectKill=false},
    {name='west Red Moblin (HP 12)',world=0,id=0x15,hp=12,ey=160,expectKill=true},
    {name='west Orange Goriya (HP 12)',world=0,id=0x19,hp=12,ey=160,expectKill=true},
    {name='west Megmat (HP 4)',world=0,id=0x1F,hp=4,ey=176,expectKill=true},
    {name='west Red Daira (HP 24)',world=0,id=0x18,hp=24,ey=160,expectKill=false},
}
local killSeen=false

local function setupPhase()
    emu.loadSavestate(base)
    local p=phases[phase]
    age=0;killSeen=false
    for s=0,5 do if r(0xB6+s)==1 and r(0xA1+s)~=0x02 then w(0xB6+s,0) end end
    w(0x707,p.world)
    w(0xB6+slot,1);w(0xA1+slot,p.id)
    w(0x4E+slot,140);w(0x3C+slot,0);w(0x2A+slot,p.ey)
    w(0xC2+slot,p.hp);w(0x040E+slot,0);w(0x71+slot,0)
    w(0x4D,140);w(0x3B,0);w(0x29,p.ey-24);w(0x0479,1);w(0x057D,2)
    w(0x0518,0);w(0x050C,0)
end

emu.addEventCallback(function()
    emu.setInput(newGameInput(frame),0)
end,emu.eventType.inputPolled)

emu.addMemoryCallback(function()
    if not pending then return end
    pending=false
    if not base then base=emu.createSavestate() end
    phase=phase+1
    if not phases[phase] then
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close()
        stopScenario(errors==0 and 0 or 1);return
    end
    setupPhase()
end,emu.callbackType.exec,0xC07B)

emu.addEventCallback(function()
    frame=frame+1
    if not base then
        if frame==1000 then
            w(0x707,3);w(0x706,0);w(0x769,3);w(0x561,5)
            w(0x701,0);w(0x75C,0);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1)
        end
        if frame==1150 then pending=true end
        return
    end
    if pending or not phases[phase] then return end
    age=age+1
    local p=phases[phase]
    w(0x4E+slot,140);w(0x71+slot,0);w(0x2A+slot,p.ey)
    if r(0xC2+slot)==0 or r(0xB6+slot)~=1 then killSeen=true end
    if age==15 then
        local info='(b6='..r(0xB6+slot)..' hp='..r(0xC2+slot)..' y='..r(0x29)..' hurt='..r(0x050C)..' air='..r(0x0479)..')'
        if p.expectKill then
            check(killSeen,p.name..' stomp-killed '..info)
        else
            check(not killSeen and r(0xC2+slot)==p.hp,p.name..' survived stomp '..info)
        end
        pending=true
    end
end,emu.eventType.endFrame)
