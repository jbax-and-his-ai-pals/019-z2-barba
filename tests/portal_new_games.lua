-- End-to-end in-ROM portal round-trip test for DK and Duck Hunt.
dofile(TEST_DIR .. '/newgame.lua')
local mem = emu.memType.nesMemory
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end

local cases = {
    {id='dk',     town=1, area=3, room=0x19, page=0, x=0x70, nmi=0x7840},
    {id='duck',   town=3, area=3, room=0x36, page=0, x=0x70, nmi=0x7840},
}

local report = assert(io.open(OUTPUT_DIR .. '/portal-new-games.txt', 'w'))
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
local idx = 1
local phase = 'boot'
local phaseStart = 0

local function warpToCase(c)
    write(0x707, 1)
    write(0x706, 0)
    write(0x056B, c.town)
    write(0x769, c.area)
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
        emu.setInput({}, 0)
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
        if ef == 15 then
            check(read(0x74C) == 0x02, c.id .. ': door opened portal message box')
        elseif ef > 250 and nmi == c.nmi then
            check(true, string.format('%s: entered guest ($FFFA=$%04X)', c.id, nmi))
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
            check(true, c.id .. ': Start+Select returned to Barba ($FFFA=$C07B)')
            phase = 'return'
            phaseStart = frame
        elseif gf > 500 then
            local st = emu.getState()
            check(false, string.format('%s: timed out returning to Barba (nmi=$%04X pc=$%04X 7fff=$%02X)',
                c.id, nmi, st['cpu.pc'] or 0, read(0x7FFF)))
            finish()
        end
    elseif phase == 'return' then
        local rf = frame - phaseStart
        if rf > 50 and read(0x74C) == 0 and read(0xDE) == 0 then
            check(read(0x056B) == c.town and read(0x0561) == c.room and read(0x3B) == c.page,
                c.id .. ': Barba restored to exact town/room/page')
            idx = idx + 1
            if idx > #cases then
                finish()
            else
                warpToCase(cases[idx])
            end
        elseif rf > 340 then
            check(false, c.id .. ': timed out dismissing return dialogue')
            finish()
        end
    end
end, emu.eventType.endFrame)
