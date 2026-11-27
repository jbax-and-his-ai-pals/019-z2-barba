-- End-to-end Barba's Arcade win-to-unlock & Phase 3 discovery/transition verification in build/barba.nes:
--   1. Verifies RA Telemetry Header ($6800-$6802), ACTIVE_GAME_ID=0, and initial discovery ($6806=$01, $6807=$00).
--   2. Verifies undiscovered Booth 1 (f13) in Rauru's Arcade ($1C) shows "OUT OF ORDER!" and does not launch.
--   3. Visits all 9 remaining Hyrule discovery spots and verifies full discovery bitmask ($6806=$FF, $6807=$03).
--   4. Tests F13 Start+Select negative case (silent clean return: $074C==0, $DE==0, $6804==0, $4015==0, $63B1==0).
--   5. Enters all 10 booths in Barba's Arcade, triggers each patched win hook, asserts >=25f melt-out,
--      verifies ACTIVE_GAME_ID (1..10 -> 0) and RA_LAST_WIN_GAME ($6804 == gameId), unlocks all rewards,
--      verifies pause menu & Gear Bar trophies, F13 Forest Coven ending, and EH $07 World 0 smb win return.
dofile(TEST_DIR .. '/newgame.lua')
local mem = emu.memType.nesMemory
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end

local booths = {
    {id='waldo', slot=0, gameId=1,  page=0, x=0x50, nmi=0xF603, rewardAddr=0x648B, expected=0x57, winPc=0xF641},
    {id='f13',   slot=1, gameId=2,  page=0, x=0x90, nmi=0x7852, rewardAddr=0x63B1, expected=0x01, winPc=0x8E40, f13Day3=true},
    {id='feud',  slot=2, gameId=3,  page=0, x=0xD0, nmi=0xCA5E, rewardAddr=0x63B2, expected=0x01, winPc=0xA964, bankR6=0, bankR7=1},
    {id='dk',    slot=3, gameId=4,  page=1, x=0x20, nmi=0x7840, rewardAddr=0x63B3, expected=0x01, winPc=0xC8B3},
    {id='smb',   slot=4, gameId=5,  page=1, x=0x70, nmi=0x7800, rewardAddr=0x63B4, expected=0x01, winPc=0x8487, bankR6=28},
    {id='duck',  slot=5, gameId=6,  page=1, x=0xC0, nmi=0x7840, rewardAddr=0x63B5, expected=0x01, winPc=0xD39B},
    {id='mm2',   slot=6, gameId=7,  page=2, x=0x70, nmi=0xF380, rewardAddr=0x63B7, expected=0x01, winPc=0xC25A},
    {id='wheel', slot=7, gameId=8,  page=2, x=0xC0, nmi=0x7850, rewardAddr=0x63B8, expected=0x01, winPc=0xC988},
    {id='zelda', slot=8, gameId=9,  page=3, x=0x20, nmi=0xFF58, rewardAddr=0x63B9, expected=0x01, winPc=0xABA8, bankR6=6, bankR7=7, zeldaSeed=true},
    {id='mtpo',  slot=9, gameId=10, page=3, x=0x70, nmi=0xDA76, rewardAddr=0x63BA, expected=0x01, winPc=0xAC6C, bankR7=29},
}

