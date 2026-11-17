-- Palace 6 Wizzrobe ($1D, bank 4 routine $AE4F) shares its hittable tail ($AEB2)
-- with Carock, whose CarockHit helper calls the boss-death bookkeeping $B1F6.
-- A Wizzrobe killed by breath must die normally: no revive ($B6 back to 1),
-- no boss mark ($6E1D+$1D = $6E3A stays non-$FF), and a second Wizzrobe killed
-- afterwards must not turn into a boss key (item $08).
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local frame,age,errors=0,0,0
local base,pending=nil,false
local f=assert(io.open(OUTPUT_DIR..'/wizzrobe.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
local function finish()
    f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close()
    stopScenario(errors==0 and 0 or 1)
end

local slot=nil
local mark0=nil
local kills=0          -- deaths observed (phase 1 = native wizzrobe, phase 2 = spawned one)
local dying=false
local deadAge=0
local revived,keySeen,bossMarked=false,false,false

emu.addEventCallback(function()
    if not base then emu.setInput(newGameInput(frame),0) return end
    emu.setInput({b=age%20<3},0)
end,emu.eventType.inputPolled)

emu.addMemoryCallback(function()
    if not pending then return end
    pending=false
    base=emu.createSavestate()
    -- Palace 6 (world 4, region 2) room $32: one Wizzrobe, nothing else.
    w(0x707,4);w(0x706,2);w(0x769,4);w(0x561,0x32);w(0x568,5);w(0x56B,6);w(0x56C,1)
    w(0x701,0);w(0x75C,0);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1);w(0x748,0x35)
    w(0x770,0xFF);w(0x771,0xFF)   -- no level-up menu mid-test
end,emu.callbackType.exec,0xC07B)

local function spawn(s)
    w(0xB6+s,1);w(0xA1+s,0x1D);w(0xC2+s,1);w(0xAF+s,0xA0)
    w(0x040E+s,0);w(0x0504+s,0)
end

emu.addEventCallback(function()
    frame=frame+1
    if not base then if frame==1000 then pending=true end return end
    age=age+1
    if age<150 then return end
    if age==150 then
        for s=0,5 do if r(0xB6+s)==1 and r(0xA1+s)==0x1D then slot=s end end
        check(slot~=nil,'Wizzrobe present in Palace 6 room $32')
        if not slot then finish() return end
        mark0=r(0x6E3A)
        check(mark0~=0xFF,string.format('Wizzrobe not boss-marked on entry ($6E3A=%02X)',mark0))
        w(0x4D,0x40);w(0x3B,0)
    end
    local px=r(0x4D)
    w(0x9F,1);w(0x5F,1);w(0x774,0xFF)  -- face right, never die
    local b6,a1=r(0xB6+slot),r(0xA1+slot)
    if r(0x6E3A)==0xFF then bossMarked=true end
    for s=0,5 do if r(0xB6+s)==1 and r(0xA1+s)==0x01 and r(0xAF+s)==0x08 then keySeen=true end end
    if not dying then
        if b6==1 and a1==0x1D and r(0xC2+slot)==1 then
            -- Pin it in its hittable window ($AF $80-$BF) just ahead of Barba.
            local af=r(0xAF+slot)
            if af<0x84 or af>=0xC0 then w(0xAF+slot,0xBC) end
            w(0x4E+slot,math.min(px+0x38,0xF0));w(0x3C+slot,0);w(0x2A+slot,0xB0)
        else
            -- Killed: normally $B6 -> 2; the old shared-tail bug instead left
            -- $B6 = 1 with HP wrapped, which counts as a revive below.
            dying=true;deadAge=age;kills=kills+1
            if b6==1 and a1==0x1D then revived=true end
        end
    else
        if b6==1 and a1==0x1D then revived=true end
        if age-deadAge==150 then
            local tag=kills==1 and 'first' or 'second'
            check(not revived,tag..' Wizzrobe stays dead (no $B6=1 revive)')
            check(not bossMarked,string.format('%s kill leaves $6E3A unmarked (%02X)',tag,r(0x6E3A)))
            check(not keySeen,tag..' kill drops no boss key')
            check(r(0xB6+slot)==0,string.format('%s Wizzrobe slot cleared ($B6=%d)',tag,r(0xB6+slot)))
            if kills==1 then
                dying=false;revived=false
                spawn(slot)
            else
                finish()
            end
        end
    end
    if age>1500 then
        check(false,'timed out waiting for Wizzrobe kill '..(kills+1))
        finish()
    end
end,emu.eventType.endFrame)
