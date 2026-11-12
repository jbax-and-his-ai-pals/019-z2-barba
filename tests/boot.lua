-- Mesen 2 headless smoke check. Run from the repository root.
local frame = 0
local function endFrame()
    frame = frame + 1
    if frame == 120 then
        local f = assert(io.open(OUTPUT_DIR..'/boot.png', 'wb'))
        f:write(emu.takeScreenshot())
        f:close()
        local report = assert(io.open(OUTPUT_DIR..'/boot-state.txt', 'w'))
        for k, v in pairs(emu.getState()) do report:write(tostring(k)..'='..tostring(v)..'\n') end
        report:close()
        local stop = emu.exit or emu.stop
        stop(0)
    end
end
emu.addEventCallback(endFrame, emu.eventType.endFrame)
