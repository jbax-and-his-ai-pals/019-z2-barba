-- 18-spell 2-column pause menu, spell costs, Green Palace palette, key items, and restore test.
dofile(TEST_DIR..'/newgame.lua')
local frame=0
local t0=nil
local gpState=nil -- nil, 'warped', 'walk', 'opening', 'open_wait', 'close_press', 'closing', 'close_wait'
local gpTimer=0
local ntSnap=nil
local mem=emu.memType.nesMemory
local ppu=emu.memType.nesPpuMemory
local oam=emu.memType.nesSpriteRam
local function read(a) return emu.read(a,mem) end
local function write(a,v) emu.write(a,v,mem) end
local function ppuRead(a) return emu.read(a,ppu) end
local function oamRead(a) return emu.read(a,oam) end
local report=assert(io.open(OUTPUT_DIR..'/spell-menu-2col.txt','w'))
local errors=0
local stopped=false
local function check(cond,msg)
    if stopped then return end
    report:write((cond and 'PASS ' or 'FAIL ')..msg..'\n')
    report:flush()
    if not cond then errors=errors+1 end
end
local function finish(code)
    if stopped then return end
    stopped=true
    report:write('RESULT '..(code==0 and 'PASS' or 'FAIL')..'\n')
    report:close()
    emu.stop(code)
end

local btn={}
local function input()
    if not gpState then
        local b=newGameInput(frame)
        if t0 then
            local dt=frame-t0
            b.start=(dt>=5 and dt<8) or (dt>=135 and dt<138)
            b.right=(dt>=35 and dt<38)
            b.down=(dt>=50 and dt<53)
            b.up=(dt>=65 and dt<68) or (dt>=80 and dt<83)
            b.left=(dt>=100 and dt<103)
            b.select=(dt>=175 and dt<178)
        end
        emu.setInput(b,0)
    else
        emu.setInput(btn,0)
    end
end

local function readBoxTile(row, col)
    local sum=read(0x72C)+0x28
    local carry=(sum>=256) and 1 or 0
    local startCol=((sum&0xF0)>>3)
    local pg=(read(0x72A)+carry)&1
    local absCol=startCol+col
    local ntBase=(pg==0) and 0x2000 or 0x2400
    if absCol>=32 then
        absCol=absCol-32
        ntBase=(ntBase==0x2000) and 0x2400 or 0x2000
    end
    local screenRow=6+row
    return ppuRead(ntBase + screenRow*32 + absCol)
end

local function readBoxQuadPal(mr, mc)
    local sum=read(0x72C)+0x28
    local carry=(sum>=256) and 1 or 0
    local startMeta=((sum&0xF0)>>4)
    local pg=(read(0x72A)+carry)&1
    local absMeta=startMeta+mc
    local ntBase=(pg==0) and 0x2000 or 0x2400
    if absMeta>=16 then
        absMeta=absMeta-16
        ntBase=(ntBase==0x2000) and 0x2400 or 0x2000
    end
    local attrCol=absMeta>>1
    local attrRow=mr>>1
    local attrByte=ppuRead(ntBase+0x3C8+attrRow*8+attrCol)
    local shift=((mr&1)*4)+((absMeta&1)*2)
    return (attrByte>>shift)&0x03
end

local function snapPpuNt()
    local s={}
    for a=0x2000,0x27FF do s[a]=ppuRead(a) end
    return s
end

