-- Save-state generator for standalone Super Barba Bros. (play/standalone/smb-barba.nes).
local mem = emu.memType.nesMemory
local function r(a) return emu.read(a, mem) end
local function w(a, v) emu.write(a, v, mem) end

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

local mmc3Sel = 0
local chrBanks = {[0]=0, [1]=0, [2]=0, [3]=0}
local axeRoarHits = 0

emu.addMemoryCallback(function(_, v) mmc3Sel = v & 0x07 end, emu.callbackType.write, 0x8000)
emu.addMemoryCallback(function(_, v)
    if mmc3Sel <= 3 then chrBanks[mmc3Sel] = v end
end, emu.callbackType.write, 0x8001)
emu.addMemoryCallback(function() axeRoarHits = axeRoarHits + 1 end, emu.callbackType.exec, 0xDE0E)

local frame = 0
local phase = 'title'
local pStart = 0
local inp = {}
local castleActive = false
local lastCastlePos = -1
local castleStuck = 0
local axeStart = nil

local function setPhase(p)
    phase = p
    pStart = frame
    castleActive = false
end

local function placePowerupOnPlayer(kind)
    w(0x0014, 1)
    w(0x001B, 0x2E)
    w(0x0039, kind)
    w(0x0023, 0x06)
    w(0x0073, r(0x006D))
    w(0x008C, r(0x0086))
    w(0x00BB, 0x01)
    w(0x00D4, r(0x00CE))
    w(0x03D6, 0x00)
    w(0x06C3, 0x00)
