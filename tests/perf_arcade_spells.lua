-- Crowded-room performance probe for all 10 Arcade spells and the ArcadeSpellHook0/ArcadeTick2 bitmask early-out.
-- Requires the current-hash 'busy' test pack (create_test_pack.py --set busy).
-- python tools/emulator_test.py tests/perf_arcade_spells.lua
dofile(TEST_DIR..'/newgame.lua')
local mem = emu.memType.nesMemory
local function r(a) return emu.read(a, mem) end
local function w(a, v) emu.write(a, v, mem) end
local function readFile(path)
    local f = assert(io.open(path, 'rb'))
    local d = f:read('*a')
    f:close()
    return d
end

local NL = string.char(10)
local digest = assert(readFile(OUTPUT_DIR..'/build-report.json'):match('"output_sha256"%s*:%s*"(%x+)"'))
local pack = OUTPUT_DIR..'/test-pack/'..digest:sub(1, 12)..'/busy/'
local report = assert(io.open(OUTPUT_DIR..'/perf-arcade-spells.txt', 'w'))

local function initTimedPos(tmrAddr, xloAddr, xhiAddr, yAddr, tmrVal)
    w(tmrAddr, tmrVal)
    w(xloAddr, r(0x4D))
    w(xhiAddr, r(0x3B))
    w(yAddr, r(0x29))
end

local CASES = {
    {name='p2-idle',      state='p2-crowded-floor', lo=0x00, hi=0x00, expectTicks=false},
    {name='p2-passive',   state='p2-crowded-floor', lo=0x84, hi=0x02, expectTicks=false, init=function() w(0x6683, 3) end},
    {name='p2-decoy',     state='p2-crowded-floor', lo=0x01, hi=0x00, expectTicks=true,
        init=function() initTimedPos(0x6684, 0x6685, 0x6686, 0x6687, 150) end},
    {name='p2-axe',       state='p2-crowded-floor', lo=0x02, hi=0x00, expectTicks=true,
        init=function() initTimedPos(0x6690, 0x6691, 0x6692, 0x6693, 120); w(0x6694, 3); w(0x6695, 0xFC) end},
    {name='p2-double',    state='p2-crowded-floor', lo=0x04, hi=0x00, expectTicks=false},
    {name='p2-barrel',    state='p2-crowded-floor', lo=0x08, hi=0x00, expectTicks=true,
        init=function() initTimedPos(0x6688, 0x6689, 0x668A, 0x668B, 120); w(0x668C, 2); w(0x668D, 0) end},
    {name='p2-star',      state='p2-crowded-floor', lo=0x10, hi=0x00, expectTicks=true, init=function() w(0x668F, 150) end},
    {name='p2-lock',      state='p2-crowded-floor', lo=0x20, hi=0x00, expectTicks=true, init=function() w(0x668E, 0) end},
    {name='p2-blade',     state='p2-crowded-floor', lo=0x40, hi=0x00, expectTicks=true},
    {name='p2-lucky',     state='p2-crowded-floor', lo=0x80, hi=0x00, expectTicks=false, init=function() w(0x6683, 3) end},
    {name='p2-clock',     state='p2-crowded-floor', lo=0x00, hi=0x01, expectTicks=true, init=function() w(0x6682, 150) end},
    {name='p2-heavy',     state='p2-crowded-floor', lo=0x00, hi=0x02, expectTicks=false},
    {name='p5-idle',      state='p5-gooma-approach', lo=0x00, hi=0x00, expectTicks=false},
    {name='p5-passive',   state='p5-gooma-approach', lo=0x84, hi=0x02, expectTicks=false, init=function() w(0x6683, 3) end},
    {name='p5-barrel',    state='p5-gooma-approach', lo=0x08, hi=0x00, expectTicks=true,
        init=function() initTimedPos(0x6688, 0x6689, 0x668A, 0x668B, 120); w(0x668C, 2); w(0x668D, 0) end},
    {name='p5-clock',     state='p5-gooma-approach', lo=0x00, hi=0x01, expectTicks=true, init=function() w(0x6682, 150) end},
}

local FRAMES_PER_CASE = 110
local idx, age, frame, pending = 0, 0, 0, false
local cur = nil
local nmis, nmiStart, nmiSideView = 0, nil, false
local sel, R6 = 0, 0
local failures = 0

local function cycles() return emu.getState()['cpu.cycleCount'] end
local function gateOn() return r(0x736) == 0x0B and r(0x74C) < 2 and r(0x726) == 0 end

