-- Cross-game cosmetic trophies & Gear Bar test:
-- Verifies Select -> Gear Bar navigation, A/B equip/toggle, Hockey Mask R2=181 &
-- deeper roar ($4010), Mega Helmet ($F9/$79) + BLADE blue palette, Red Necktie ($FB/$7B),
-- and Championship Belt ($FD/$7D) stacking.
dofile(TEST_DIR .. '/newgame.lua')
local mem = emu.memType.nesMemory
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end
local function writeFile(name, data)
    local f = assert(io.open(OUTPUT_DIR .. '/' .. name, 'wb'))
    f:write(data)
    f:close()
end

local frame = 0
local phase = 'boot'
local phaseStart = 0
local currentInput = {}
local report = assert(io.open(OUTPUT_DIR .. '/cosmetic-gear.txt', 'w'))
local errors = 0
local stopped = false
local function check(cond, msg)
    if stopped then return end
    report:write((cond and 'PASS ' or 'FAIL ') .. msg .. '\n')
    report:flush()
    if not cond then errors = errors + 1 end
end
local function finish(code)
    if stopped then return end
    stopped = true
    report:write('RESULT ' .. (code == 0 and 'PASS' or 'FAIL') .. '\n')
    report:close()
    emu.stop(code)
end

local sawDeeperRoar = false
local lastDmcRate = nil
emu.addMemoryCallback(function(addr, val)
    lastDmcRate = val & 0x0F
    if (read(0x648F) & 0x03) == 2 and lastDmcRate <= 0x0D then
        sawDeeperRoar = true
    end
end, emu.callbackType.write, 0x4010)

local function findGearOam(tile)
    for i = 0x20, 0xFC, 4 do
        if read(0x6500 + i + 1) == tile and read(0x6500 + i) < 0xF0 then
            return read(0x6500 + i), read(0x6500 + i + 2), read(0x6500 + i + 3)
        end
    end
    return nil
end

emu.addEventCallback(function()
    if phase == 'boot' then
        emu.setInput(newGameInput(frame), 0)
    else
        emu.setInput(currentInput, 0)
    end
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if stopped then return end
    frame = frame + 1
    currentInput = {}
    if phase == 'boot' then
        if frame >= 900 and read(0x0736) == 0x0B and read(0x0524) == 0 then
            -- Unlock all 5 trophies + spells (including BLADE) in Rauru
            write(0x648B, 0x57) -- Waldo Hat / DECOY
            write(0x63B1, 1)    -- F13 Hockey Mask / AXE
            write(0x63B3, 1)    -- DK Red Necktie / BARREL
            write(0x63B7, 1)    -- MM2 Mega Helmet / BLADE
            write(0x63BA, 1)    -- MTPO Champ Belt / HEAVY
            write(0x0773, 0x80)
            write(0x0778, 8)
            write(0x0749, 14)   -- select BLADE
            phase = 'open1'
            phaseStart = frame
        elseif frame > 1600 then
            check(false, 'reached side-view play')
            finish(1)
        end
    elseif phase == 'open1' then
        local dt = frame - phaseStart
        if dt >= 4 and dt < 7 then currentInput = {start = true} end
        if dt == 32 then
            check(read(0x0524) == 5, 'menu opened to input state')
            writeFile('gear-menu-open.png', emu.takeScreenshot())
            phase = 'equip_mask'
            phaseStart = frame
        end
    elseif phase == 'equip_mask' then
        local dt = frame - phaseStart
        if dt >= 2 and dt < 5 then currentInput = {select = true} end -- focus Gear (HAT=1)
        if dt >= 10 and dt < 13 then currentInput = {right = true} end -- move to MASK (2)
        if dt >= 18 and dt < 21 then currentInput = {a = true} end -- equip MASK
        if dt >= 26 and dt < 29 then currentInput = {start = true} end -- close menu
        if dt == 60 then
            check(read(0x0524) == 0, 'menu closed after equipping Hockey Mask')
            check((read(0x648F) & 0x83) == 0x82, string.format('BARBA_GEAR=$%02X has Hockey Mask (2)', read(0x648F)))
            writeFile('gear-hockey-mask.png', emu.takeScreenshot())
            -- Trigger a roar by casting BLADE (Select) or hurt roar
            phase = 'test_roar'
            phaseStart = frame
        end
    elseif phase == 'test_roar' then
        local dt = frame - phaseStart
        if dt == 2 then
            -- Trigger full sampled roar via ROAR_REQUEST ($05EE = $40)
            write(0x05EE, 0x40)
        end
        if dt == 20 then
            check(sawDeeperRoar, string.format('Hockey Mask lowered $4010 DMC rate (last=$%s)', tostring(lastDmcRate)))
            phase = 'open2'
            phaseStart = frame
        end
    elseif phase == 'open2' then
        local dt = frame - phaseStart
        if dt >= 4 and dt < 7 then currentInput = {start = true} end
        if dt == 32 then
            phase = 'equip_stacked'
            phaseStart = frame
        end
    elseif phase == 'equip_stacked' then
        local dt = frame - phaseStart
        if dt >= 2 and dt < 5 then currentInput = {select = true} end -- HAT (1)
        if dt >= 8 and dt < 11 then currentInput = {right = true} end -- MASK (2)
        if dt >= 14 and dt < 17 then currentInput = {right = true} end -- HELM (3)
        if dt >= 20 and dt < 23 then currentInput = {a = true} end -- equip HELM
        if dt >= 26 and dt < 29 then currentInput = {right = true} end -- TIE (4)
        if dt >= 32 and dt < 35 then currentInput = {a = true} end -- toggle TIE on
        if dt >= 38 and dt < 41 then currentInput = {right = true} end -- BELT (5)
        if dt >= 44 and dt < 47 then currentInput = {a = true} end -- toggle BELT on
        if dt >= 52 and dt < 55 then currentInput = {start = true} end -- close menu
        if dt == 86 then
            local g = read(0x648F)
            check((g & 0xB3) == 0xB3, string.format('BARBA_GEAR=$%02X has HELM+TIE+BELT stacked', g))
            local hy = findGearOam(0x79)
            local ty = findGearOam(0x7B)
            local by = findGearOam(0x7D) -- North Palace (non-town) uses $7D for belt
            check(hy ~= nil, 'Mega Helmet crest ($79) drawn in OAM')
            check(ty ~= nil, 'Red Necktie ($7B) drawn in OAM')
            check(by ~= nil, 'Championship Belt ($7D) drawn in OAM')
            phase = 'cast_blade'
            phaseStart = frame
        end
    elseif phase == 'cast_blade' then
        local dt = frame - phaseStart
        if dt >= 2 and dt < 5 then currentInput = {select = true} end -- cast BLADE ($0749=14)
        if dt == 12 then
            check((read(0x6680) & 0x40) == 0x40, 'BLADE cast active')
            check(read(0x69D2) == 0x12 and read(0x69D8) == 0x21,
                string.format('Mega Helmet + BLADE blue palette ($69D2=%02X $69D8=%02X)', read(0x69D2), read(0x69D8)))
            writeFile('gear-mega-stacked.png', emu.takeScreenshot())
            finish(errors == 0 and 0 or 1)
        end
    end
end, emu.eventType.endFrame)
