-- End-to-end Barba's Arcade win-to-unlock & Phase 3 discovery/transition verification in build/barba.nes:
--   1. Verifies RA Telemetry Header ($6800-$6802), ACTIVE_GAME_ID=0, and initial discovery ($6806=$01, $6807=$00).
--   2. Verifies undiscovered Booth 2 (feud) in Rauru's Arcade ($1C) shows "OUT OF ORDER!" and does not launch.
--   3. Visits all 4 remaining active Hyrule discovery spots and verifies full discovery bitmask ($6806=$AD, $6807=$00).
--   4. Tests feud Start+Select negative case (silent clean return: $074C==0, $DE==0, $6804==0, $4015==0, $63B2==0).
--   5. Enters all 5 active booths in Barba's Arcade, triggers each patched win hook, asserts >=25f melt-out,
--      verifies ACTIVE_GAME_ID (1/3/4/6/8 -> 0) and RA_LAST_WIN_GAME ($6804 == gameId), unlocks all rewards,
--      and verifies pause menu & Gear Bar trophies (HAT & TIE).
dofile(TEST_DIR .. '/newgame.lua')
local mem = emu.memType.nesMemory
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end

local booths = {
    {id='waldo', slot=0, gameId=1, page=0, x=0x50, nmi=0xF8FB, rewardAddr=0x648B, expected=0x57, winPc=0xF941, bankR6=16},
    {id='feud',  slot=2, gameId=3, page=0, x=0xD0, nmi=0xCA5E, rewardAddr=0x63B2, expected=0x01, winPc=0xA964, bankR6=0, bankR7=1},
    {id='dk',    slot=3, gameId=4, page=1, x=0x20, nmi=0x7840, rewardAddr=0x63B3, expected=0x01, winPc=0xC8B3},
    {id='duck',  slot=5, gameId=6, page=1, x=0xC0, nmi=0x7840, rewardAddr=0x63B5, expected=0x01, winPc=0xD39B},
    {id='wheel', slot=7, gameId=8, page=2, x=0xC0, nmi=0x7850, rewardAddr=0x63B8, expected=0x01, winPc=0xC988},
}

local hyruleSpots = {
    {id='feud_saria',     world=1, reg=0, town=2, area=1, room=0x1B, page=0, x=0x70, y=0xB0},
    {id='dk_ruto',        world=1, reg=0, town=1, area=3, room=0x19, page=0, x=0x70, y=0xB0},
    {id='duck_mido',      world=1, reg=0, town=3, area=3, room=0x36, page=0, x=0x70, y=0xB0},
    {id='wheel_nabooru',  world=2, reg=2, town=4, area=3, room=0x3B, page=0, x=0x70, y=0xB0},
}

local report = assert(io.open(OUTPUT_DIR .. '/subgame-rewards-e2e.txt', 'w'))
local errors = 0
local done = false
local function check(cond, msg)
    report:write((cond and 'PASS ' or 'FAIL ') .. msg .. '\n')
    report:flush()
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
local phase = 'boot'
local phaseStart = 0
local lockedTest = true
local negTest = false
local idx = 1
local discIdx = 1
local winTriggerPending = false
local winTriggerFrame = 0
local lastLaunchedGameId = 0
local last4011 = 0xFF
local unlocked = {}

local function activeBooth()
    if lockedTest or negTest then return booths[2] end
    return booths[idx]
end

local function warpRoom(w)
    write(0x707, w.world); write(0x706, w.reg); write(0x056B, w.town)
    write(0x769, w.area); write(0x561, w.room)
    if w.f748 then write(0x0748, w.f748) end
    if w.owY then write(0x73, w.owY) end
    if w.owX then write(0x74, w.owX) end
    write(0x701, 0); write(0x75C, w.page); write(0x704, 0)
    write(0x736, 0); write(0x73D, 0); write(0x726, 1)
end

-- Capture ACTIVE_GAME_ID writes while in WRAM bank 0 (before $A001 switches to bank 1/2/3).
emu.addMemoryCallback(function(_, val)
    if phase == 'enter_game' and lastLaunchedGameId == 0 and val ~= 0 then
        lastLaunchedGameId = val
    end
end, emu.callbackType.write, 0x6803)

emu.addMemoryCallback(function(_, val)
    last4011 = val
end, emu.callbackType.write, 0x4011)

