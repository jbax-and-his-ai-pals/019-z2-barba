-- Verify Palace 6 "Lava Link" boss: Link palette, Link sprite art, and Spear (05) sword beams.
dofile(TEST_DIR..'/newgame.lua')
local frame=0
local mem=emu.memType.nesMemory
local pal=emu.memType.nesPaletteRam
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/link_boss.txt','w'))
local errors=0
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n')
    if not ok then errors=errors+1 end
end

local sawBoss=false
local sawSpear=false
local sawFlame=false
local bossPaletteOk=false
local shotBeamPng=false
local bossSlot=nil
local bossStartHp=nil
local bossMinHp=255

emu.addEventCallback(function()
    local buttons=newGameInput(frame)
    -- Wait for Lava Link to fire a sword beam first, then hop/aim at Lava Link's head.
    if sawSpear and bossSlot~=nil then
        local bx=r(0x4E+bossSlot)
        local by=r(0x2A+bossSlot)
        local px=r(0x4D)
        local py=r(0x29)
        if bx<px-16 then buttons.left=(frame%16<2)
        elseif bx>px+16 then buttons.right=(frame%16<2) end
        buttons.a=buttons.a or (py>by+8 and frame%40<20)
        buttons.b=(math.abs(py-by)<=20 and frame%10<3)
    end
    emu.setInput(buttons,0)
end,emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        w(0x707,4);w(0x706,2);w(0x769,4);w(0x561,0x3A)
        w(0x568,5);w(0x56B,6);w(0x56C,1);w(0x701,0);w(0x75C,1);w(0x704,0)
        w(0x736,0);w(0x73D,0);w(0x726,1)
        w(0x774,255);w(0x784,8);w(0x777,8);w(0x778,8)
    end
    if frame>1200 then
        if frame%60==0 then w(0x774,255) end
        for slot=0,5 do
            local eid=r(0xA1+slot)
            if r(0xB6+slot)>0 and (eid==0x21 or eid==0x22) then
                sawBoss=true
                bossSlot=slot
                local hp=r(0xC2+slot)
                if bossStartHp==nil and hp>0 and hp<255 then bossStartHp=hp end
                if hp<bossMinHp then bossMinHp=hp end
            end
        end
        for p=0,5 do
            local kind=r(0x87+p)
            if kind==0x05 then
                sawSpear=true
                if not shotBeamPng then
                    shotBeamPng=true
                    screenshot('link_boss_beam')
                end
            elseif kind==0x04 then
                sawFlame=true
            end
        end
        if r(0x0499)>=2 then
            local c1,c2,c3=emu.read(0x15,pal),emu.read(0x16,pal),emu.read(0x17,pal)
            if c1==0x18 and c2==0x36 and c3==0x2A then
                bossPaletteOk=true
            end
        end
    end
    if frame==1600 then
        screenshot('link_boss_rising')
    end
    if frame==2500 then
        local c1,c2,c3=emu.read(0x15,pal),emu.read(0x16,pal),emu.read(0x17,pal)
        report:write(string.format('sp_pal1=%02X %02X %02X hp_start=%s hp_min=%d\n',
            c1,c2,c3,tostring(bossStartHp),bossMinHp))
        check(sawBoss,'Palace 6 boss (0x21) spawned')
        check(bossPaletteOk,'Sprite palette 1 switched to Link (18 36 2A)')
        check(sawSpear,'Lava Link spawned Spear/sword-beam projectile (05)')
        check(not sawFlame,'Lava Link did not spawn Barba flame (04)')
        check(bossStartHp~=nil and bossMinHp<bossStartHp,'Barba fireballs damaged Lava Link')
        report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
        report:close()
        emu.stop()
    end
end,emu.eventType.endFrame)
