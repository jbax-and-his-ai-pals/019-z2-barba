-- Verify NG+ Overworld Mountain Melting, RLE $04 Merging, and Live PPU Attribute Update:
-- 1) Non-NG+ ($07A0==0): B facing Mountain ($0B) does NOT melt it.
-- 2) NG+ ($07A0==2) even with Flute ($0789==1): B facing Mountain ($0B) melts it to Desert ($04).
-- 3) Live PPU attribute byte ($23C0..$23FF / $27C0..$27FF) updates to Desert palette 3 immediately.
-- 4) Barba can walk onto the melted tile, and burning an adjacent Mountain merges into the $x4 run (no RLE bloat).
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local ppu=emu.memType.nesPpuDebug
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/ow-mountain-melt.txt','w'))
local errors=0
local frame=0
local worldAt=nil
local phase='seek_mtn'
local actionFrame=nil
local mtnPos=nil
local preMeltEnd=nil

local function check(ok,msg)
    report:write((ok and 'PASS ' or 'FAIL ')..msg..'\n')
    if not ok then errors=errors+1 end
end

local function rleEndAddr()
    local ptr=r(0x6094)+r(0x6095)*256
    local y=0
    local x=0
    while y<64 do
        local b=r(ptr+y)
        x=x+(b>>4)+1
        if x>=0x40 then return ptr+y end
        y=y+1
    end
    return ptr+y
end

local function attrForCurrentTile()
    local hi=r(0x79)
    local lo=r(0x7A)
    local aHi=(hi&0xFC)|0x03
    local tx=lo&0x1F
    local ty=((hi&0x03)<<3)|(lo>>5)
    local aLo=0xC0|((ty&0x1C)<<1)|(tx>>2)
    local q=((ty>>1)&1)*2 + ((tx>>1)&1)
    return (aHi<<8)|aLo, q*2
end

local function input()
    local b=newGameInput(frame)
    if frame>=1000 then
        if worldAt==nil then
            b.right=(frame>=1250 and frame<2050)
        elseif phase=='seek_mtn' then
            w(0x86,0); w(0x87,0); w(0x88,0); w(0x89,0)
            if r(0x0563)==0x0B and r(0x7D)==0 then
                -- Non-NG+ check first
                w(0x07A0,0)
                w(0x0789,0)
                actionFrame=frame
                b.b=true
                phase='check_non_ng'
            else
                -- Walk right off North Palace bridge, then up into the northern mountain range
                if (frame-worldAt)<100 then b.right=true else b.up=true end
            end
        elseif phase=='melt_ng' then
            if actionFrame and frame==actionFrame then b.b=true end
        elseif phase=='step_onto_melted' then
            if actionFrame and frame>=actionFrame and frame<actionFrame+22 then b.up=true end
        elseif phase=='melt_adjacent' then
            if actionFrame and frame==actionFrame then b.b=true end
        end
    end
    emu.setInput(b,0)
end

local function tick()
    frame=frame+1
    if frame>1250 and worldAt==nil and r(0x0736)==5 then worldAt=frame end
    if worldAt then
        if phase=='check_non_ng' and actionFrame and frame==actionFrame+20 then
            check(r(0x0563)==0x0B,'non-NG+ ($07A0==0) B does not melt Mountain ($0B)')
            -- Now enable NG+ ($07A0=2) AND give Flute ($0789=1)
            w(0x07A0,2)
            w(0x0789,1)
            preMeltEnd=rleEndAddr()
            phase='melt_ng'
            actionFrame=frame+2
        elseif phase=='melt_ng' and actionFrame and frame==actionFrame+10 then
            local aAddr,shift=attrForCurrentTile()
            local attrByte=emu.read(aAddr,ppu)
            local pal=(attrByte>>shift)&0x03
            check(pal==3,string.format('live PPU attr $%04X shift %d updated to Desert pal 3 (got %d, byte=$%02X)',aAddr,shift,pal,attrByte))
            screenshot('ow-mtn-melt')
            mtnPos=r(0x73)
            phase='step_onto_melted'
            actionFrame=frame+2
        elseif phase=='step_onto_melted' and actionFrame and frame==actionFrame+26 then
            local curEnd=rleEndAddr()
            check(r(0x7D)==0 and mtnPos~=nil and r(0x73)==mtnPos-1,
                string.format('Barba walked onto melted Mountain tile ($7D=%d y=%d->%d)', r(0x7D), mtnPos or -1, r(0x73)))
            check(r(0x0563)==0x0B,'facing Mountain (31,30) after stepping onto melted tile, got '..r(0x0563))
            preMeltEnd=curEnd
            phase='melt_adjacent'
            actionFrame=frame+2
        elseif phase=='melt_adjacent' and actionFrame and frame==actionFrame+10 then
            local postEnd=rleEndAddr()
            local growth=postEnd-preMeltEnd
            check(growth<=0,string.format('adjacent melt merged into $x4 run without RLE growth (delta=%d)',growth))
            report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
            report:close()
            stopScenario(errors==0 and 0 or 1)
        end
    end
    if frame==3200 then
        check(false,'timed out in phase '..phase..' (terrain='..r(0x0563)..')')
        report:write('RESULT FAIL\n'); report:close(); stopScenario(1)
    end
end

emu.addEventCallback(input,emu.eventType.inputPolled)
emu.addEventCallback(tick,emu.eventType.endFrame)
