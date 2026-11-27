-- Mesen callbacks for the experimental two-ROM Rauru portal.
local memory = emu.memType.nesDebug
local function read(address) return emu.read(address, memory) end
local function write(address, value) emu.write(address, value, memory) end

local function writeFile(name, data)
    local file = assert(io.open(PORTAL_DIR .. '/' .. name, 'wb'))
    assert(file:write(data))
    assert(file:close())
end

local function readFile(name)
    local file = assert(io.open(PORTAL_DIR .. '/' .. name, 'rb'))
    local data = file:read('*a')
    file:close()
    return data
end

local switching = false

local function signal(name, data)
    writeFile(name .. '.tmp', data)
    assert(os.rename(PORTAL_DIR .. '/' .. name .. '.tmp', PORTAL_DIR .. '/' .. name))
end

local function switchGame(nextGame)
    switching = true
    signal('next', nextGame)
    emu.stop(0)
end

local function guarded(callback)
    return function()
        if switching then return end
        local ok, message = xpcall(callback, debug.traceback)
        if not ok then
            switching = true
            signal('error', message)
            emu.stop(1)
        end
    end
end

local function location()
    return string.format('world=%02X room=%02X page=%02X x=%02X y=%02X scroll=%02X%02X hp=%02X magic=%02X',
        read(0x707), read(0x561), read(0x3B), read(0x4D), read(0x29),
        read(0x72A), read(0x72C), read(0x774), read(0x773))
end

local function atDoor()
    local x = read(0x4D)
    return read(0x707) == 1 and read(0x561) == 1 and read(0x736) == 0x0B
        and read(0x3B) == 1 and x >= 0x20 and x < 0x30 and read(0x29) == 0xB0
end

local frame, blocked = 0, STAGE == 'return'
local snapshot, position, restored
local moonFrames = 0

if STAGE == 'setup' then dofile(TEST_DIR .. '/newgame.lua') end

emu.addEventCallback(guarded(function()
    local up = emu.getInput(0).up
    if HEADLESS then
        if STAGE == 'setup' then
            emu.setInput(newGameInput(frame), 0)
        elseif STAGE == 'enter' then
            emu.setInput({up = frame >= 30 and frame < 34}, 0)
        elseif STAGE == 'waldo' then
            emu.setInput({start = frame == 263 or frame == 274 or frame == 285 or frame >= 1360,
                          select = frame == 270 or frame == 272 or frame >= 1360}, 0)
        else
            up = frame < 12
            if not blocked then emu.setInput({up = up}, 0) end
        end
    end
    if blocked then
        emu.setInput({up = false}, 0)
        if restored and not up then blocked = false end
    end
end), emu.eventType.inputPolled)

if STAGE ~= 'waldo' then
    -- Mesen only allows state operations inside a CPU execution callback.
    emu.addMemoryCallback(guarded(function()
        if STAGE == 'return' and not restored then
            assert(emu.loadSavestate(readFile('barba.state')), 'Could not restore Rauru state')
            assert(location() == readFile('departure'), 'Rauru state differs from departure')
            writeFile('arrival', location())
            restored, blocked = true, true
        elseif STAGE == 'enter' and not restored then
            assert(emu.loadSavestate(readFile('rauru.state')), 'Could not load the Rauru doorstep')
            restored = true
        elseif atDoor() and not blocked and not emu.getInput(0).up then
            -- Capture the street before the native door changes game mode.
            snapshot, position = emu.createSavestate(), location()
            if STAGE == 'setup' and frame >= 1170 then
                writeFile('rauru.state', snapshot)
                switchGame('ready')
            end
        end
    end), emu.callbackType.exec, 0xC07B)
end

emu.addEventCallback(guarded(function()
    frame = frame + 1
    if STAGE == 'waldo' then
        -- The US Moon ending sets this PPU shadow, palette entry, and music state.
        -- Leave the landing visible for six seconds before returning.
        if read(0x00) == 0xA8 and read(0x34) == 0x1F and read(0x56) == 0x80 then
            moonFrames = moonFrames + 1
            if moonFrames >= 360 then switchGame('return'); return end
        else
            moonFrames = 0
        end
        if HEADLESS and frame == 1280 then writeFile('waldo.png', emu.takeScreenshot()) end
        local input = emu.getInput(0)
        if not HEADLESS and frame < 180 then emu.drawString(8, 16, 'START + SELECT: RETURN') end
        if frame > 60 and input.start and input.select then switchGame('return') end
        return
    end

    if HEADLESS and STAGE == 'return' and frame == 30 then
        assert(restored and atDoor(), 'Barba left the doorstep after the restore: ' .. location())
        switchGame('done')
        return
    end

    if STAGE == 'setup' then
        if frame == 1000 then
            write(0x707, 1); write(0x706, 0); write(0x769, 3); write(0x561, 1)
            write(0x701, 0); write(0x75C, 1); write(0x704, 0); write(0x736, 0)
            write(0x73D, 0); write(0x726, 1)
        elseif frame == 1150 then
            for slot = 0, 5 do write(0xB6 + slot, 0) end
            write(0x4D, 40); write(0x70, 0)
        end
    end

    if snapshot and read(0x707) == 1 and read(0x561) == 0x1C then
        writeFile('barba.state', snapshot)
        writeFile('departure', position)
        switchGame('waldo')
    elseif atDoor() and not blocked then
        if not HEADLESS then emu.drawString(8, 48, 'UP: SECRET DOOR') end
    elseif read(0x736) ~= 0x16 then
        snapshot = nil
    end
end), emu.eventType.endFrame)
