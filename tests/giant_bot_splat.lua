-- Verify Giant Bot ($1E) split in Great Palace triggers the comical splat SFX
-- ($635E timer, Bank 5 $A186 hook, Bank 2/6 APU envelope) and spawns 5 Bots ($04).
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local frame,age,errors=0,0,0
local base,pending=nil,false
local f=assert(io.open(OUTPUT_DIR..'/giant_bot_splat.txt','w'))
local function check(ok,msg)
    if done then return end
    f:write((ok and 'PASS ' or 'FAIL ')..msg..string.char(10));f:flush()
    if not ok then errors=errors+1 end
end
local function finish()
    if done then return end
    done=true
    f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..string.char(10));f:close()
    stopScenario(errors==0 and 0 or 1)
end

local SPLAT_TIMER=0x635E
local spawned=false
local splitAge=nil
local sawTrigger=false
local sawNoise=0
local sawLoopedNoise=false
local sawBloop1=false
local sawBloop2=false
local sawSilence=false
local botsAtSplit=0
local done=false

emu.addEventCallback(function()
    if not base then emu.setInput(newGameInput(frame),0) return end
    emu.setInput({b=(age>=155 and age%12<3)},0)
end,emu.eventType.inputPolled)

emu.addMemoryCallback(function()
    if not pending then return end
    pending=false
    base=emu.createSavestate()
    -- Great Palace (world 5, region 2) room $35 (flat floor), bank 5.
    w(0x707,5);w(0x706,2);w(0x70A,2);w(0x769,5);w(0x561,0x35);w(0x568,6);w(0x56B,7);w(0x56C,2)
    w(0x701,0);w(0x75C,0);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1);w(0x748,0x35)
    w(0x770,0xFF);w(0x771,0xFF)
end,emu.callbackType.exec,0xC07B)

emu.addMemoryCallback(function(addr,val)
    if not splitAge and val==14 then
        sawTrigger=true
        splitAge=age
    end
end,emu.callbackType.write,SPLAT_TIMER)

emu.addMemoryCallback(function(addr,val)
    if splitAge and (age-splitAge)<=20 then
        sawNoise=sawNoise+1
        if (val&0x80)~=0 then sawLoopedNoise=true end
    end
end,emu.callbackType.write,0x400E)

emu.addMemoryCallback(function(addr,val)
    if splitAge and (age-splitAge)<=20 then
        if val==0x8A then sawBloop1=true end
        if val==0x89 then sawBloop2=true end
        if val==0x08 then sawSilence=true end
    end
end,emu.callbackType.write,0x4005)

emu.addEventCallback(function()
    if done then return end
    frame=frame+1
    if not base then if frame==1000 then pending=true end return end
    age=age+1
    if age<150 then return end
    w(0x9F,1);w(0x5F,1);w(0x774,0xFF) -- face right, full HP
    local px,pg,py=r(0x4D),r(0x3B),r(0x29)
    if age==150 then
        -- Clear slots 0..5 and spawn Giant Bot ($1E) in slot 1 at HP $30 (splits on next hit).
        for s=0,5 do w(0xB6+s,0) end
        w(0xB6+1,1);w(0xA1+1,0x1E);w(0xC2+1,0x30);w(0x81+1,1);w(0xA8+1,0)
        w(0x444+1,0x33);w(0x4E+1,(px+0x14)&0xFF);w(0x3C+1,pg+((px+0x14)>=0x100 and 1 or 0));w(0x2A+1,py)
        w(0x040E+1,0);w(0x0504+1,0)
        spawned=true
    end
    if age==155 and not splitAge then
        w(0xC2+1,0x2C) -- drop HP below $30 to trigger Giant Bot split
    end
    if splitAge and age==splitAge+1 then
        for s=1,5 do
            if r(0xB6+s)==1 and r(0xA1+s)==0x04 then botsAtSplit=botsAtSplit+1 end
        end
    end
    if splitAge and age==splitAge+20 then
        check(sawTrigger,'Giant Bot split set SPLAT_TIMER=14')
        check(botsAtSplit==5,string.format('Giant Bot split into 5 small Bots (%d)',botsAtSplit))
        check(sawNoise>=10,string.format('Splat drove Noise channel (%d frames)',sawNoise))
        check(sawLoopedNoise,'Splat used looped-noise squelch frames')
        check(sawBloop1 and sawBloop2,'Splat played both Pulse 2 downward bloops ($8A/$89)')
        check(sawSilence and r(SPLAT_TIMER)==0,string.format('Splat silenced cleanly and cleared timer (%d)',r(SPLAT_TIMER)))
        finish()
    end
    if age>600 then
        check(false,string.format('timed out waiting for Giant Bot split (mode=%02X trig=%s A1=%02X,%02X,%02X C2=%02X B6=%02X)',r(0x736),tostring(sawTrigger),r(0xA1+1),r(0xA1+2),r(0xA1+3),r(0xC2+1),r(0xB6+1)))
        finish()
    end
end,emu.eventType.endFrame)
