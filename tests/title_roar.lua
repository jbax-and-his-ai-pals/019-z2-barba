-- Title screen: the jaw no longer triggers the fireball SFX ($ED bit 6); every 4th
-- full jaw opening starts the noise roar (ROAR_TIMER $05F0), which then counts down.
local frame, starts, sfx, maxTimer, lastTimer, noiseWrites = 0, 0, 0, 0, 0, 0
local function rd(a) return emu.read(a, emu.memType.nesDebug) end
emu.addMemoryCallback(function() noiseWrites = noiseWrites + 1 end, emu.callbackType.write, 0x400E, 0x400E)
-- Vanilla's title sets $ED bit 6 on its own; count only writes made by Barba's title code ($A54F-$A5E7).
emu.addMemoryCallback(function(addr, value)
    local pc = emu.getState()['cpu.pc']
    if pc >= 0xA54F and pc < 0xA5E8 then sfx = sfx + 1 end
end, emu.callbackType.write, 0xED, 0xED)
local function endFrame()
    frame = frame + 1
    local t = rd(0x05F0)
    if t > lastTimer then starts = starts + 1 end
    if t > maxTimer then maxTimer = t end
    lastTimer = t
    if frame == 1500 then
        local f = assert(io.open(OUTPUT_DIR..'/title-roar.txt', 'w'))
        local ok = starts >= 1 and maxTimer <= 0x30 and sfx == 0
        f:write(string.format('roar starts=%d maxTimer=%d barbaSfxWrites=%d noiseWrites=%d jawCount=%d\n', starts, maxTimer, sfx, noiseWrites, rd(0x05FA)))
        f:write((starts >= 1 and 'PASS' or 'FAIL')..' roar started on title\n')
        f:write((sfx == 0 and 'PASS' or 'FAIL')..' no fireball SFX on title\n')
        f:write('RESULT '..(ok and 'PASS' or 'FAIL')..'\n')
        f:close()
        local stop = emu.exit or emu.stop
        stop(0)
    end
end
emu.addEventCallback(endFrame, emu.eventType.endFrame)
