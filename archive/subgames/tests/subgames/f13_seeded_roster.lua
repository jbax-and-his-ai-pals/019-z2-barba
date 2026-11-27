-- Verify seeded Barba roster randomization across separate Zelda II -> F13 portal runs,
-- keeping Slot 0 as OG Barba and syncing map portraits, HUD portraits, and exterior palettes.
dofile(TEST_DIR .. '/newgame.lua')
local mem = emu.memType.nesMemory
local oam = emu.memType.nesSpriteRam
local pal = emu.memType.nesPaletteRam
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end

local report = assert(io.open(OUTPUT_DIR .. '/f13-seeded-roster.txt', 'w'))
local errors = 0
local done = false
local function check(cond, msg)
    report:write((cond and 'PASS ' or 'FAIL ') .. msg .. '\n')
    if not cond then errors = errors + 1 end
end
local function finish()
    if done then return end
    done = true
    report:write(errors == 0 and 'RESULT PASS\n' or 'RESULT FAIL\n')
    report:close()
    emu.stop(errors == 0 and 0 or 1)
end

local frame = 0
local runIdx = 1
local phase = 'setup'
local phaseStart = 0
local snapshots = {}

local function warpToRuto()
    write(0x707, 1); write(0x706, 0); write(0x056B, 1); write(0x769, 3); write(0x561, 5)
    write(0x701, 0); write(0x75C, 0); write(0x704, 0); write(0x736, 0)
    write(0x73D, 0); write(0x726, 1)
end

local function readRoster()
    local desc = {}
    for i = 0x7CA0, 0x7CAF do table.insert(desc, string.format('%02X', read(i))) end
    local pal0, pal1, pal2, pal3 = {}, {}, {}, {}
    for i = 0, 3 do
        table.insert(pal0, string.format('%02X', emu.read(16 + i, pal)))
        table.insert(pal1, string.format('%02X', emu.read(20 + i, pal)))
        table.insert(pal2, string.format('%02X', emu.read(24 + i, pal)))
        table.insert(pal3, string.format('%02X', emu.read(28 + i, pal)))
    end
    local hud = {}
    for i = 0x7CB0, 0x7CB5 do table.insert(hud, string.format('%02X', read(i))) end
    return {
        desc = table.concat(desc, ''),
        pal0 = table.concat(pal0, ''),
        pal1 = table.concat(pal1, ''),
        pal2 = table.concat(pal2, ''),
        pal3 = table.concat(pal3, ''),
        hud  = table.concat(hud, ''),
    }
end