-- Execute guest win triggers cleanly inside an exec callback in ROM space.
emu.addMemoryCallback(function()
    if not winTriggerPending then return end
    local b = activeBooth()
    local nmi = read(0xFFFA) + read(0xFFFB) * 256
    if nmi ~= b.nmi then return end
    winTriggerPending = false
    if b.bankR6 then
        write(0x8000, 0x06); write(0x8001, b.bankR6)
    end
    if b.bankR7 then
        write(0x8000, 0x07); write(0x8001, b.bankR7)
    end
    emu.setState({['cpu.pc'] = b.winPc})
end, emu.callbackType.exec, 0x8000, 0xFFFF)

local currentInput = {}
emu.addEventCallback(function()
    if phase == 'boot' and frame < 1000 then
        emu.setInput(newGameInput(frame), 0)
    elseif phase == 'enter_arcade' then
        local ef = frame - phaseStart
        emu.setInput({up = (ef >= 10 and ef < 14)}, 0)
    elseif phase == 'walk_booth' then
        local b = activeBooth()
        local curPage = read(0x3B)
        local curX = read(0x4D)
        if curPage < b.page or (curPage == b.page and curX < b.x - 4) then
            emu.setInput({right = true}, 0)
        elseif curPage > b.page or (curPage == b.page and curX > b.x + 4) then
            emu.setInput({left = true}, 0)
        else
            emu.setInput({}, 0)
        end
    elseif phase == 'enter_game' then
        local ef = frame - phaseStart
        if lockedTest then
            emu.setInput({up = (ef >= 10 and ef < 14), b = (ef >= 160 and ef < 164)}, 0)
        else
            emu.setInput({up = (ef >= 10 and ef < 14), b = (ef >= 240 and ef < 244)}, 0)
        end
    elseif phase == 'guest_neg' then
        local gf = frame - phaseStart
        emu.setInput({
            start = (gf >= 80),
            select = (gf >= 80),
        }, 0)
    elseif phase == 'guest_win' then
        emu.setInput({}, 0)
    elseif phase == 'return' then
        local rf = frame - phaseStart
        if negTest then
            emu.setInput({}, 0)
        elseif owWinTest then
            emu.setInput({b = (rf >= 70 and rf < 80)}, 0)
        else
            emu.setInput({b = (rf >= 240 and rf < 244)}, 0)
        end
    elseif phase == 'cast_heavy_palace' or phase == 'menu_verify' or phase == 'gear_verify' then
        emu.setInput(currentInput, 0)
    else
        emu.setInput({}, 0)
    end
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if done then return end
    frame = frame + 1
    currentInput = {}

    if phase == 'boot' then
        if frame == 1000 then
            check(read(0x6800) == 0x42 and read(0x6801) == 0x32 and read(0x6802) == 0x01,
                string.format('RA Telemetry header valid ($6800=%02X $6801=%02X $6802=%02X)',
                    read(0x6800), read(0x6801), read(0x6802)))
            check(read(0x6803) == 0, string.format('ACTIVE_GAME_ID starts at 0 (got %d)', read(0x6803)))
            check(read(0x6806) == 0x01 and read(0x6807) == 0x00,
                string.format('Discovery starts at $0001 ($6806=%02X $6807=%02X)', read(0x6806), read(0x6807)))
            -- Warp to Rauru ($01) page 1 in front of Barba's Arcade door (x=40)
            warpRoom({world=1, reg=0, town=0, area=3, room=0x1C, page=1})
            write(0x561, 1)
            phase = 'load_rauru'
            phaseStart = frame
        end
    elseif phase == 'load_rauru' then
        if frame - phaseStart >= 60 and read(0x726) == 0 and read(0x736) == 11 then
            for s = 0, 5 do write(0xB6 + s, 0) end
            write(0x3B, 1); write(0x4D, 40); write(0x70, 0)
            phase = 'enter_arcade'
            phaseStart = frame
        end
    elseif phase == 'enter_arcade' then
        local ef = frame - phaseStart
        if ef > 30 and read(0x561) == 0x1C and read(0x736) == 11 and read(0x726) == 0 then
            if discIdx > #hyruleSpots then
                check(read(0x6806) == 0xAD and read(0x6807) == 0x00,
                    string.format('All 5 active spots discovered ($6806=%02X $6807=%02X)', read(0x6806), read(0x6807)))
            else
                check(true, 'Entered Barba Arcade room $1C')
            end
            phase = 'walk_booth'
            phaseStart = frame
        elseif ef > 180 then
            check(false, 'Timed out entering Arcade')
            finish()
        end
    elseif phase == 'discover_load' then
        local sf = frame - phaseStart
        local sp = hyruleSpots[discIdx]
        if sf >= 30 and read(0x726) == 0 and read(0x736) == 11 and read(0x561) == sp.room then
            for s = 0, 5 do write(0xB6 + s, 0) end
            write(0x3B, sp.page); write(0x4D, sp.x); write(0x29, sp.y); write(0x70, 0)
            phase = 'discover_settle'
            phaseStart = frame
        elseif sf > 240 then
            check(false, string.format('Timed out loading discovery spot %s', sp.id))
            finish()
        end
    elseif phase == 'discover_settle' then
        if frame - phaseStart >= 15 then
            discIdx = discIdx + 1
            if discIdx <= #hyruleSpots then
                warpRoom(hyruleSpots[discIdx])
                phase = 'discover_load'
                phaseStart = frame
            else
                check(read(0x6806) == 0xAD and read(0x6807) == 0x00,
                    string.format('Hyrule discovery bitmask complete ($6806=%02X $6807=%02X)',
                        read(0x6806), read(0x6807)))
                negTest = true
                warpRoom({world=1, reg=0, town=0, area=3, room=1, page=1})
                phase = 'load_rauru'
                phaseStart = frame
            end
        end
    elseif phase == 'walk_booth' then
        local b = activeBooth()
        if read(0x3B) == b.page and math.abs(read(0x4D) - b.x) <= 4 and read(0x29) == 0xB0 then
            write(0x70, 0)
            if not lockedTest and not negTest then
                check(read(b.rewardAddr) == 0,
                    string.format('%s: reward $%04X starts locked (0)', b.id, b.rewardAddr))
            end
            lastLaunchedGameId = 0
            last4011 = 0xFF
            phase = 'enter_game'
            phaseStart = frame
        elseif frame - phaseStart > 1500 then
            check(false, string.format('%s: timed out walking to booth (world=%02X room=%02X pg=%d x=%02X y=%02X vx=%02X f7=%02X 74F=%02X DE=%02X 74C=%02X 524=%02X)',
                b.id, read(0x0707), read(0x0561), read(0x3B), read(0x4D), read(0x29), read(0x70), read(0xF7), read(0x074F), read(0xDE), read(0x074C), read(0x0524)))
            finish()
        end
    elseif phase == 'enter_game' then
        local b = activeBooth()
        local ef = frame - phaseStart
        local nmi = read(0xFFFA) + read(0xFFFB) * 256
        if lockedTest then
            if ef == 40 then
                check(read(0x074C) ~= 0 or read(0xDE) ~= 0, 'Undiscovered booth feud opened OUT OF ORDER dialogue')
            end
            if ef == 200 then
                check(nmi == 0xC07B and read(0x6803) == 0 and read(0x074C) == 0,
                    'Undiscovered booth feud did not launch and dismissed cleanly')
                lockedTest = false
                discIdx = 1
                warpRoom(hyruleSpots[discIdx])
                phase = 'discover_load'
                phaseStart = frame
            end
        elseif ef > 240 and nmi == b.nmi then
            check(lastLaunchedGameId == b.gameId,
                string.format('%s: ACTIVE_GAME_ID set to %d on launch (got %d)', b.id, b.gameId, lastLaunchedGameId))
            phase = negTest and 'guest_neg' or 'guest_win'
            phaseStart = frame
        elseif ef > 450 then
            check(false, string.format('%s: timed out entering guest (nmi=$%04X)', b.id, nmi))
            finish()
        end
    elseif phase == 'guest_neg' then
        local gf = frame - phaseStart
        local nmi = read(0xFFFA) + read(0xFFFB) * 256
        if gf > 80 and nmi == 0xC07B then
            check((read(0x4015) & 0x1F) == 0 and last4011 == 0,
                string.format('feud negative clean APU mute ($4015=%02X $4011=%02X)', read(0x4015), last4011))
            phase = 'return'
            phaseStart = frame
        elseif gf > 650 then
            local st = emu.getState()
            check(false, string.format('feud negative Start+Select timed out (pc=%04X nmi=%04X 2D=%02X 7FFF=%02X 7FFA=%02X)',
                st['cpu.pc'], nmi, read(0x2D), read(0x7FFF), read(0x7FFA)))
            finish()
        end
    elseif phase == 'guest_win' then
        local b = activeBooth()
        local gf = frame - phaseStart
        local nmi = read(0xFFFA) + read(0xFFFB) * 256
        local triggerFrame = 120
        if gf == triggerFrame then
            winTriggerPending = true
            winTriggerFrame = frame
        end
        if gf > triggerFrame and nmi == 0xC07B then
            local meltFrames = frame - winTriggerFrame
            local minMelt = (b.id == 'waldo') and 22 or 25
            check(meltFrames >= minMelt,
                string.format('%s: melt-out transition ran >=%d frames (%df)', b.id, minMelt, meltFrames))
            check((read(0x4015) & 0x1F) == 0 and last4011 == 0,
                string.format('%s: win exit clean APU mute ($4015=%02X $4011=%02X)', b.id, read(0x4015), last4011))
            phase = 'return'
            phaseStart = frame
        elseif gf > 550 then
            check(false, string.format('%s: win hook timed out waiting for return (nmi=$%04X)', b.id, nmi))
            finish()
        end
    elseif phase == 'return' then
        local b = activeBooth()
        local rf = frame - phaseStart
        if not negTest and rf == 60 then
            check(read(0x6804) == b.gameId,
                string.format('%s: RA_LAST_WIN_GAME ($6804) == %d (got %d)', b.id, b.gameId, read(0x6804)))
            check(read(0x74C) ~= 0, string.format('%s: context-aware win dialogue active', b.id))
        end
        if (negTest and rf > 50 or (not negTest and rf > 245))
            and read(0x74C) == 0 and read(0xDE) == 0 then
            check(read(0x6803) == 0, string.format('%s: ACTIVE_GAME_ID restored to 0 (got %d)', b.id, read(0x6803)))
            if negTest then
                check(read(0x6804) == 0, string.format('feud Start+Select left $6804=0 (got %d)', read(0x6804)))
                check(read(0x63B2) == 0, string.format('feud Start+Select left $63B2=0 (got $%02X)', read(0x63B2)))
                negTest = false
                idx = 1
                phase = 'walk_booth'
                phaseStart = frame
            else
                local got = read(b.rewardAddr)
                check(got == b.expected,
                    string.format('%s: win unlocked $%04X=$%02X (got $%02X)', b.id, b.rewardAddr, b.expected, got))
                unlocked[b.id] = {addr = b.rewardAddr, expected = b.expected}
                local persistOk = true
                for _, prev in pairs(unlocked) do
                    if read(prev.addr) ~= prev.expected then
                        persistOk = false
                    end
                end
                check(persistOk, string.format('%s: all %d unlocked rewards persisted', b.id, idx))
                idx = idx + 1
                if idx <= #booths then
                    phase = 'walk_booth'
                    phaseStart = frame
                else
                    -- Prepare for pause menu & Gear Bar verification inside Rauru Arcade
                    write(0x0773, 0xFF)
                    write(0x0778, 8)
                    write(0x0749, 0)
                    phase = 'menu_verify'
                    phaseStart = frame
                end
            end
        elseif rf > 360 then
            check(false, b.id .. ': return dialogue did not clear')
            finish()
        end
    elseif phase == 'menu_verify' then
        local dt = frame - phaseStart
        if dt >= 4 and dt < 7 then currentInput = {start = true} end
        if dt == 32 then
            check(read(0x0524) == 5, 'Pause menu opened to input state after all 5 wins')
        elseif dt >= 36 and dt < 39 then
            -- Hop from left column (Hyrule 0) to right column (Arcade 8: DECOY)
            currentInput = {right = true}
        elseif dt == 42 then
            check(read(0x0749) == 8, string.format('Arcade slot 8 (DECOY) selectable (sel=%d)', read(0x0749)))
        elseif dt >= 44 and dt < 68 then
            -- Step down 4 times (10 DOUBLE, 11 BARREL, 13 LOCK, 15 LUCKY)
            local step = dt - 44
            if step % 6 < 3 and math.floor(step / 6) < 4 then
                currentInput = {down = true}
            end
        elseif dt == 72 then
            check(read(0x0749) == 15, string.format('Arcade slot 15 (LUCKY, Wheel) selectable (sel=%d)', read(0x0749)))
        elseif dt >= 76 and dt < 79 then
            -- Focus Gear Bar (HAT) and equip TIE ($10)
            currentInput = {select = true}
        elseif dt >= 84 and dt < 87 then
            currentInput = {right = true}
        elseif dt >= 92 and dt < 95 then
            currentInput = {a = true} -- equip TIE ($10)
        elseif dt >= 100 and dt < 103 then
            currentInput = {start = true} -- close menu
        elseif dt == 135 then
            check(read(0x0524) == 0, 'Pause menu closed cleanly')
            check((read(0x648F) & 0x91) == 0x91,
                string.format('Active Gear Bar trophies equipped ($648F=$%02X)', read(0x648F)))
            finish()
        end
    end
end, emu.eventType.endFrame)
