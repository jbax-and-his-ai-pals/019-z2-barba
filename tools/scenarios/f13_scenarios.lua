-- Generate save states for standalone Friday the 13th: Barba Edition (play/f13-barba.nes).
local pendingCapture = nil

local function saveStateAndShot(id)
    local data = emu.createSavestate()
    local f = assert(io.open(PACK_DIR .. '/' .. id .. '.mss', 'wb'))
    f:write(data)
    f:close()
    local png = emu.takeScreenshot()
    local pf = assert(io.open(PACK_DIR .. '/' .. id .. '.png', 'wb'))
    pf:write(png)
    pf:close()
end

emu.addMemoryCallback(function()
    if pendingCapture then
        local id = pendingCapture
        pendingCapture = nil
        saveStateAndShot(id)
    end
end, emu.callbackType.exec, 0x8000, 0xFFFF)

local f = 0
local inp = {}

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    f = f + 1
    inp = {}
    if f == 360 then
        pendingCapture = 'title'
    elseif f >= 380 and f < 385 then
        inp = {start = true}
    elseif f >= 460 and f < 465 then
        inp = {start = true}
    elseif f == 520 then
        pendingCapture = 'camp-map'
    elseif f >= 540 and f < 545 then
        inp = {start = true}
    elseif f == 960 then
        pendingCapture = 'exterior-path'
    elseif f >= 970 and f < 980 then
        inp = {up = true}
    elseif f == 1030 then
        pendingCapture = 'cabin-inside'
    elseif f == 1040 then
        emu.stop(0)
    end
end, emu.eventType.endFrame)
