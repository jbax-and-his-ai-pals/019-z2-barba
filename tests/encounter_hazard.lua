-- Outside-palace encounter water surface interaction:
-- West Hyrule water bridge (world 0, room $01, $0707 = 0).
dofile(TEST_DIR..'/newgame.lua')
local frame=0
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/encounter_hazard.txt','w'))
local contacts=0
local standingY=nil
local stable=true
local errors=0
local settledAt=nil
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n')
    if not ok then errors=errors+1 end
end
emu.addMemoryCallback(function()
    if frame>1000 then contacts=contacts+1 end
end,emu.callbackType.exec,0xE0A4)
emu.addEventCallback(function()
    local buttons=newGameInput(frame)
    buttons.right=(frame>=1100 and frame<1160)
    buttons.down=(settledAt~=nil and frame>=settledAt+40 and frame<settledAt+44)
    emu.setInput(buttons,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        -- Enter West Hyrule water bridge (world 0, region 0, bank 1, room $01)
        w(0x707,0);w(0x706,0);w(0x769,1);w(0x561,0x01)
        w(0x568,0);w(0x56B,0);w(0x56C,0);w(0x701,0);w(0x75C,0);w(0x704,0)
        w(0x736,7);w(0x73D,0);w(0x726,1)
        w(0x774,255);w(0x784,8)
    end
    if frame==1100 then
        check(r(0x736)==11 and r(0x707)==0 and r(0x561)==0x01,'water bridge room loaded in world 0')
    end
    if frame==1220 then
        -- Drop Barba below the bridge so she lands directly on the water surface ($80).
        w(0x29,0x98)
    end
    if frame>=1220 then
        if not settledAt and contacts>=10 and r(0x479)==0 then
            settledAt=frame
            standingY=r(0x29)
        end
        if settledAt then
            local rel=frame-settledAt
            if rel>=1 and rel<39 then
                if math.abs(r(0x29)-standingY)>1 then stable=false end
            end
            if rel==39 then
                screenshot('barba-on-water')
                check(contacts>10 and r(0xB5)==1,'repeated water contact leaves player alive')
                check(stable and r(0x479)==0,'dragon settles on water surface without sinking')
                check((r(0x5F6)&4)~=0,'standing on water sets submerged geometry bit')
            end
            if rel==43 then
                check((r(0x5F6)&6)==0 and r(0x20C)<0xF8,'crouching on water keeps full head row above water')
                check(r(0xB5)==1 and r(0x736)==11,'player survives water interaction in world 0')
                report:write('hazard contacts '..contacts..'\nRESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
                report:close();stopScenario(errors==0 and 0 or 1)
            end
        end
    end
    if frame==2500 then
        check(false,string.format('timed out waiting for water hazard contact (contacts=%d x=%03X y=%02X air=%d mode=%02X)',contacts,r(0x3B)*256+r(0x4D),r(0x29),r(0x479),r(0x736)))
        report:write('RESULT FAIL\n');report:close();stopScenario(1)
    end
end,emu.eventType.endFrame)