emu.addEventCallback(function()
    if phase == 'setup' then
        if frame < 1000 then
            emu.setInput(newGameInput(frame), 0)
        elseif frame >= 1100 and (read(0x3B) ~= 0 or read(0x4D) < 0x94) then
            emu.setInput({right = true}, 0)
        else
            emu.setInput({}, 0)
        end
    elseif phase == 'enter' then
        local ef = frame - phaseStart
        emu.setInput({up = (ef >= 10 and ef < 15), b = (ef >= 250 and ef < 254)}, 0)
    elseif phase == 'f13_to_map' then
        local ff = frame - phaseStart
        local onMap = (emu.read(21, pal) == 0x16 and emu.read(26, pal) == 0x35)
        emu.setInput({start = (not onMap) and ((ff >= 380 and ff < 385) or (ff >= 460 and ff < 465))}, 0)
    elseif phase == 'f13_select_alt' then
        local ff = frame - phaseStart
        -- Move cursor right twice to BORBA (slot 2), then Start into exterior!
        emu.setInput({
            right = (ff >= 10 and ff < 14) or (ff >= 25 and ff < 29),
            start = (ff >= 45 and ff < 50),
        }, 0)
    elseif phase == 'f13_return' then
        emu.setInput({start = true, select = true}, 0)
    elseif phase == 'z2_wait_return' then
        local rf = frame - phaseStart
        emu.setInput({b = (rf >= 250 and rf < 254)}, 0)
    else
        emu.setInput({}, 0)
    end
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if done then return end
    frame = frame + 1
    if phase == 'setup' then
        if frame == 1000 then
            warpToRuto()
        elseif frame > 1100 and read(0x3B) == 0 and read(0x4D) >= 0x94 then
            for slot = 0, 5 do write(0xB6 + slot, 0) end
            write(0x4D, 0x95); write(0x70, 0)
            phase = 'enter'; phaseStart = frame
        end
    elseif phase == 'enter' then
        local ef = frame - phaseStart
        if ef > 250 and read(0xFFFA) == 0x40 and read(0xFFFB) == 0x78 then
            phase = 'f13_to_map'; phaseStart = frame
        elseif ef > 400 then
            check(false, 'Run ' .. runIdx .. ': timed out entering F13'); finish()
        end
    elseif phase == 'f13_to_map' then
        local ff = frame - phaseStart
        if ff == 520 then
            local snap = readRoster()
            snapshots[runIdx] = snap
            report:write(string.format('Run %d: desc=%s pal0=%s pal1=%s pal2=%s pal3=%s hud=%s\n',
                runIdx, snap.desc, snap.pal0, snap.pal1, snap.pal2, snap.pal3, snap.hud))
            check(read(0x7CA0) == 0x00 and read(0x7CA3) == 0x01, 'Run ' .. runIdx .. ': Slot 0 BARBA stays OG ($00, pal 1)')
            check(snap.pal1 == '0F162730', 'Run ' .. runIdx .. ': Map Sprite Pal 1 is OG Barba ($0F/$16/$27/$30)')
            check(snap.pal2 == '0F163527', 'Run ' .. runIdx .. ': Map Sprite Pal 2 preserved for Laura/Debbie/Child ($0F/$16/$35/$27)')
            check((emu.read(44 * 4 + 2, oam) & 3) == 2, 'Run ' .. runIdx .. ': Child icon uses Sprite Pal 2')
            local png = emu.takeScreenshot()
            local pf = assert(io.open(OUTPUT_DIR .. '/f13-seed-run' .. runIdx .. '.png', 'wb'))
            pf:write(png); pf:close()
            if runIdx == 1 then
                phase = 'f13_return'; phaseStart = frame
            else
                check(snapshots[1].desc ~= snapshots[2].desc or snapshots[1].pal0 ~= snapshots[2].pal0 or snapshots[1].pal3 ~= snapshots[2].pal3,
                    'Different Zelda II portal runs generated different Barba rosters')
                phase = 'f13_select_alt'; phaseStart = frame
            end
        end
    elseif phase == 'f13_return' then
        if read(0xFFFA) ~= 0x40 or read(0xFFFB) ~= 0x78 then
            phase = 'z2_wait_return'; phaseStart = frame
        elseif frame - phaseStart > 300 then
            check(false, 'Timed out returning from F13'); finish()
        end
    elseif phase == 'z2_wait_return' then
        local rf = frame - phaseStart
        if rf == 270 then
            -- Advance Z2 RNG slightly and re-enter Ruto door for Run 2
            write(0x051A, (read(0x051A) + 0x37) & 0xFF)
            write(0x051B, (read(0x051B) + 0x5D) & 0xFF)
            runIdx = 2
            phase = 'enter'; phaseStart = frame
        end
    elseif phase == 'f13_select_alt' then
        local ff = frame - phaseStart
        if ff == 420 then
            local slot = read(0x0507)
            local extp = {}
            for i = 0, 3 do table.insert(extp, string.format('%02X', emu.read(24 + i, pal))) end
            local wrp = {}
            for i = 0, 3 do table.insert(wrp, string.format('%02X', read(0x7CC0 + slot * 4 + i))) end
            report:write(string.format('Ext slot=%d ppuPal2=%s wramExt=%s\n', slot, table.concat(extp,''), table.concat(wrp,'')))
            check(slot == 2, 'Selected BORBA (slot 2) on map screen (' .. slot .. ')')
            local hudTile = emu.read(1 * 4 + 1, oam)
            local expectedHud = read(0x7CB0 + slot)
            check(hudTile == expectedHud, string.format('HUD portrait tile matches rolled slot (%02X == %02X)', hudTile, expectedHud))
            check(emu.read(31, pal) == 0x0F, 'Exterior Sprite Pal 3 color 3 stays $0F (Sprite 0 invisible)')
            local png = emu.takeScreenshot()
            local pf = assert(io.open(OUTPUT_DIR .. '/f13-seed-run2-ext.png', 'wb'))
            pf:write(png); pf:close()
            finish()
        end
    end
end, emu.eventType.endFrame)