local function tick()
    if stopped then return end
    frame=frame+1
    if not t0 and frame>=900 and read(0x736)==0x0B and read(0x524)==0 then
        t0=frame
        check(true,'reached side-view play')
        for i=0,7 do write(0x77B+i,1) end
        write(0x648B,0x57) -- DECOY (8)
        write(0x63B1,1)    -- AXE (9)
        write(0x63B2,1)    -- DOUBLE (10)
        write(0x63B9,1)    -- CLOCK (16)
        write(0x63BA,1)    -- HEAVY (17)
        write(0x773,0x80)  -- full magic
        write(0x778,8)     -- Magic Level 8
        write(0x749,0)     -- start at SCALES (0)
    end
    if not t0 then
        if frame>1600 then
            check(false,'reached side-view play')
            finish(1)
        end
        return
    end
    if not gpState then
        local dt=frame-t0
        if dt==32 then
            check(read(0x524)==5,'pause menu reached state 5 (input)')
            check(read(0x6697)~=0,'SPELL_MENU_ACTIVE is nonzero')
            check(read(0x749)==0,'cursor starts on SCALES (0)')
            screenshot('spell-menu-2col')
        end
        if dt==41 then check(read(0x749)==8,'Right moves cursor to DECOY (8)') end
        if dt==56 then check(read(0x749)==9,'Down moves cursor to AXE (9)') end
        if dt==71 then check(read(0x749)==8,'Up moves cursor back to DECOY (8)') end
        if dt==86 then
            check(read(0x749)==17,'Up wraps to HEAVY (17)')
            screenshot('spell-menu-2col-heavy')
        end
        if dt==106 then check(read(0x749)==7,'Left from HEAVY (17) moves to INFERNO (7)') end
        if dt==165 then
            check(read(0x524)==0,'Start closes pause menu cleanly')
            check(read(0x6697)==0,'SPELL_MENU_ACTIVE cleared on close')
            screenshot('spell-menu-2col-closed')
            write(0x749,17)
        end
        if dt==180 then
            check((read(0x6681)&0x02)==0x02,'Select casts HEAVY (17) after 2-col menu')
            -- Phase 2: Warp inside Palace 2 (Green Palace, room $0F)
            gpState='warped'
            gpTimer=0
            write(0x707,3); write(0x706,0); write(0x70A,0); write(0x769,3)
            write(0x561,0x0F); write(0x568,1); write(0x56B,2); write(0x56C,1); write(0x748,0x35)
            write(0x701,0); write(0x75C,0); write(0x704,0)
            write(0x736,0); write(0x73D,0); write(0x726,1)
        end
        return
    end

    gpTimer=gpTimer+1
    btn={}
    if gpState=='warped' then
        if read(0x736)==0x0B and read(0x524)==0 then
            if gpTimer<20 then return end
            for i=0,7 do write(0x77B+i,1) end
            write(0x648B,0x57)
            for i=1,9 do write(0x63B0+i,1) end
            for i=0,7 do write(0x785+i,1) end
            write(0x778,6)
            write(0x700,6)
            write(0x793,0)
            write(0x794,2)
            write(0x749,0)
            gpState='walk'
            gpTimer=0
        elseif gpTimer>200 then
            check(false,'warped to Green Palace')
            finish(1)
        end
    elseif gpState=='walk' then
        if gpTimer<=25 then
            btn.right=true
        elseif gpTimer==35 then
            ntSnap=snapPpuNt()
        elseif gpTimer>=38 and gpTimer<41 then
            btn.start=true
        elseif gpTimer>=41 then
            gpState='opening'
            gpTimer=0
        end
    elseif gpState=='opening' then
        if read(0x524)==5 then
            gpState='open_wait'
            gpTimer=0
        elseif gpTimer>60 then
            check(false,'Green Palace menu reached state 5')
            finish(1)
        end
    elseif gpState=='open_wait' then
        if gpTimer==4 then
            check(readBoxTile(0,0)==0xCA and readBoxTile(0,13)==0xCA and readBoxTile(0,25)==0xCA,'top border corners/junctions')
            check(readBoxTile(13,0)==0xCA and readBoxTile(13,13)==0xCA and readBoxTile(13,25)==0xCA,'spell divider corners/junctions')
            check(readBoxTile(19,0)==0xCA and readBoxTile(19,25)==0xCA and readBoxTile(19,13)==0xCB,'bottom border spans 26 tiles')
            check(readBoxTile(1,4)==0xE1 and readBoxTile(1,9)==0xDE,'HYRULE header drawn')
            check(readBoxTile(1,16)==0xDA and readBoxTile(1,21)==0xDE,'ARCADE header drawn')
            check(readBoxTile(16,17)==0xF4 and readBoxTile(16,21)==0xF4,'row 16 spacer above key items is blank')
            check(readBoxTile(17,2)==0x96 and readBoxTile(17,3)==0xFC and readBoxTile(17,4)==0xD6,'lives counter Head x6')
            check(readBoxTile(17,6)==0xB9 and readBoxTile(17,7)==0xFC and readBoxTile(17,8)==0xD0,'keys counter Key x0')
            check(readBoxTile(17,10)==0xCD and readBoxTile(17,11)==0xFC and readBoxTile(17,12)==0xD2,'crystals counter Crystal x2')
            check(readBoxTile(3,10)==0xCF and readBoxTile(3,11)==0xD1 and readBoxTile(3,12)==0xD6,'SCALES cost 16 at Mag 6')
            check(readBoxTile(10,10)==0xD1 and readBoxTile(10,11)==0xD2 and readBoxTile(10,12)==0xD0,'INFERNO cost 120 at Mag 6')
            check(readBoxTile(3,22)==0xCF and readBoxTile(3,23)==0xCF and readBoxTile(3,24)==0xD4,'DECOY cost 4 at Mag 6')
            check(readBoxTile(12,22)==0xCF and readBoxTile(12,23)==0xD1 and readBoxTile(12,24)==0xD4,'HEAVY cost 14 at Mag 6')
            local badPal=0
            for mr=1,10 do
                for mc=0,12 do
                    if readBoxQuadPal(mr,mc)~=0 then badPal=badPal+1 end
                end
            end
            check(badPal==0,'all 130 box quadrants use BG palette 00 (bad='..badPal..')')
            local boxLeft=((read(0x72C)+0x28)&0xF0)-read(0x72C)
            if boxLeft<0 then boxLeft=boxLeft+256 end
            local itemsOk=true
            local ppuOamOk=true
            for i=0,7 do
                local sy=read(0x0204+i*4)
                local sx=read(0x0207+i*4)
                if sy~=0xB7 or sx<boxLeft+8 or sx>boxLeft+25*8-8 then
                    itemsOk=false
                end
                local psy=oamRead(0x04+i*4)
                local psx=oamRead(0x07+i*4)
                if psy~=0xB7 or psx<boxLeft+8 or psx>boxLeft+25*8-8 then
                    ppuOamOk=false
                end
            end
            check(itemsOk,'all 8 key item sprites seated inside bottom tray (boxLeft='..boxLeft..', scroll='..read(0x72C)..')')
            check(ppuOamOk,'all 8 key item sprites live in PPU OAM inside bottom tray')
            screenshot('spell-menu-green-palace-open')
            gpState='close_press'
            gpTimer=0
        end
    elseif gpState=='close_press' then
        if gpTimer>=1 and gpTimer<4 then
            btn.start=true
        elseif gpTimer>=4 then
            gpState='closing'
            gpTimer=0
        end
    elseif gpState=='closing' then
        if read(0x524)==0 then
            gpState='close_wait'
            gpTimer=0
        elseif gpTimer>60 then
            check(false,'Green Palace menu closed cleanly')
            finish(1)
        end
    elseif gpState=='close_wait' then
        if gpTimer==2 then
            local ntDiff=0
            local attrDiff=0
            for a=0x2000,0x27FF do
                if ppuRead(a)~=ntSnap[a] then
                    if (a&0x3FF)>=0x3C0 then attrDiff=attrDiff+1 else ntDiff=ntDiff+1 end
                end
            end
            check(ntDiff==0,'Green Palace nametable restored identically (diff='..ntDiff..')')
            check(attrDiff==0,'Green Palace attributes restored identically (diff='..attrDiff..')')
            screenshot('spell-menu-green-palace-closed')
            finish(errors==0 and 0 or 1)
        end
    end
end

emu.addEventCallback(input,emu.eventType.inputPolled)
emu.addEventCallback(tick,emu.eventType.endFrame)
