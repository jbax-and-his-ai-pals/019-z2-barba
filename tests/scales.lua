-- SCALES (vanilla Shield): navy outline, sky-blue body, white belly, cast roar + decor flash, and a
-- clang + short palette flash when Barba is hit while shielded.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local pal=emu.memType.nesPaletteRam
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/scales.txt','w'))
local errors=0
local frame=0
local castFrame=nil
local sawRoar,sawDecor=false,false
local clangs=0
local hitFrame=nil
local sawHitFlash=false
local baseline=0
local done=false

local function check(ok,msg)
    report:write((ok and 'PASS ' or 'FAIL ')..msg..'\n')
    if not ok then errors=errors+1 end
end

local function input()
    local b=newGameInput(frame)
    if castFrame and frame==castFrame then
        b.select=true
    end
    emu.setInput(b,0)
end

-- Count shield clangs ($EC bit 1) requested from the bank-3 pad (ScalesTick);
-- the native cast sequence writes its own $EC=$02 from $9927.
emu.addMemoryCallback(function(addr,value)
    if castFrame and frame>castFrame and (value&0x02)~=0 and (r(0xEC)&0x02)==0 and not done then
        local pc=emu.getState()['cpu.pc'] or 0
        if pc<0x9D0A or pc>=0xA000 then return end
        clangs=clangs+1
    end
end,emu.callbackType.write,0x00EC)

local function finish()
    done=true
    report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
    report:close()
    stopScenario(errors==0 and 0 or 1)
end

local function tick()
    frame=frame+1
    if not castFrame and frame>700 and r(0x0736)==0x0B and r(0x074C)==0 and r(0x0524)==0 and r(0xDE)==0 then
        w(0x077B,1)    -- learn SCALES
        w(0x0749,0)    -- select SCALES
        w(0x074A,0)
        w(0x0773,0xFF) -- full MP
        castFrame=frame+1
    end
    if not castFrame then
        if frame==2000 then
            check(false,'entered side-view to cast SCALES')
            finish()
        end
        return
    end
    if frame<=castFrame then return end
    local t=frame-castFrame
    if r(0x05F0)>0 or (LABELS.RoarAudio and (r(0x05EE)&0x80)~=0) then sawRoar=true end
    if (r(0x074B)&0x80)~=0 then sawDecor=true end
    if t==6 then screenshot('scales-cast') end
    if t==60 then
        check(r(0x070F)~=0,'SCALES sets the shield flag ($070F='..string.format('%02X',r(0x070F))..')')
        check(r(0x69DE)==0x30,'SCALES belly stays white ($69DE='..string.format('%02X',r(0x69DE))..')')
        check(emu.read(0x13,pal)==0x30,'PPU belly (colour 3) shows white ($3F13='..string.format('%02X',emu.read(0x13,pal))..')')
        check(emu.read(0x12,pal)==0x21,'PPU body (colour 2) shows sky blue ($3F12='..string.format('%02X',emu.read(0x12,pal))..')')
        check(emu.read(0x11,pal)==0x01,'PPU outline (colour 1) turns navy ($3F11='..string.format('%02X',emu.read(0x11,pal))..')')
        check(sawRoar,'SCALES cast plays the dragon roar')
        check(sawDecor,'SCALES cast flashes the scenery ($074B bit 7)')
        check(clangs==0,'no clang before any hit (clangs='..clangs..')')
        screenshot('scales-blue')
        -- Simulate a hit landing: the native damage path sets the injured timer.
        hitFrame=frame
        w(0x050C,0x20)
    end
    if hitFrame and frame>hitFrame and frame<=hitFrame+3 and r(0x074B)>0 then sawHitFlash=true end
    if hitFrame and frame==hitFrame+4 then
        check(clangs>=1,'shielded hit plays the shield clang (clangs='..clangs..')')
        check(sawHitFlash,'shielded hit flashes Barba\'s palette ($074B)')
    end
    if hitFrame and frame==hitFrame+40 then
        check(emu.read(0x11,pal)==0x01 and emu.read(0x12,pal)==0x21,'blues restored after the hit flash ($3F11/$3F12='..string.format('%02X/%02X',emu.read(0x11,pal),emu.read(0x12,pal))..')')
        baseline=clangs
        w(0x076F,r(0x076F)&0xFE) -- shield over (magic state bit 0, as on side-view init)
        w(0x070F,0)
        w(0x69DE,0x30)
    end
    if hitFrame and frame==hitFrame+42 then
        w(0x050C,0x20) -- unshielded hit
    end
    if hitFrame and frame==hitFrame+48 then
        check(clangs==baseline,'unshielded hit plays no clang (clangs='..clangs..')')
        check(r(0x05EC)==0,'cast latch clears when the shield ends')
        check(emu.read(0x11,pal)==0x16 and emu.read(0x12,pal)==0x27 and emu.read(0x13,pal)==0x30,'red outline, orange body and white belly return when the shield ends ($3F12/$3F13='..string.format('%02X/%02X',emu.read(0x12,pal),emu.read(0x13,pal))..')')
        finish()
    end
end

emu.addEventCallback(input,emu.eventType.inputPolled)
emu.addEventCallback(tick,emu.eventType.endFrame)