local hyruleSpots = {
    {id='f13_bagu',       world=1, reg=0, town=3, area=3,  room=0x18, page=0, x=0x90, y=0xB0},
    {id='feud_saria',     world=1, reg=0, town=2, area=1,  room=0x1B, page=0, x=0x70, y=0xB0},
    {id='dk_ruto',        world=1, reg=0, town=1, area=3,  room=0x19, page=0, x=0x70, y=0xB0},
    {id='smb_ocean',      world=0, reg=2, town=0, area=2,  room=0x07, page=1, x=0x70, y=0xB0, f748=0x0A, owY=56, owX=63},
    {id='duck_mido',      world=1, reg=0, town=3, area=3,  room=0x36, page=0, x=0x70, y=0xB0},
    {id='mm2_darunia',    world=2, reg=2, town=5, area=3,  room=0x3D, page=0, x=0x70, y=0xB0},
    {id='wheel_nabooru',  world=2, reg=2, town=4, area=3,  room=0x3B, page=0, x=0x70, y=0xB0},
    {id='zelda_nkasuto',  world=2, reg=2, town=6, area=3,  room=0x3E, page=0, x=0x70, y=0xB0},
    {id='mtpo_okasuto',   world=2, reg=2, town=7, area=3,  room=0x23, page=2, x=0x70, y=0xB0},
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
local covenTest = false
local owWinTest = false
local idx = 1
local discIdx = 1
local winTriggerPending = false
local winTriggerFrame = 0
local lastLaunchedGameId = 0
local last4011 = 0xFF
local unlocked = {}

local function activeBooth()
    if lockedTest or negTest or covenTest then return booths[2] end
    if owWinTest then return booths[5] end
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
    if covenTest then
        -- Map F13 Bank 2 ($8000-$BFFF) = R6 26, R7 27 and enter CovenMain ($8000) as Debbie ($7C60=1).
        write(0x7C60, 1)
        write(0x8000, 0x06); write(0x8001, 26)
        write(0x8000, 0x07); write(0x8001, 27)
        emu.setState({['cpu.pc'] = 0x8000})
        return
    end
    if b.f13Day3 then
        write(0x0522, 2)
    end
    if b.zeldaSeed then
        write(0x7FE8, 6)
        write(0x7FE9, 7)
    end
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
        if owWinTest then
            emu.setInput({up = (ef >= 10 and ef < 14)}, 0)
        elseif lockedTest then
            emu.setInput({up = (ef >= 10 and ef < 14), b = (ef >= 160 and ef < 164)}, 0)
        else
            emu.setInput({up = (ef >= 10 and ef < 14), b = (ef >= 240 and ef < 244)}, 0)
        end
    elseif phase == 'guest_neg' then
        local gf = frame - phaseStart
        emu.setInput({
            start = (gf >= 380 and gf < 385) or (gf >= 460),
            select = (gf >= 460),
        }, 0)
    elseif phase == 'guest_win' then
        local gf = frame - phaseStart
        if covenTest then
            local b_btn = (gf > 180 and gf < 950)
            local a_btn = (gf > 180 and (gf % 20 < 4))
            local st_btn = (gf >= 700 and (gf % 15 < 5))
            emu.setInput({a = a_btn, b = b_btn, start = st_btn}, 0)
        elseif activeBooth().f13Day3 then
            emu.setInput({start = (gf >= 90 and gf < 95)}, 0)
        else
            emu.setInput({}, 0)
        end
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
                check(read(0x6806) == 0xFF and read(0x6807) == 0x03,
                    string.format('All 10 spots discovered ($6806=%02X $6807=%02X)', read(0x6806), read(0x6807)))
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
                check(read(0x6806) == 0xFF and read(0x6807) == 0x03,
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
        if read(0x3B) == b.page and math.abs(read(0x4D) - b.x) <= 4 and (owWinTest and read(0x479) == 0 or read(0x29) == 0xB0) then
            write(0x70, 0)
            if not lockedTest and not negTest and not covenTest and not owWinTest then
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
                check(read(0x074C) ~= 0 or read(0xDE) ~= 0, 'Undiscovered booth f13 opened OUT OF ORDER dialogue')
            end
            if ef == 200 then
                check(nmi == 0xC07B and read(0x6803) == 0 and read(0x074C) == 0,
                    'Undiscovered booth f13 did not launch and dismissed cleanly')
                lockedTest = false
                discIdx = 1
                warpRoom(hyruleSpots[discIdx])
                phase = 'discover_load'
                phaseStart = frame
            end
        elseif ((owWinTest and ef > 60) or (not owWinTest and ef > 240)) and nmi == b.nmi then
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
                string.format('f13 negative clean APU mute ($4015=%02X $4011=%02X)', read(0x4015), last4011))
            phase = 'return'
            phaseStart = frame
        elseif gf > 650 then
            local st = emu.getState()
            check(false, string.format('f13 negative Start+Select timed out (pc=%04X nmi=%04X 2D=%02X 7FFF=%02X 7FFA=%02X)',
                st['cpu.pc'], nmi, read(0x2D), read(0x7FFF), read(0x7FFA)))
            finish()
        end
    elseif phase == 'guest_win' then
        local b = activeBooth()
        local gf = frame - phaseStart
        local nmi = read(0xFFFA) + read(0xFFFB) * 256
        local triggerFrame = b.f13Day3 and 140 or 120
        if covenTest then triggerFrame = 50 end
        if gf == triggerFrame then
            winTriggerPending = true
            winTriggerFrame = frame
        end
        if gf > triggerFrame and nmi == 0xC07B then
            local meltFrames = frame - winTriggerFrame
            check(meltFrames >= 25,
                string.format('%s: melt-out transition ran >=25 frames (%df)', b.id, meltFrames))
            check((read(0x4015) & 0x1F) == 0 and last4011 == 0,
                string.format('%s: win exit clean APU mute ($4015=%02X $4011=%02X)', b.id, read(0x4015), last4011))
            phase = 'return'
            phaseStart = frame
        elseif gf > (covenTest and 1400 or 550) then
            check(false, string.format('%s: win hook timed out waiting for return (nmi=$%04X)', b.id, nmi))
            finish()
        end
    elseif phase == 'return' then
        local b = activeBooth()
        local rf = frame - phaseStart
        if not negTest and not owWinTest and rf == 60 then
            check(read(0x6804) == b.gameId,
                string.format('%s: RA_LAST_WIN_GAME ($6804) == %d (got %d)', b.id, b.gameId, read(0x6804)))
            check(read(0x74C) ~= 0, string.format('%s: context-aware win dialogue active', b.id))
        end
        if (negTest and rf > 50 or (owWinTest and rf > 100) or (not negTest and not owWinTest and rf > 245))
            and read(0x74C) == 0 and read(0xDE) == 0 and (not owWinTest or read(0x726) == 0) then
            check(read(0x6803) == 0, string.format('%s: ACTIVE_GAME_ID restored to 0 (got %d)', b.id, read(0x6803)))
            if negTest then
                check(read(0x6804) == 0, string.format('f13 Start+Select left $6804=0 (got %d)', read(0x6804)))
                check(read(0x63B1) == 0, string.format('f13 Start+Select left $63B1=0 (got $%02X)', read(0x63B1)))
                negTest = false
                idx = 1
                phase = 'walk_booth'
                phaseStart = frame
            elseif owWinTest then
                check(read(0x6804) == 5, string.format('EH $07 smb win set $6804=5 (got %d)', read(0x6804)))
                check(read(0x63B4) == 1, string.format('EH $07 smb win set $63B4=1 (got $%02X)', read(0x63B4)))
                check(read(0x0707) == 0 and read(0x0561) == 0x07,
                    string.format('EH $07 resumed World 0 room 7 ($0707=%d $0561=%02X)', read(0x0707), read(0x0561)))
                owWinTest = false
                -- Warp to Palace 1 to verify casting newly unlocked HEAVY in side-view combat
                warpRoom({world=3, reg=0, town=0, area=3, room=5, page=0})
                phase = 'cast_heavy_load'
                phaseStart = frame
            elseif covenTest then
                check(read(0x63B1) == 0x01,
                    string.format('f13 Forest Coven ending unlocked $63B1=$01 (got $%02X)', read(0x63B1)))
                covenTest = false
                owWinTest = true
                write(0x63B4, 0x00)
                warpRoom(hyruleSpots[4])  -- East Hyrule Ocean Island ($0707=0, $0706=2, $0561=7)
                phase = 'ow_load'
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
    elseif phase == 'ow_load' then
        local sf = frame - phaseStart
        local sp = hyruleSpots[4]
        if sf >= 30 and read(0x726) == 0 and read(0x736) == 11 and read(0x0561) == 0x07 then
            for s = 0, 5 do write(0xB6 + s, 0) end
            write(0x72A, sp.page); write(0x72C, 0)
            write(0x3B, sp.page); write(0x4D, sp.x); write(0x29, 0x80); write(0x70, 0)
            phase = 'walk_booth'
            phaseStart = frame
        elseif sf > 240 then
            check(false, 'Timed out loading EH $07 for World 0 win return test')
            finish()
        end
    elseif phase == 'menu_verify' then
        local dt = frame - phaseStart
        if dt >= 4 and dt < 7 then currentInput = {start = true} end
        if dt == 32 then
            check(read(0x0524) == 5, 'Pause menu opened to input state after all 10 wins')
        elseif dt >= 36 and dt < 39 then
            -- Hop from left column (Hyrule 0) to right column (Arcade 8: DECOY)
            currentInput = {right = true}
        elseif dt == 42 then
            check(read(0x0749) == 8, string.format('Arcade slot 8 (DECOY) selectable (sel=%d)', read(0x0749)))
        elseif dt >= 44 and dt < 47 then
            currentInput = {down = true}
        elseif dt == 50 then
            check(read(0x0749) == 9, string.format('Arcade slot 9 (AXE, F13) selectable (sel=%d)', read(0x0749)))
        elseif dt >= 52 and dt < 100 then
            -- Step down 8 times (10..17) to HEAVY (17)
            local step = dt - 52
            if step % 6 < 3 and math.floor(step / 6) < 8 then
                currentInput = {down = true}
            end
        elseif dt == 104 then
            check(read(0x0749) == 17, string.format('Arcade slot 17 (HEAVY, MTPO) selectable (sel=%d)', read(0x0749)))
        elseif dt >= 108 and dt < 111 then
            -- Focus Gear Bar (HAT) and equip MASK -> HELM -> TIE -> BELT
            currentInput = {select = true}
        elseif dt >= 116 and dt < 119 then
            currentInput = {right = true}
        elseif dt >= 122 and dt < 125 then
            currentInput = {right = true}
        elseif dt >= 128 and dt < 131 then
            currentInput = {a = true} -- equip HELM (3)
        elseif dt >= 134 and dt < 137 then
            currentInput = {right = true}
        elseif dt >= 140 and dt < 143 then
            currentInput = {a = true} -- equip TIE ($10)
        elseif dt >= 146 and dt < 149 then
            currentInput = {right = true}
        elseif dt >= 152 and dt < 155 then
            currentInput = {a = true} -- equip BELT ($20)
        elseif dt >= 160 and dt < 163 then
            currentInput = {start = true} -- close menu
        elseif dt == 195 then
            check(read(0x0524) == 0, 'Pause menu closed cleanly')
            check((read(0x648F) & 0xB3) == 0xB3,
                string.format('All 5 unlocked Gear Bar trophies equipped ($648F=$%02X)', read(0x648F)))
        elseif dt >= 200 and dt < 203 then
            currentInput = {select = true} -- cast HEAVY (17)
        elseif dt == 210 then
            -- Walk to f13 for Forest Coven test, then EH $07 smb test, then Palace 1 HEAVY spell cast check.
            write(0x63B1, 0x00)
            covenTest = true
            phase = 'walk_booth'
            phaseStart = frame
        end
    elseif phase == 'cast_heavy_load' then
        if frame - phaseStart >= 30 and read(0x0736) == 0x0B and read(0x0726) == 0 and read(0x0524) == 0 then
            phase = 'cast_heavy_palace'
            phaseStart = frame
        elseif frame - phaseStart > 300 then
            check(false, 'Timed out loading Palace 1 for HEAVY spell cast check')
            finish()
        end
    elseif phase == 'cast_heavy_palace' then
        local dt = frame - phaseStart
        if dt == 25 then
            write(0x0773, 0xFF); write(0x0778, 8); write(0x0749, 17); write(0x074A, 0)
            currentInput = {select = true}
        elseif dt >= 26 and dt < 29 then
            currentInput = {select = true}
        elseif dt == 36 then
            check((read(0x6681) & 0x02) == 0x02,
                string.format('Cast newly unlocked HEAVY spell ($6681=$%02X)', read(0x6681)))
            finish()
        end
    end
end, emu.eventType.endFrame)
