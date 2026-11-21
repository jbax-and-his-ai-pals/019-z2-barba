-- Rauru's page-2 door shares a PPU address with the grass on page 0.
dofile(TEST_DIR..'/newgame.lua')
local mem,ppu=emu.memType.nesMemory,emu.memType.nesPpuMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local frame,errors=0,0
local grass,door
local f=assert(io.open(OUTPUT_DIR..'/rauru_rogue_door.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n')
    f:flush()
    if not ok then errors=errors+1 end
end
local function tiles(nt)
    local result={}
    for row=0,5 do
        for col=0,1 do
            result[#result+1]=string.char(emu.read(nt+row*32+col,ppu))
        end
    end
    return table.concat(result)
end
local function closeOpener(page)
    -- Resume a house-opener one tick before its native final close.
    local slot=5
    w(0xB6+slot,1);w(0xA1+slot,0x14);w(0xAF+slot,0xAF)
    w(0x5BD+slot,0);w(0x5C3+slot,0)
    w(0x599+slot,0x20);w(0x59F+slot,page)
    w(0x4E+slot,0x20);w(0x3C+slot,page);w(0x2A+slot,0xB0);w(0x71+slot,0)
end
emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then b={right=frame>=1220 and frame<1540} end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        w(0x707,1);w(0x706,0);w(0x769,3);w(0x561,1)
        w(0x701,0);w(0x75C,0);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1)
    elseif frame==1150 then
        check(r(0x561)==1 and r(0x736)==11 and r(0x72A)==0,'camera starts on Rauru west street')
        check(r(0x60A2)~=0x8B and r(0x6242)==0x8B,'page 0 has grass where page 2 has a real door')
        grass=tiles(0x2284)
        closeOpener(2)
    elseif frame==1155 then
        check(r(0xAF+5)==0,'offscreen opener finishes its close cycle')
        check(tiles(0x2284)==grass,'page-2 close leaves page-0 grass intact')
        for i=1,#grass do
            emu.write(0x2284+math.floor((i-1)/2)*32+(i-1)%2,grass:byte(i),ppu)
        end
        closeOpener(0)
    elseif frame==1160 then
        check(tiles(0x2284)==grass,'a close aimed directly at the grass leaves it intact')
    elseif frame==1540 then
        -- Native door art on page 2. Mark a tile in the drawing so the final
        -- close must actually repaint the real door to pass.
        check(r(0x561)==1 and r(0x72A)*256+r(0x72C)>=0x130
            and r(0x72A)*256+r(0x72C)<=0x220,'camera reaches the real doorway')
        door=tiles(0x2284):byte(3)
        emu.write(0x22A4,0xFF,ppu)
        closeOpener(2)
    elseif frame==1545 then
        check(door==0x40 and emu.read(0x22A4,ppu)==door,'visible door still paints its closed tiles')
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
        f:close()
        stopScenario(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
