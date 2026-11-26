-- Overworld Fairy -> Wyrmling: spawn an overworld fairy (type 3) and verify
-- both animation frames ($81/$83 and $85/$87) with palette 3 and capture screenshots.
dofile(TEST_DIR..'/newgame.lua')
local frame = 0
local mem = emu.memType.nesMemory
local function read(address) return emu.read(address, mem) end
local function write(address, val) emu.write(address, val, mem) end
local report = assert(io.open(OUTPUT_DIR..'/overworld-fairy.txt', 'w'))
local errors = 0
local worldAt = nil
local seen = {}

local function check(condition, message)
    report:write((condition and 'PASS ' or 'FAIL ')..message..'\n')
    if not condition then errors = errors + 1 end
end

local function input()
    local buttons = newGameInput(frame)
    if frame >= 1000 and worldAt == nil and frame >= 1250 and frame < 2050 then
        buttons.right = true
    end
    emu.setInput(buttons, 0)
end

local function tick()
    frame = frame + 1
    if frame > 1250 and worldAt == nil and read(0x736) == 5 then
        worldAt = frame
    end
    if worldAt then
        local rel = frame - worldAt
        if rel == 10 then
            write(0x050E, 0x60)
            write(0x82, 3)
            write(0x2A, (read(0x7F) + 0x70) % 256)
            write(0x4E, (read(0xFD) + 0xA0) % 256)
            write(0x056D, 0)
            write(0x0575, 0)
        elseif rel >= 12 and rel < 40 then
            local y = read(0x0280)
            local tL = read(0x0281)
            local tR = read(0x0285)
            local attr = read(0x0282) & 3
            if y < 0xF0 and tL == 0x81 and tR == 0x83 and attr == 3 then
                if not seen.f0 then
                    seen.f0 = true
                    screenshot('ow-fairy-0')
                end
            elseif y < 0xF0 and tL == 0x85 and tR == 0x87 and attr == 3 then
                if not seen.f1 then
                    seen.f1 = true
                    screenshot('ow-fairy-1')
                end
            end
        elseif rel == 42 then
            check(seen.f0, 'overworld fairy frame 0 uses tiles $81/$83 with palette 3')
            check(seen.f1, 'overworld fairy frame 1 uses tiles $85/$87 with palette 3')
            report:write('RESULT '..(errors == 0 and 'PASS' or 'FAIL')..'\n')
            report:close()
            stopScenario(errors == 0 and 0 or 1)
        end
    end
    if frame == 2400 then
        check(false, 'reached overworld')
        report:write('RESULT FAIL\n')
        report:close()
        stopScenario(1)
    end
end

emu.addEventCallback(input, emu.eventType.inputPolled)
emu.addEventCallback(tick, emu.eventType.endFrame)