end

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if pendingStop and not pendingSave then emu.stop(0) return end
    frame = frame + 1
    local elapsed = frame - pStart
    inp = {}

    if phase == 'title' then
        if frame == 45 then
            saveState('title')
            setPhase('press_start')
        end

    elseif phase == 'press_start' then
        if elapsed < 4 then inp = {start = true} end
        if r(0x0770) == 1 and r(0x0772) == 3 and elapsed > 20 then
            setPhase('w1_wyrmling')
        elseif elapsed > 240 then
            emu.stop(1)
        end

    elseif phase == 'w1_wyrmling' then
        if elapsed < 90 then inp = {right = true} end
        if elapsed == 90 then
            saveState('w1_wyrmling')
            setPhase('collect_mushroom')
        end

    elseif phase == 'collect_mushroom' then
        if elapsed == 1 then
            placePowerupOnPlayer(0)
        elseif r(0x0756) == 0 then
            w(0x0073, r(0x006D)); w(0x008C, r(0x0086)); w(0x00BB, 1); w(0x00D4, r(0x00CE))
        end
        if r(0x0756) == 1 and r(0x7C00) == 0 and chrBanks[0] == 2 and elapsed > 80 then
            saveState('super_barba')
            setPhase('collect_flower')
        elseif elapsed > 240 then
            emu.stop(1)
        end

    elseif phase == 'collect_flower' then
        if elapsed == 1 then
            placePowerupOnPlayer(1)
        elseif r(0x0756) < 2 then
            w(0x0073, r(0x006D)); w(0x008C, r(0x0086)); w(0x00BB, 1); w(0x00D4, r(0x00CE))
        end
        if r(0x0756) == 2 and elapsed > 20 and chrBanks[0] == 12 then
            w(0x7C00, 0); w(0x7C05, 0)
            saveState('inferno_barba')
            setPhase('z2_enemies')
        elseif elapsed > 180 then
            emu.stop(1)
        end

    elseif phase == 'z2_enemies' then
        if elapsed <= 4 then
            w(0x0024, 0); w(0x0025, 0)
            local baseX = r(0x006D) * 256 + r(0x0086)
            local function setX(slot, dx)
                local wx = baseX + dx
                w(0x006E + slot, math.floor(wx / 256))
                w(0x0087 + slot, wx % 256)
            end
            w(0x000F, 1); w(0x0016, 0x00); w(0x001E, 0); setX(0, 24);  w(0x00B6, 1); w(0x00CF, 0xB0); w(0x0046, 2); w(0x03C5, 1)
            w(0x0010, 1); w(0x0017, 0x01); w(0x001F, 0); setX(1, 48);  w(0x00B7, 1); w(0x00D0, 0xB0); w(0x0047, 2); w(0x03C6, 2)
            w(0x0011, 1); w(0x0018, 0x11); w(0x0020, 0); setX(2, 74);  w(0x00B8, 1); w(0x00D1, 0x70); w(0x0048, 2); w(0x03C7, 1)
            w(0x0012, 1); w(0x0019, 0x0D); w(0x0021, 0); setX(3, 100); w(0x00B9, 1); w(0x00D2, 0xB0); w(0x005B, 0x80); w(0x03C8, 1)
            w(0x0013, 1); w(0x001A, 0x12); w(0x0022, 0); setX(4, 126); w(0x00BA, 1); w(0x00D3, 0x90); w(0x004A, 2); w(0x03C9, 2)
        elseif elapsed == 8 then
            saveState('z2_enemies')
            w(0x075F, 0x00); w(0x075C, 0x03); w(0x0760, 0x00)
            w(0x0750, 0x60); w(0x074E, 0x03); w(0x07A0, 0x01)
            w(0x0772, 0x00); w(0x0770, 0x01)
            setPhase('castle_run')
        end

    elseif phase == 'castle_run' then
        if r(0x0772) == 3 and chrBanks[1] == 18 then
            if not castleActive then
                castleActive = true
                pStart = frame
                elapsed = 0
            end
            w(0x079E, 0x10)
            if r(0x00CE) > 0xC4 then w(0x00CE, 0x70); w(0x009F, 0x00) end
            local curPos = r(0x071A) * 256 + r(0x0086)
            if curPos == lastCastlePos then
                castleStuck = castleStuck + 1
                if castleStuck == 20 then
                    local ny = r(0x00CE) - 28
                    if ny < 0x48 then ny = 0xB0 end
                    w(0x00CE, ny); w(0x009F, 0x00); castleStuck = 0
                end
            else
                lastCastlePos = curPos; castleStuck = 0
            end
            inp = {right = true, b = true}
            if (elapsed % 28) < 12 then inp.a = true end
            local foundBowser = false
            for s = 0, 4 do
                if r(0x000F + s) ~= 0 and r(0x0016 + s) == 0x2D then foundBowser = true break end
            end
            if foundBowser and r(0x071A) >= 0x07 then
                w(0x7C00, 0)
                setPhase('castle_boss')
            elseif elapsed > 2000 then
                emu.stop(1)
            end
        elseif elapsed > 240 then
            emu.stop(1)
        end

    elseif phase == 'castle_boss' then
        w(0x079E, 0x10); w(0x0756, 0x02); w(0x0754, 0x00); w(0x0714, 0x00)
        if r(0x00CE) > 0xC4 then w(0x00CE, 0x80); w(0x009F, 0x00) end
        if r(0x006D) < 8 or r(0x0086) < 0x18 then inp.right = true end
        if elapsed == 60 then
            w(0x079E, 0x00) -- remove invincibility for real playtest
            saveState('castle_boss')
            setPhase('grab_axe')
        end

    elseif phase == 'grab_axe' then
        w(0x079E, 0x10); w(0x0754, 0x00)
        if axeRoarHits > 0 and not axeStart then axeStart = frame end
        if not axeStart then
            inp = {right = true}
            if r(0x00CE) > 0xB8 then w(0x00CE, 0x80); w(0x009F, 0x00) end
            if (elapsed % 30) < 10 then inp.a = true end
        end
        if axeStart and (frame - axeStart) == 140 then
            saveState('caged_fairy')
            pendingStop = true
        elseif elapsed > 480 then
            emu.stop(1)
        end
    end
end, emu.eventType.endFrame)
