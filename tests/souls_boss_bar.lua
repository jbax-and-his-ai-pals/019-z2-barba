-- Dark Souls bottom boss health bar regression (build with --boss-meter souls).
dofile(TEST_DIR..'/newgame.lua')
local mem = emu.memType.nesMemory
local ppu = emu.memType.nesPpuMemory
local function r(a) return emu.read(a, mem) end
local function readFile(path)
    local f = assert(io.open(path, 'rb'))
    local d = f:read('*a')
    f:close()
    return d
end

local digest = assert(readFile(OUTPUT_DIR..'/build-report.json'):match('"output_sha256"%s*:%s*"(%x+)"'))
local pack = OUTPUT_DIR..'/test-pack/'..digest:sub(1,12)..'/bosses/'
local cases = {
    {name='horsehead', target=390},
    {name='gooma', target=430},
    {name='dark-link', target=405},
}
local out = assert(io.open(OUTPUT_DIR..'/souls_boss_bar.txt', 'w'))
local idx, age, errors = 0, 0, 0
local pending = true
local sawActive, sawHit, sawWhiteDrain = false, false, false

local function check(ok, msg)
    out:write((ok and 'PASS ' or 'FAIL ')..msg..'\n')
    if not ok then errors = errors + 1 end
end

emu.addMemoryCallback(function()
    if not pending then return end
    pending = false
    idx = idx + 1
    local c = cases[idx]
    if not c then
        out:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
        out:close()
        stopScenario(errors==0 and 0 or 1)
        return
    end
    assert(emu.loadSavestate(readFile(pack..'boss-'..c.name..'.mss')), c.name)
    age, sawActive, sawHit, sawWhiteDrain = 0, false, false, false
end, emu.callbackType.exec, 0xC07B)

emu.addEventCallback(function()
    local c = cases[idx]
    if not c then return end
    local x = r(0x3B)*256 + r(0x4D)
    emu.setInput({
        right = x < c.target,
        left = x > c.target + 16,
        a = age > 260 and age % 40 < 20,
        b = age > 260 and age % 10 < 3,
    }, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    local c = cases[idx]
    if not c then return end
    age = age + 1
    local active = r(0x6352)
    local red = r(0x6355)
    local wht = r(0x6356)
    if active == 1 then
        if not sawActive and r(0x64D7) >= 2 then
            sawActive = true
            -- Verify left-cap $92 at $2423 and no left-side OAM pips at X=$10.
            check(emu.read(0x2423, ppu) == 0x92, c.name..' bottom bar left cap in $2423')
        end
        if wht > red and not sawHit then
            sawHit = true
        elseif sawHit and wht == red and not sawWhiteDrain then
            sawWhiteDrain = true
        end
    end
    if age >= 450 or (sawWhiteDrain and age > 250) then
        check(sawActive, c.name..' bar became active')
        check(sawHit, c.name..' white hit-flash triggered')
        check(sawWhiteDrain, c.name..' white chunk drained right-to-left')
        pending = true
    end
end, emu.eventType.endFrame)
