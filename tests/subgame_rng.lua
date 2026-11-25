-- Verify subgame RNG is seeded from Zelda II's base RNG on every portal entry
-- and changes across re-entries into the same door.
dofile(TEST_DIR .. '/newgame.lua')
local mem = emu.memType.nesMemory
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end

local report = assert(io.open(OUTPUT_DIR .. '/subgame-rng.txt', 'w'))
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

-- Cases: smb twice (to verify re-entry changes RNG), plus waldo inside Barba's Arcade ($1C).
local cases = {
    {id='smb_1',    town=0, room=0x1C, page=1, x=0x70, nmi=0x7800},
    {id='smb_2',    town=0, room=0x1C, page=1, x=0x70, nmi=0x7800, reuse=true},
    {id='waldo',    town=0, room=0x1C, page=0, x=0x50, nmi=0xF603},
}

local frame = 0
local idx = 1
local phase = 'boot'
local phaseStart = 0
local smbSeed1 = nil
local smbBoot1 = nil
local smbBoot2 = nil

-- Capture subgame RNG right at NMI hook entry (first frame inside guest)
local captured = {}

local function warpToCase(c)
    write(0x707, 1)
    write(0x706, c.town)
    write(0x056B, c.town)
    write(0x769, 3)
    write(0x561, c.room)
    write(0x701, 0)
    write(0x75C, 0)
    write(0x704, 0)
    write(0x736, 0)
    write(0x73D, 0)
    write(0x726, 1)
    phase = 'load_room'
    phaseStart = frame
end

emu.addEventCallback(function()
    if phase == 'boot' and frame < 1000 then
        emu.setInput(newGameInput(frame), 0)
    elseif phase == 'walk' then
        local c = cases[idx]
        local curPage = read(0x3B)
        local curX = read(0x4D)
        if curPage < c.page or (curPage == c.page and curX < c.x - 4) then
            emu.setInput({right = true}, 0)
        elseif curPage > c.page or (curPage == c.page and curX > c.x + 4) then
            emu.setInput({left = true}, 0)
        else
            emu.setInput({}, 0)
        end
    elseif phase == 'enter' then
        local ef = frame - phaseStart
        emu.setInput({up = (ef >= 10 and ef < 15), b = (ef >= 250 and ef < 254)}, 0)
    elseif phase == 'guest' then
        local gf = frame - phaseStart
        emu.setInput({start = (gf >= 80), select = (gf >= 80)}, 0)
    elseif phase == 'return' then
        local rf = frame - phaseStart
        emu.setInput({b = (rf >= 250 and rf < 254)}, 0)
    else
        emu.setInput({}, 0)
    end
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if done then return end
    frame = frame + 1
    local c = cases[idx]
    if phase == 'boot' then
        if frame == 1000 then
            warpToCase(c)
        end
    elseif phase == 'load_room' then
        if frame - phaseStart >= 8 and read(0x726) == 0 then
            phase = 'walk'
            phaseStart = frame
        end
    elseif phase == 'walk' then
        for s = 0, 5 do write(0xB6 + s, 0) end
        if read(0x3B) == c.page and math.abs(read(0x4D) - c.x) <= 4 and read(0x29) == 0xB0 then
            write(0x70, 0)
            phase = 'enter'
            phaseStart = frame
        elseif frame - phaseStart > 600 then
            check(false, c.id .. ': timed out walking to door')
            finish()
        end
    elseif phase == 'enter' then
        local ef = frame - phaseStart
        local nmi = read(0xFFFA) + read(0xFFFB) * 256
        if ef > 250 and nmi == c.nmi then
            -- Sample WRAM seed ($7FF0..$7FF7) and guest RNG right after boot
            local wseed = {}
            for i = 0, 7 do wseed[i + 1] = read(0x7FF0 + i) end
            if c.id == 'smb_1' then
                local r0, r1 = read(0x07A7), read(0x07A8)
                local any_diff = false
                for i = 1, 6 do
                    if read(0x07A7 + i) ~= 0 then any_diff = true end
                end
                smbSeed1 = string.format('%02X%02X', wseed[1], wseed[2])
                smbBoot1 = string.format('%02X%02X', r0, r1)
                check(wseed[1] ~= 0, 'smb_1: host wrote non-zero seed to $7FF0 (' .. smbSeed1 .. ')')
                check(r0 == wseed[1], string.format('smb_1: $07A7 seeded from $7FF0 ($%02X == $%02X)', r0, wseed[1]))
                check(any_diff, 'smb_1: $07A8-$07AD seeded beyond hardcoded $A5/00')
            elseif c.id == 'smb_2' then
                local r0, r1 = read(0x07A7), read(0x07A8)
                local seed2 = string.format('%02X%02X', wseed[1], wseed[2])
                smbBoot2 = string.format('%02X%02X', r0, r1)
                check(seed2 ~= smbSeed1, 'smb_2: WRAM seed changed on re-entry (' .. smbSeed1 .. ' -> ' .. seed2 .. ')')
                check(smbBoot2 ~= smbBoot1, 'smb_2: guest RNG $07A7/$07A8 changed on re-entry (' .. smbBoot1 .. ' -> ' .. smbBoot2 .. ')')
            elseif c.id == 'waldo' then
                check(read(0x0200) == wseed[1] and read(0x0201) == wseed[2],
                    string.format('waldo: $0200/$0201 seeded from $7FF0/$7FF1 ($%02X%02X)', read(0x0200), read(0x0201)))
            end
            phase = 'guest'
            phaseStart = frame
        elseif ef > 340 then
            check(false, string.format('%s: timed out entering guest (nmi=$%04X)', c.id, nmi))
            finish()
        end
    elseif phase == 'guest' then
        local gf = frame - phaseStart
        local nmi = read(0xFFFA) + read(0xFFFB) * 256
        if gf > 80 and nmi == 0xC07B then
            phase = 'return'
            phaseStart = frame
        elseif gf > 200 then
            check(false, c.id .. ': timed out returning from guest')
            finish()
        end
    elseif phase == 'return' then
        local rf = frame - phaseStart
        if rf > 260 and read(0x74C) == 0 then
            idx = idx + 1
            if idx > #cases then
                finish()
            elseif cases[idx].reuse then
                -- Stay in the same room and walk back into the same door after a few frames
                phase = 'walk'
                phaseStart = frame
            else
                warpToCase(cases[idx])
            end
        elseif rf > 320 then
            check(false, c.id .. ': return dialog did not close')
            finish()
        end
    end
end, emu.eventType.frameEnd)
