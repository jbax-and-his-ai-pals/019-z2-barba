-- Verify full 24x48 Barba body + trail + Z2 5-shot fireball volley in Friday the 13th exterior.
local mem = emu.memType.nesMemory
local oam = emu.memType.nesSpriteRam
local ppu = emu.memType.nesPpuDebug
local function r(a) return emu.read(a, mem) end
local function w(a, v) emu.write(a, v, mem) end

local report = assert(io.open(OUTPUT_DIR .. '/f13-barba-gameplay.txt', 'w'))
local failed = false
local function check(cond, msg)
    if cond then
        report:write('PASS ' .. msg .. '\n')
    else
        report:write('FAIL ' .. msg .. '\n')
        failed = true
    end
end

local f = 0
local inp = {}
local shotFrames = {}
local prevRem = 0
local prevState = 0
local maxLiveFireballs = 0
local sawVolleyWhileMoving = false
local sawNativeWeapon = false
local killedByVolley = false
local savedZ28, savedZ30 = nil, nil
local cabinPhase = false
local cabinTimer = 0
local done = false

emu.addEventCallback(function()
    emu.setInput(inp, 0)
end, emu.eventType.inputPolled)

local function oamStats()
    local minY, maxY = 255, 0
    local minX, maxX = 255, 0
    local fireCount = 0
    local barbaCount = 0
    local ghostBodyCount = 0
    for i = 0, 252, 4 do
        local y = emu.read(i, oam)
        local t = emu.read(i + 1, oam)
        local a = emu.read(i + 2, oam)
        local x = emu.read(i + 3, oam)
        if y >= 0x30 and y < 0xEC then
            if t >= 0x4D and t <= 0x52 and (a & 0x03) == 3 then
                ghostBodyCount = ghostBodyCount + 1
            elseif t >= 0x45 and t <= 0x62 then
                barbaCount = barbaCount + 1
                if y < minY then minY = y end
                if y + 8 > maxY then maxY = y + 8 end
                if x < minX then minX = x end
                if x + 8 > maxX then maxX = x + 8 end
            elseif t == 0x15 then
                fireCount = fireCount + 1
            end
        end
    end
    return barbaCount, minY, maxY, minX, maxX, fireCount, ghostBodyCount
end

