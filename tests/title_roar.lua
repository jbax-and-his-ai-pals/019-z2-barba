-- Title screen: the jaw no longer triggers the fireball SFX ($ED bit 6); every 4th
-- full jaw opening starts the noise roar (ROAR_TIMER $05F0), which then counts down.
local frame, starts, sfx, maxTimer, lastTimer, noiseWrites = 0, 0, 0, 0, 0, 0
local function rd(a) return emu.read(a, emu.memType.nesDebug) end
local jaws, badHead = {}, false
emu.addMemoryCallback(function()
    if rd(0x8506)~=0x2F or rd(0x21C)~=0x7F then return end
    local first=rd(0x21D)
    local expected=({[0x00]={0x02,0x04},[0x1A]={0x1C,0x04},[0x1E]={0x20,0x04}})[first]
    if not expected or rd(0x221)~=expected[1] or rd(0x23D)~=expected[2] then badHead=true end
    jaws[first]=true
end,emu.callbackType.exec,0xA58E)
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
    if jaws[0x1E] and not jaws.captured and rd(0x21D)==0x1E then
        jaws.captured=true
        local shot=assert(io.open(OUTPUT_DIR..'/title-open.png','wb'))
        shot:write(emu.takeScreenshot());shot:close()
    end
    if frame == 1500 then
        local f = assert(io.open(OUTPUT_DIR..'/title-roar.txt', 'w'))
        local headOk=jaws[0] and jaws[0x1A] and jaws[0x1E] and not badHead
        local ok = starts >= 1 and maxTimer <= 0x30 and sfx == 0 and headOk
        f:write(string.format('roar starts=%d maxTimer=%d barbaSfxWrites=%d noiseWrites=%d jawCount=%d\n', starts, maxTimer, sfx, noiseWrites, rd(0x05FA)))
        f:write((starts >= 1 and 'PASS' or 'FAIL')..' roar started on title\n')
        f:write((sfx == 0 and 'PASS' or 'FAIL')..' no fireball SFX on title\n')
        f:write((headOk and 'PASS' or 'FAIL')..' all three jaws retain the complete head\n')
        f:write('RESULT '..(ok and 'PASS' or 'FAIL')..'\n')
        f:close()
        local stop = emu.exit or emu.stop
        stop(ok and 0 or 1)
    end
end
emu.addEventCallback(endFrame, emu.eventType.endFrame)
