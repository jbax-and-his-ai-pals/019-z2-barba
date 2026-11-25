-- Smoke test for Barba's Arcade (Rauru Room $1C) and all 9 currently wired booths.
dofile(TEST_DIR .. '/newgame.lua')
local mem = emu.memType.nesMemory
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end

local booths = {
    {id='waldo',  page=0, x=0x50, nmi=0xF603},
    {id='f13',    page=0, x=0x90, nmi=0x7840},
    {id='feud',   page=0, x=0xD0, nmi=0xCA5E},
    {id='dk',     page=1, x=0x20, nmi=0x7840},
    {id='smb',    page=1, x=0x70, nmi=0x7800},
    {id='duck',   page=1, x=0xC0, nmi=0x7840},
    {id='mm2',    page=2, x=0x70, nmi=0xF380},
    {id='wheel',  page=2, x=0xC0, nmi=0x7850},
    {id='zelda',  page=3, x=0x20, nmi=0xFF58},
    {id='mtpo',   page=3, x=0x70, nmi=0xDA57},
}

local report = assert(io.open(OUTPUT_DIR .. '/arcade-smoke.txt', 'w'))
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
local idx = 1
local phase = 'boot'
local phaseStart = 0
local tookShot = false

emu.addEventCallback(function()
    if phase == 'boot' and frame < 1000 then
        emu.setInput(newGameInput(frame), 0)
    elseif phase == 'enter_arcade' then
        local ef = frame - phaseStart
        emu.setInput({up = (ef >= 10 and ef < 14)}, 0)
    elseif phase == 'walk_booth' then
        local b = booths[idx]
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
        emu.setInput({up = (ef >= 10 and ef < 14), b = (ef >= 240 and ef < 244)}, 0)
    elseif phase == 'guest' then
        local gf = frame - phaseStart
        emu.setInput({start = (gf >= 80), select = (gf >= 80)}, 0)
    elseif phase == 'return' then
        local rf = frame - phaseStart
        emu.setInput({b = (rf >= 240 and rf < 244)}, 0)
    elseif phase == 'exit_arcade' then
        emu.setInput({left = true}, 0)
    else
        emu.setInput({}, 0)
    end
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if done then return end
    frame = frame + 1
    local b = booths[idx]
    if phase == 'boot' then
        if frame == 1000 then
            -- Warp to Rauru ($01) page 1 right in front of the Arcade door (x=40)
            write(0x707, 1); write(0x706, 0); write(0x056B, 0); write(0x769, 3); write(0x561, 1)
            write(0x701, 0); write(0x75C, 1); write(0x704, 0); write(0x736, 0); write(0x73D, 0); write(0x726, 1)
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
            check(true, 'Entered Barba Arcade room $1C')
            phase = 'walk_booth'
            phaseStart = frame
        elseif ef > 180 then
            check(false, string.format('Timed out entering Arcade (room=$%02X mode=%d p=%d x=%d y=%d)', read(0x561), read(0x736), read(0x3B), read(0x4D), read(0x29)))
            finish()
        end
    elseif phase == 'walk_booth' then
        if not tookShot and frame - phaseStart == 25 then
            local png = emu.takeScreenshot()
            local out = assert(io.open(OUTPUT_DIR .. '/arcade_p0.png', 'wb'))
            out:write(png); out:close()
            tookShot = true
        end
        if read(0x3B) == b.page and math.abs(read(0x4D) - b.x) <= 4 and read(0x29) == 0xB0 then
            write(0x70, 0)
            phase = 'enter_game'
            phaseStart = frame
        elseif frame - phaseStart > 900 then
            check(false, string.format('%s: timed out walking to booth (page=%d x=%d)', b.id, read(0x3B), read(0x4D)))
            finish()
        end
    elseif phase == 'enter_game' then
        local ef = frame - phaseStart
        local nmi = read(0xFFFA) + read(0xFFFB) * 256
        if ef == 16 then
            check(read(0x74C) == 0x02, b.id .. ': booth opened INSERT COIN dialogue')
        elseif ef > 240 and nmi == b.nmi then
            check(true, string.format('%s: entered guest ($FFFA=$%04X)', b.id, nmi))
            phase = 'guest'
            phaseStart = frame
        elseif ef > 380 then
            check(false, string.format('%s: timed out entering guest (nmi=$%04X)', b.id, nmi))
            finish()
        end
    elseif phase == 'guest' then
        local gf = frame - phaseStart
        local nmi = read(0xFFFA) + read(0xFFFB) * 256
        if gf > 80 and nmi == 0xC07B then
            check(true, string.format('%s: Start+Select returned to Barba ($FFFA=$C07B)', b.id))
            phase = 'return'
            phaseStart = frame
        elseif gf > 260 then
            check(false, string.format('%s: Start+Select timed out (nmi=$%04X)', b.id, nmi))
            finish()
        end
    elseif phase == 'return' then
        local rf = frame - phaseStart
        if rf > 245 and read(0x74C) == 0 and read(0xDE) == 0 then
            check(read(0x0561) == 0x1C, string.format('%s: restored cleanly inside Barba Arcade ($1C)', b.id))
            idx = idx + 1
            if idx <= #booths then
                phase = 'walk_booth'
                phaseStart = frame
            else
                phase = 'exit_arcade'
                phaseStart = frame
            end
        elseif rf > 360 then
            check(false, b.id .. ': return dialogue did not clear')
            finish()
        end
    elseif phase == 'exit_arcade' then
        if read(0x561) == 0x01 and read(0x736) == 11 then
            check(true, 'Exited Barba Arcade left door back to Rauru $01')
            finish()
        elseif frame - phaseStart > 900 then
            check(false, string.format('Timed out exiting Arcade (room=$%02X page=%d x=%d)', read(0x561), read(0x3B), read(0x4D)))
            finish()
        end
    end
end, emu.eventType.endFrame)