emu.addEventCallback(function()
    if done then return end
    f = f + 1
    inp = {}
    if (f >= 380 and f < 385) or (f >= 460 and f < 465) or (f >= 540 and f < 545) then
        inp = {start = true}
    elseif f == 960 then
        for s = 2, 5 do
            if r(0x0420 + s) ~= 0 and r(0x0328 + s) + r(0x0330 + s) > 0 then
                savedZ28, savedZ30 = r(0x0328 + s), r(0x0330 + s)
                break
            end
        end
        local bc, minY, maxY, minX, maxX, _, ghostStand = oamStats()
        check(bc >= 20, 'Standing 24x48 Barba + trail uses >= 20 OAM sprites (' .. bc .. ')')
        check(ghostStand == 0, 'No vanilla counselor body ($4D-$52 pal 3) over standing Barba (' .. ghostStand .. ')')
        check(maxY - minY >= 44, 'Standing Barba spans >= 44px height (' .. (maxY - minY) .. 'px)')
        check(maxX - minX >= 48, 'Barba + trail spans >= 48px width (' .. (maxX - minX) .. 'px)')
        check(emu.read(0x3F1F, ppu) == 0x0F, string.format('Sprite Palette 3 color 3 is $0F (got %02X)', emu.read(0x3F1F, ppu)))
        check(emu.read(0x3F15, ppu) == 0x16 and emu.read(0x3F16, ppu) == 0x27 and emu.read(0x3F17, ppu) == 0x30,
            'Sprite Palette 1 matches Z2 Palace 1 Wosu ($0F/$16/$27/$30)')
        local png = emu.takeScreenshot()
        local pf = assert(io.open(OUTPUT_DIR .. '/f13-barba-stand.png', 'wb'))
        pf:write(png); pf:close()
    elseif f >= 965 and f < 990 then
        if f == 965 then
            -- Ensure Barba is grounded and invulnerable during crouch test
            w(0x0420, 0); w(0x0308, 0); w(0x0488, 0x50); w(0x0348, 0)
        end
        inp = {down = true}
        if f == 984 then
            local bc, minY, maxY, _, _, _, ghostCrouch = oamStats()
            check(bc >= 14, 'Crouching Barba + trail renders (' .. bc .. ' sprites)')
            check(ghostCrouch == 0, 'No vanilla counselor body ($4D-$52 pal 3) over crouching Barba (' .. ghostCrouch .. ')')
            check(maxY - minY <= 28 and maxY - minY >= 20, 'Crouching Barba folds to ~24px height (' .. (maxY - minY) .. 'px)')
            local png = emu.takeScreenshot()
            local pf = assert(io.open(OUTPUT_DIR .. '/f13-barba-crouch.png', 'wb'))
            pf:write(png); pf:close()
        end
    elseif f >= 1005 and f <= 1085 then
        -- Hold B + Right: should fire exactly 5 shots on 8-frame cadence WITHOUT locking movement or repeating while held!
        inp = {b = true, right = true}
        if f == 1005 then
            for slot = 2, 5 do w(0x0420 + slot, 0) end
        end
        if r(0x0576) ~= 0 or r(0x0420) == 4 or r(0x0420) == 5 then
            sawNativeWeapon = true
        end
        local st = r(0x7C00)
        local rem = r(0x7C01)
        if (st == 1 and prevState == 0) or (rem < prevRem) then
            table.insert(shotFrames, f)
        end
        prevState = st
        prevRem = rem
        local live = 0
        for s = 0, 4 do
            if r(0x7C10 + s) > 0 then live = live + 1 end
        end
        if live > maxLiveFireballs then maxLiveFireballs = live end
        if live > 0 and r(0x0458) > 0 then sawVolleyWhileMoving = true end
        if f == 1038 then
            local png = emu.takeScreenshot()
            local pf = assert(io.open(OUTPUT_DIR .. '/f13-barba-volley.png', 'wb'))
            pf:write(png); pf:close()
        end
    elseif f == 1095 then
        check(#shotFrames == 5, 'Holding B fired exactly 5-shot volley (' .. #shotFrames .. ' shots: ' .. table.concat(shotFrames, ',') .. ')')
        if #shotFrames == 5 then
            local cadOk = true
            for i = 2, 5 do
                if shotFrames[i] - shotFrames[i - 1] < 8 then cadOk = false end
            end
            check(cadOk, 'Volley cadence >= 8 frames between shots')
        end
        check(maxLiveFireballs >= 3, 'At least 3 concurrent fireballs in flight (' .. maxLiveFireballs .. ')')
        check(sawVolleyWhileMoving, 'Barba can move freely during fireball volley')
        check(not sawNativeWeapon, 'Regular F13 attack never triggered')
        -- Place an active enemy right in front of Barba's diagonal line and fire a volley!
        for s = 2, 5 do
            if (r(0x0470 + s) & 0x08) ~= 0 or r(0x0480 + s) > 0 then killedByVolley = true end
        end
        w(0x0420, 0); w(0x0308, 0); w(0x0488, 0x40); w(0x0348, 0)
        local targetSlot = nil
        for s = 2, 5 do
            if r(0x0420 + s) ~= 0 and (r(0x0470 + s) & 0x08) == 0 then
                targetSlot = s
                break
            end
        end
        if not targetSlot and savedZ28 then
            targetSlot = 2
            w(0x0420 + 2, 3); w(0x0478 + 2, 0); w(0x0470 + 2, 0)
            w(0x0328 + 2, savedZ28); w(0x0330 + 2, savedZ30)
        end
        if targetSlot then
            w(0x0480 + targetSlot, 0)
            w(0x0360 + targetSlot, r(0x0360) + 28)
            w(0x0368 + targetSlot, 0)
            w(0x0370 + targetSlot, r(0x0370))
            w(0x0378 + targetSlot, 0)
        end
    elseif f >= 1100 and f < 1145 then
        inp = {b = (f >= 1100 and f < 1105)}
        for s = 2, 5 do
            if (r(0x0470 + s) & 0x08) ~= 0 or r(0x0480 + s) > 0 then killedByVolley = true end
        end
    elseif f == 1150 then
        local killed = killedByVolley
        for s = 2, 5 do
            if (r(0x0470 + s) & 0x08) ~= 0 or r(0x0480 + s) > 0 then killed = true end
        end
        check(killed, 'Z2 fireball volley damaged/killed enemy in F13')
        cabinPhase = true
        cabinTimer = 0
    elseif cabinPhase then
        cabinTimer = cabinTimer + 1
        if r(0x38) == 2 and r(0x37) == 2 then
            if cabinTimer < 1000 then cabinTimer = 1000 end
            if cabinTimer == 1025 then
                check(r(0x05A2) ~= 0 and r(0x05A0) ~= 0,
                    string.format('Cabin entry after fireball breath loaded valid cabin ID ($05A2=%02X $05A0=%02X)', r(0x05A2), r(0x05A0)))
                check(r(0x7C0B) == 0 and r(0x7C0C) == 0, 'Interior cleared BARBA_R0_0/1 overrides')
                done = true
                report:write('RESULT ' .. (failed and 'FAIL' or 'PASS') .. '\n')
                report:close()
                emu.stop(failed and 1 or 0)
            end
        else
            inp = {
                right = true,
                up = ((cabinTimer % 12) < 6),
                b = ((cabinTimer % 24) == 2),
            }
            if cabinTimer > 1000 then
                check(false, string.format('Timed out entering cabin ($38=%02X $37=%02X $44=%02X $45=%02X $0420=%02X)', r(0x38), r(0x37), r(0x44), r(0x45), r(0x0420)))
                done = true
                report:write('RESULT ' .. (failed and 'FAIL' or 'PASS') .. '\n')
                report:close()
                emu.stop(1)
            end
        end
    end
end, emu.eventType.endFrame)
