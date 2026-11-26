-- Verify Phase 2 Arcade Spells: DOUBLE, LUCKY, HEAVY, CLOCK, STAR.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a) return emu.read(a,m) end
local function w(a,v) emu.write(a,v,m) end
local frame,warped,t0,errors=0,false,nil,0
local f=assert(io.open(OUTPUT_DIR..'/arcade-spells-p2.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n'); f:flush()
    if not ok then errors=errors+1 end
end

local botKilledByStar=false
local luckyDropSeen=false
local xpBefore=0

local function input()
    local b=newGameInput(frame)
    if t0 then
        local dt=frame-t0
        b.b=(dt>=10 and dt<13)
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
        -- Wait until frame settles (Palace 3 room enemies spawned)
        if not settled then settled=frame+15 end
        if frame<settled then return end
        t0=frame
        for s=0,5 do w(0xB6+s,0) end
        -- Set up Palace 3 Ironknuckle in slot 1 (shielded high, HP=16)
        w(0xB6+1,1); w(0xA1+1,0x18); w(0xC2+1,0x10); w(0x0444+1,1)
        w(0x4E+1,156); w(0x3C+1,0); w(0x2A+1,176); w(0x040E+1,0); w(0x71+1,0); w(0x60+1,1)
        w(0x4D,120); w(0x3B,0); w(0x29,176); w(0x9F,1); w(0x5F,1)
        w(0x76F,0x10); w(0x777,1) -- Attack level 2 = 3 dmg -> 6 dmg with HEAVY
        w(0x6681,0x02) -- HEAVY active
    end
    if not t0 then
        if frame>1800 then check(false,'reached Palace 3'); f:write('RESULT FAIL\n'); f:close(); emu.stop(1) end
        return
    end
    local dt=frame-t0
    if dt<35 then
        w(0x4E+1,156); w(0x71+1,0); w(0x0444+1,1)
    end
    if dt==35 then
        local hp=r(0xC2+1)
        check(hp<16,'HEAVY bypasses Ironknuckle high shield (hp='..hp..')')
        check(hp<=10,'HEAVY deals 2x damage (hp='..hp..')')
        -- Test DOUBLE (2x XP)
        w(0x6681,0); w(0x6680,0x04)
        xpBefore=r(0x776)
        w(0x756,5); w(0x755,0)
    end
    if dt==50 then
        local gained=(r(0x776)-xpBefore) & 0xFF
        check(gained==10,'DOUBLE doubles XP gained (gained='..gained..')')
        -- Test CLOCK freeze
        w(0x6680,0); w(0x6681,0x01); w(0x6682,0x40)
        w(0xB6+2,1); w(0xA1+2,4); w(0xC2+2,4)
        w(0x4E+2,180); w(0x3C+2,0); w(0x2A+2,176); w(0x040E+2,0)
        w(0x66E6+2,180); w(0x66EC+2,0); w(0x66F2+2,176)
    end
    if dt>=51 and dt<65 then
        w(0x71+2,0x20)
    end
    if dt==65 then
        check(r(0x4E+2)==180,'CLOCK freezes enemy X position (x='..r(0x4E+2)..')')
        -- Test STAR + LUCKY
        w(0x6682,0)
        w(0x6683,3) -- LUCKY count = 3
        w(0x6680,0x10); w(0x668F,0x40) -- STAR active
        w(0xB6+2,1); w(0xA1+2,4); w(0xC2+2,4)
        w(0x4E+2,r(0x4D)); w(0x3C+2,r(0x3B)); w(0x2A+2,r(0x29))
    end
    if dt>=66 and dt<80 then
        if r(0xB6+2)~=1 then botKilledByStar=true end
        if r(0x048E+2)==0x08 or r(0x048E+2)==0x10 then luckyDropSeen=true end
    end
    if dt==80 then
        check(r(0x50C)>0,'STAR grants contact invincibility (050C='..r(0x50C)..')')
        check(botKilledByStar,'STAR touch-kills overlapping Bot')
        check(r(0x6683)<3,'LUCKY decrements drop counter on kill (cnt='..r(0x6683)..')')
        check(luckyDropSeen,'LUCKY forces Blue Jar or 50-XP P-Bag drop')
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n'); f:close()
        emu.stop(errors==0 and 0 or 1)
    end
end

emu.addEventCallback(input,emu.eventType.inputPolled)
emu.addEventCallback(tick,emu.eventType.endFrame)
