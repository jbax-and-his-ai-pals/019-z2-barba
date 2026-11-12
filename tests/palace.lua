-- Controlled room entry into the original Palace 6 lava arena. The test skips
-- the overworld journey; room construction, gravity and collision are real.
dofile(TEST_DIR..'/newgame.lua')
local frame=0
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/palace.txt','w'))
local contacts=0
local standingY=nil
local stable=true
local jumped=false
local errors=0
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n')
    if not ok then errors=errors+1 end
end
emu.addMemoryCallback(function()if frame>1000 then contacts=contacts+1 end end,emu.callbackType.exec,0xE0A4)
emu.addEventCallback(function()
    local buttons=newGameInput(frame)
    buttons.right=(frame>=1300 and frame<1430)
    buttons.a=buttons.a or (frame>=1490 and frame<1510)
    emu.setInput(buttons,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        w(0x707,4);w(0x706,2);w(0x769,4);w(0x561,0x33)
        w(0x568,5);w(0x56B,6);w(0x56C,1);w(0x701,0);w(0x75C,0);w(0x704,0)
        w(0x736,0);w(0x73D,0);w(0x726,1)
        w(0x774,255);w(0x784,8)
    end
    if frame>=1000 and frame%100==0 then
        report:write(string.format('%d mode %d world %d room %d bank %d y %d state %d\n',
            frame,r(0x736),r(0x707),r(0x561),r(0x769),r(0x29),r(0xB5)));report:flush()
    end
    if frame==1300 then
        screenshot('palace-lava-room')
        for page=0,3 do
            local count=0
            for offset=0,0xCF do if r(0x6000+page*0xD0+offset)==0x83 then count=count+1 end end
            report:write('lava page '..page..' count '..count..'\n')
        end
        check(r(0x736)==11 and r(0x76E)==24,'original Palace 6 room and graphics load')
    end
    if frame>=1450 and frame<1485 then
        if not standingY then standingY=r(0x29) end
        if math.abs(r(0x29)-standingY)>1 then stable=false end
    end
    if frame==1485 then
        screenshot('barba-on-lava')
        check(contacts>10 and r(0xB5)==1,'repeated lava contact leaves player alive')
        check(stable and r(0x479)==0,'dragon settles on lava surface without sinking')
    end
    if frame>=1490 and frame<1530 and r(0x29)<standingY-4 then jumped=true end
    if frame==1580 then
        screenshot('barba-lava-after-jump')
        check(jumped,'jump lifts dragon out of lava')
        check(r(0xB5)==1 and r(0x736)==11,'player survives jump and return to lava')
        report:write('hazard contacts '..contacts..'\nRESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
        report:close();stopScenario(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
