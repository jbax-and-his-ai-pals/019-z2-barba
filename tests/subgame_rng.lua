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

-- Capture subgame RNG immediately after boot RNG seeder returns ($803C SMB / $E09D Waldo)
local smbBootSeed = nil
local waldoBootSeed = nil

emu.addMemoryCallback(function()
    if phase == 'enter' or phase == 'guest' then
        local c = cases[idx]
        local nmi = read(0xFFFA) + read(0xFFFB) * 256
        if c and (c.id == 'smb_1' or c.id == 'smb_2') and nmi == c.nmi and not smbBootSeed then
            smbBootSeed = {read(0x07A7), read(0x07A8), read(0x07A9), read(0x07AA), read(0x07AB), read(0x07AC), read(0x07AD)}
        end
    end
end, emu.callbackType.exec, 0x803C)

emu.addMemoryCallback(function()
    if phase == 'enter' or phase == 'guest' then
        local c = cases[idx]
        local nmi = read(0xFFFA) + read(0xFFFB) * 256
        if c and c.id == 'waldo' and nmi == c.nmi and not waldoBootSeed then
            waldoBootSeed = {read(0x0200), read(0x0201)}
        end
    end
end, emu.callbackType.exec, 0xE09D)

local function warpToArcade()
    write(0x707, 1)
    write(0x706, 0)
    write(0x056B, 0)
    write(0x769, 3)
    write(0x561, 1)
    write(0x701, 0)
    write(0x75C, 1)
    write(0x704, 0)
    write(0x736, 0)
    write(0x73D, 0)
    write(0x726, 1)
    phase = 'load_rauru'
    phaseStart = frame
end

emu.addEventCallback(function()
    if phase == 'boot' and frame < 1000 then
        emu.setInput(newGameInput(frame), 0)
    elseif phase == 'enter_arcade' then
        local ef = frame - phaseStart
        emu.setInput({up = (ef >= 10 and ef < 14)}, 0)
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
            warpToArcade()
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
            phase = 'walk'
            phaseStart = frame
        elseif ef > 180 then
            check(false, 'Timed out entering Arcade')
            finish()
        end
    elseif phase == 'walk' then
        for s = 0, 5 do write(0xB6 + s, 0) end
        if read(0x3B) == c.page and math.abs(read(0x4D) - c.x) <= 4 and read(0x29) == 0xB0 then
            write(0x70, 0)
            smbBootSeed = nil
            waldoBootSeed = nil
            phase = 'enter'
            phaseStart = frame
        elseif frame - phaseStart > 900 then
            check(false, c.id .. ': timed out walking to door')
            finish()
        end
    elseif phase == 'enter' then
        local ef = frame - phaseStart
        local nmi = read(0xFFFA) + read(0xFFFB) * 256
        if ef > 250 and nmi == c.nmi and (smbBootSeed ~= nil or waldoBootSeed ~= nil) then
            -- Sample WRAM seed ($7FF0..$7FF7) and captured boot RNG
            local wseed = {}
            for i = 0, 7 do wseed[i + 1] = read(0x7FF0 + i) end
            if c.id == 'smb_1' then
                local r0, r1 = smbBootSeed[1], smbBootSeed[2]
                local any_diff = false
                for i = 2, 7 do
                    if smbBootSeed[i] ~= 0 then any_diff = true end
                end
                smbSeed1 = string.format('%02X%02X', wseed[1], wseed[2])
                smbBoot1 = string.format('%02X%02X', r0, r1)
                check(wseed[1] ~= 0, 'smb_1: host wrote non-zero seed to $7FF0 (' .. smbSeed1 .. ')')
                check(r0 == wseed[1], string.format('smb_1: $07A7 seeded from $7FF0 ($%02X == $%02X)', r0, wseed[1]))
                check(any_diff, 'smb_1: $07A8-$07AD seeded beyond hardcoded $A5/00')
            elseif c.id == 'smb_2' then
                local r0, r1 = smbBootSeed[1], smbBootSeed[2]
                local seed2 = string.format('%02X%02X', wseed[1], wseed[2])
                smbBoot2 = string.format('%02X%02X', r0, r1)
                check(seed2 ~= smbSeed1, 'smb_2: WRAM seed changed on re-entry (' .. smbSeed1 .. ' -> ' .. seed2 .. ')')
                check(smbBoot2 ~= smbBoot1, 'smb_2: guest RNG $07A7/$07A8 changed on re-entry (' .. smbBoot1 .. ' -> ' .. smbBoot2 .. ')')
            elseif c.id == 'waldo' then
                check(waldoBootSeed[1] == wseed[1] and waldoBootSeed[2] == wseed[2],
                    string.format('waldo: $0200/$0201 seeded from $7FF0/$7FF1 ($%02X%02X)', waldoBootSeed[1], waldoBootSeed[2]))
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
            else
                -- Stay inside Barba's Arcade ($1C) and walk to the next booth
                phase = 'walk'
                phaseStart = frame
            end
        elseif rf > 320 then
            check(false, c.id .. ': return dialog did not close')
            finish()
        end
    end
end, emu.eventType.endFrame)