emu.addMemoryCallback(function(a, v)
    if (a & 1) == 0 then
        sel = v & 7
    elseif sel == 6 then
        R6 = v
    end
end, emu.callbackType.write, 0x8000, 0x9FFF)

emu.addMemoryCallback(function()
    if pending then
        pending = false
        if cur then
            local avg = cur.nmiCount > 0 and math.floor(cur.nmiSum / cur.nmiCount) or 0
            local ok = (cur.lag == 0) and (cur.hudBad == 0) and (cur.late == 0)
                and (cur.spec.expectTicks and (cur.tickHits > 0) or (not cur.spec.expectTicks and cur.tickHits == 0))
            if not ok then failures = failures + 1 end
            report:write(string.format('%s %-14s frames=%d lag=%d late=%d hudBad=%d nmiAvg=%d nmiMax=%d tickHits=%d'..NL,
                ok and 'PASS' or 'FAIL', cur.spec.name, cur.frames, cur.lag, cur.late, cur.hudBad, avg, cur.nmiMax, cur.tickHits))
            report:flush()
        end
        idx = idx + 1
        local spec = CASES[idx]
        if not spec then
            report:write('RESULT '..(failures == 0 and 'PASS' or 'FAIL')..NL)
            report:close()
            stopScenario(failures == 0 and 0 or 1)
            return
        end
        local f = assert(io.open(pack..spec.state..'.mss', 'rb'))
        assert(emu.loadSavestate(f:read('*a')), spec.state..' loads')
        f:close()
        cur = {spec=spec, frames=0, lag=0, late=0, hudBad=0, nmiMax=0, nmiSum=0, nmiCount=0, tickHits=0}
        age = 0
        nmis = 0
        nmiStart = nil
        local s = emu.getState()
        R6 = s['mapper.mmc3Registers6'] or 0
        return
    end
    nmiStart = cycles()
    nmis = nmis + 1
    nmiSideView = gateOn()
end, emu.callbackType.exec, 0xC07B)

local nmiRti = LABELS.NmiRti or 0xC1B2
emu.addMemoryCallback(function()
    if nmiStart and cur and age > 20 and nmiSideView and gateOn() then
        local c = cycles() - nmiStart
        cur.nmiSum = cur.nmiSum + c
        cur.nmiCount = cur.nmiCount + 1
        if c > cur.nmiMax then cur.nmiMax = c end
    end
    nmiStart = nil
end, emu.callbackType.exec, nmiRti)

if LABELS.VblankOverrun6 then
    emu.addMemoryCallback(function()
        if cur and age > 20 and nmiSideView and gateOn() and (R6 >> 1) == 6 then
            cur.late = cur.late + 1
        end
    end, emu.callbackType.exec, LABELS.VblankOverrun6)
end

if LABELS.ArcadeTick2 then
    emu.addMemoryCallback(function()
        if cur and age > 20 and (R6 >> 1) == 1 then
            cur.tickHits = cur.tickHits + 1
        end
    end, emu.callbackType.exec, LABELS.ArcadeTick2)
end

emu.addEventCallback(function()
    if not cur or age <= 20 or not gateOn() then return end
    local s = emu.getState()
    if (s['ppu.tmpVideoRamAddr'] & 0x041F) ~= 0 or s['ppu.xScroll'] ~= 0 then
        cur.hudBad = cur.hudBad + 1
    end
end, emu.eventType.startFrame)

emu.addEventCallback(function()
    local b = {start=false, select=false, a=false, b=false, up=false, down=false, left=false, right=false}
    if cur and age > 20 then
        local t = age % 120
        b.right = t < 80
        b.left = t >= 80
        b.b = (age % 6) < 2
        b.a = (age % 45) < 10
    end
    emu.setInput(b, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame = frame + 1
    if idx == 0 then
        if frame == 30 then pending = true end
        return
    end
    age = age + 1
    if age == 20 and cur then
        w(0x774, 255)
        w(0x773, 255)
        w(0x6680, cur.spec.lo)
        w(0x6681, cur.spec.hi)
        if cur.spec.init then cur.spec.init() end
    elseif age > 20 and cur and r(0x736) == 0x0B then
        w(0x774, 255)
        w(0x773, 255)
        cur.frames = cur.frames + 1
        if nmis == 0 then cur.lag = cur.lag + 1 end
    end
    nmis = 0
    if age == FRAMES_PER_CASE then pending = true end
end, emu.eventType.endFrame)
