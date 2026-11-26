-- Verify Phase 3 Arcade Spells: DECOY, AXE, BARREL, LOCK, BLADE.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a) return emu.read(a,m) end
local function w(a,v) emu.write(a,v,m) end
local frame,warped,t0,settled,errors=0,false,nil,nil,0
local f=assert(io.open(OUTPUT_DIR..'/arcade-spells-p3.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n'); f:flush()
    if not ok then errors=errors+1 end
end

local decoySpriteSeen,decoyKilled=false,false
local axeArcSeen,axeKilled=false,false
local barrelMoved,barrelKilled=false,false
local lockSteered,bladeSteered=false,false
local lockY0,bladeY0=nil,nil

local function input()
    local b=newGameInput(frame)
    if t0 then
        local dt=frame-t0
        b.select=(dt>=2 and dt<5) or (dt>=25 and dt<28) or (dt>=50 and dt<53) or (dt>=75 and dt<78)
        b.b=(dt>=78 and dt<81) or (dt>=105 and dt<108)
        b.up=(dt>=105 and dt<120)
    end
    emu.setInput(b,0)
end

local function tick()
    frame=frame+1
    if not warped and frame>=900 and r(0x736)==0x0B then
        warped=true
        w(0x707,3); w(0x706,0); w(0x769,3); w(0x561,5)
        w(0x701,0); w(0x75C,0); w(0x704,0); w(0x736,0); w(0x73D,0); w(0x726,1)
        return
    end
    if warped and not t0 and r(0x736)==0x0B and r(0x524)==0 then
        if not settled then settled=frame+15 end
        if frame<settled then return end
        t0=frame
        for s=0,5 do w(0xB6+s,0) end
        w(0x4D,120); w(0x3B,0); w(0x29,176); w(0x9F,1); w(0x5F,1)
        w(0x773,0xFF); w(0x778,7)
        w(0x648B,0x57); w(0x63B1,1); w(0x63B3,1); w(0x63B5,1); w(0x63B7,1)
        -- 1) DECOY (slot 8): Bot starts at 170 so decoy sprite is visible first, then moves onto 120
        w(0x749,8); w(0x74A,0)
        w(0xB6+1,1); w(0xA1+1,4); w(0xC2+1,4); w(0x4E+1,170); w(0x3C+1,0); w(0x2A+1,176); w(0x040E+1,0)
    end
    if not t0 then
        if frame>1800 then check(false,'reached Palace 3'); f:write('RESULT FAIL\n'); f:close(); emu.stop(1) end
        return
    end
    local dt=frame-t0
    if dt==10 then w(0x4E+1,120) end
    if dt>=5 and dt<22 then
        if r(0x2E0)<0xF0 then decoySpriteSeen=true end
        if r(0xB6+1)~=1 then decoyKilled=true end
    end
    if dt==22 then
        check(decoySpriteSeen,'DECOY draws sprite in OAM $02E0')
        check(decoyKilled,'DECOY detonates and kills overlapping Bot')
        -- 2) AXE (slot 9)
        w(0x6680,0); w(0x749,9); w(0x74A,0)
        w(0xB6+1,1); w(0xA1+1,4); w(0xC2+1,4); w(0x4E+1,140); w(0x3C+1,0); w(0x2A+1,160); w(0x040E+1,0)
    end
    if dt>=29 and dt<48 then
        if r(0x6690)>0 and r(0x6693)<176 then axeArcSeen=true end
        if r(0xB6+1)~=1 then axeKilled=true end
    end
    if dt==48 then
        check(axeArcSeen,'AXE arcs upward above player')
        check(axeKilled,'AXE hits and kills Bot in arc')
        -- 3) BARREL (slot 11)
        w(0x6680,0); w(0x6690,0); w(0x749,11); w(0x74A,0)
        w(0xB6+1,1); w(0xA1+1,4); w(0xC2+1,4); w(0x4E+1,150); w(0x3C+1,0); w(0x2A+1,196); w(0x040E+1,0)
    end
    if dt>=54 and dt<73 then
        if r(0x6689)>120 then barrelMoved=true end
        if r(0xB6+1)~=1 then barrelKilled=true end
    end
    if dt==73 then
        check(barrelMoved,'BARREL rolls forward across room')
        check(barrelKilled,'BARREL crushes Bot in path')
        -- 4) LOCK (slot 13)
        w(0x6680,0); w(0x6688,0); w(0x749,13); w(0x74A,0)
        w(0xB6+1,1); w(0xA1+1,4); w(0xC2+1,4); w(0x4E+1,190); w(0x3C+1,0); w(0x2A+1,130); w(0x040E+1,0)
    end
    if dt>=80 and dt<100 then
        if r(0x8D)==1 then
            if not lockY0 then lockY0=r(0x36) end
            if r(0x36)<lockY0 then lockSteered=true end
        end
    end
    if dt==102 then
        check(r(0x668E)>0,'LOCK acquires active enemy slot')
        check(lockSteered,'LOCK steers fireball toward locked enemy Y')
        -- 5) BLADE (slot 14)
        w(0x6680,0x40); w(0x668E,0); w(0x8D,0); w(0x8E,0)
    end
    if dt>=107 and dt<122 then
        if r(0x8D)==1 then
            if not bladeY0 then bladeY0=r(0x36) end
            if r(0x36)<bladeY0 then bladeSteered=true end
        end
    end
    if dt==125 then
        check(bladeSteered,'BLADE steers fireball 8-way with D-pad Up')
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n'); f:close()
        emu.stop(errors==0 and 0 or 1)
    end
end

emu.addEventCallback(input,emu.eventType.inputPolled)
emu.addEventCallback(tick,emu.eventType.endFrame)
