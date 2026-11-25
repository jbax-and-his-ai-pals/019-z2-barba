-- Save-state generator for standalone Villager Hunt (play/standalone/duck-barba.nes).
local mem = emu.memType.nesMemory
local function read(a) return emu.read(a, mem) end
local function write(a, v) emu.write(a, v, mem) end

local VH_CURSOR_X = 0x0620
local VH_CURSOR_Y = 0x0621
local VH_CUR_R0   = 0x062B
local VH_CUR_R1   = 0x062C

local pendingSave = nil
local pendingStop = false
local function saveState(name)
    pendingSave = name
end

emu.addMemoryCallback(function()
    if pendingSave then
        local name = pendingSave
        pendingSave = nil
        local data = emu.createSavestate()
        local f = assert(io.open(PACK_DIR .. '/' .. name .. '.mss', 'wb'))
        f:write(data)
        f:close()
    end
end, emu.callbackType.exec, 0x8000, 0xFFFF)

local frame = 0
local phase = 'title'
local phaseStart = 0
local inp = {}
local savedIntro = false
local savedJump = false
local savedVillager = false
local shotFired = false
local missShots = 3

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if pendingStop and not pendingSave then emu.stop(0) return end
    frame = frame + 1
    inp = {}

    if phase == 'title' then
        if frame == 65 then
            saveState('title')
            phase = 'start_game_a'
            phaseStart = frame
        end

    elseif phase == 'start_game_a' then
        local dt = frame - phaseStart
        if dt <= 4 then
            inp = {a = true}
        elseif read(0x0024) == 0x00 then
            phase = 'intro'
            phaseStart = frame
        elseif dt > 60 then
            emu.stop(1)
        end

    elseif phase == 'intro' then
        local dt = frame - phaseStart
        local f35 = read(0x0035)
        if not savedIntro and (f35 == 0x0C or f35 == 0x0D) and read(0x0033) >= 48 then
            savedIntro = true
            saveState('barba_intro')
        end
        if not savedJump and f35 == 0x12 then
            savedJump = true
            saveState('barba_jump')
        end
        if read(0x0025) == 0x03 and read(0x0300) ~= 0 and read(0x0301) == 0x03 then
            phase = 'game_a_villager'
            phaseStart = frame
        elseif dt > 800 then
            emu.stop(1)
        end

    elseif phase == 'game_a_villager' then
        local dt = frame - phaseStart
        local tx, ty = read(0x0303), read(0x0302)
        if not savedVillager and ty <= 132 then
            savedVillager = true
            saveState('game_a')
        end
        if savedVillager and not shotFired and ty <= 132 and read(0x0301) == 0x03 then
            write(VH_CURSOR_X, tx)
            write(VH_CURSOR_Y, ty)
            inp = {a = true}
            shotFired = true
        end
        if shotFired and read(0x03A0) ~= 0 and (read(0x03A1) == 0x0C or read(0x03A1) == 0x0D) and read(0x03A2) <= 0x90 then
            saveState('barba_catch')
            phase = 'miss_for_link'
            phaseStart = frame
        elseif dt > 360 then
            emu.stop(1)
        end

    elseif phase == 'miss_for_link' then
        local dt = frame - phaseStart
        if read(0x0025) == 0x03 and read(0x0300) ~= 0 and read(0x0301) == 0x03 and read(0x00B9) ~= 0 then
            local tx = read(0x0303)
            write(VH_CURSOR_X, (tx < 128) and 224 or 16)
            write(VH_CURSOR_Y, 40)
            if missShots > 0 and (dt % 6 == 0) then
                inp = {b = true}
                missShots = missShots - 1
            end
        end
        if read(0x03A0) ~= 0 and read(VH_CUR_R1) == 16 and read(0x03A2) <= 0x90 then
            saveState('link_laugh')
            phase = 'game_b_reset'
            phaseStart = frame
            emu.reset()
        elseif dt > 640 then
            emu.stop(1)
        end

    elseif phase == 'game_b_reset' then
        local dt = frame - phaseStart
        if dt >= 65 and dt <= 68 then
            inp = {down = true}
        elseif dt >= 75 and dt <= 78 then
            inp = {a = true}
        elseif read(0x0024) == 0x00 and read(0x0025) == 0x03 and read(0x0300) ~= 0 and read(0x0301) == 0x03 and read(0x0302) <= 132 then
            saveState('game_b')
            phase = 'game_c_reset'
            phaseStart = frame
            emu.reset()
        elseif dt > 800 then
            emu.stop(1)
        end

    elseif phase == 'game_c_reset' then
        local dt = frame - phaseStart
        if dt >= 65 and dt <= 68 then
            inp = {down = true}
        elseif dt >= 75 and dt <= 78 then
            inp = {down = true}
        elseif dt >= 84 and dt <= 88 then
            inp = {a = true}
        elseif read(0x0024) == 0x00 and read(0x0025) == 0x0B and read(0x0300) ~= 0 and read(0x0301) == 0x03 and read(0x0302) <= 136 then
            saveState('game_c')
            pendingStop = true
        elseif dt > 600 then
            emu.stop(1)
        end
    end
end, emu.eventType.endFrame)
