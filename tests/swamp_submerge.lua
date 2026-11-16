-- Live West Hyrule swamp encounter test: Barba walks into swamp water,
-- submerges lower body like lava (GEOMETRY bit 2, DRAW_TOP = actor Y, bottom
-- OAM row hidden), and restores full height when jumping.
dofile(TEST_DIR..'/newgame.lua')
local frame=0
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/swamp-submerge.txt','w'))
local errors=0
local function check(ok,msg)
    report:write((ok and 'PASS ' or 'FAIL ')..msg..'\n')
    if not ok then errors=errors+1 end
end
local sawSwamp,sawAir=false,false
local submergedHeadY,submergedBotY,airBotY=nil,nil,nil
emu.addEventCallback(function()
    local buttons=newGameInput(frame)
    if frame>=1150 and frame<1450 then buttons.right=true end
    if frame>=1470 and frame<1490 then buttons.a=true end
    emu.setInput(buttons,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        w(0x707,0);w(0x706,0);w(0x769,1);w(0x748,0xFF);w(0x563,7)
        w(0x701,0);w(0x75C,0);w(0x704,0)
        w(0x736,0);w(0x73D,0);w(0x726,1)
        w(0x774,255);w(0x784,8)
    end
    if frame>=1200 and frame<=1460 then
        if r(0x752)==0x20 and r(0x479)==0 and (r(0x5F6)&4)~=0 then
            sawSwamp=true
            submergedHeadY=r(0x204)
            submergedBotY=r(0x214)
        end
    end
    if frame>=1475 and frame<=1520 then
        if r(0x479)~=0 and (r(0x5F6)&4)==0 and r(0x214)~=0xF8 then
            sawAir=true
            airBotY=r(0x214)
        end
    end
    if frame==1540 then
        check(sawSwamp,'grounded in swamp sets $0752=$20 and GEOMETRY bit 2')
        check(submergedBotY==0xF8,'bottom OAM row is hidden while submerged in swamp (got '..tostring(submergedBotY)..')')
        check(submergedHeadY~=nil and submergedHeadY~=0xF8,'head OAM row stays visible while submerged (got '..tostring(submergedHeadY)..')')
        check(sawAir,'jumping in swamp restores full height and bottom OAM row (got '..tostring(airBotY)..')')
        report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
        report:close();stopScenario(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
