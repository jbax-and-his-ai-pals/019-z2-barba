-- Title and story scroll split. After the sprite-0 hit, the final $2006 write
-- must land in HBlank after scanline 143 so line 143 is all sky and line 144
-- starts the lava on the right row. The right border column stays black.
local m=emu.memType.nesDebug
local function r(a)return emu.read(a,m)end
local frame,errors=0,0
local f=assert(io.open(OUTPUT_DIR..'/title_split.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end

local LAST_FRAME=4700
local writes,reads=0,0
local last=nil
local splitFrames,lateOrEarly,wrongLine,wrongAddr=0,0,0,0
local minDot,maxDot=999,-1
local seamLava,seamFrames=0,0
local holdChanged,holdFrames,holdLine=0,0,nil
local borderDirty,borderFrames=0,0
local storySeen,backToTitle=false,false
local phases={}

-- Mesen reports the dot before the write; v takes the new value three dots later.
emu.addMemoryCallback(function(addr,value)
    local st=emu.getState()
    local line=st['ppu.scanline']
    if line<0 or line>=240 then return end
    writes=writes+1
    if not st['ppu.writeToggle'] then return end
    -- Second write of a pair: t's low byte is replaced and v = t.
    local t=(st['ppu.tmpVideoRamAddr']&0x7F00)|value
    last={line=line,dot=st['ppu.cycle'],t=t,a27=r(0x27)}
end,emu.callbackType.write,0x2006,0x2006)

emu.addMemoryCallback(function()
    local line=emu.getState()['ppu.scanline']
    if line>=0 and line<240 then reads=reads+1 end
end,emu.callbackType.read,0x2007,0x2007)

local lava={[0x6C0600]=true,[0xB53120]=true,[0xEA9E22]=true}
-- The screen buffer is a 1-based Lua array.
local function pix(px,x,y) return px[y*256+x+1]&0xFFFFFF end

emu.addEventCallback(function()
    frame=frame+1
    local mode=r(0x0736)
    -- From the first title frame: the first roar (DMC fetches + letterbox) is near frame 78.
    if frame>=12 and frame<LAST_FRAME and (mode==3 or mode==4) and r(0x0726)==0 then
        if mode==4 then storySeen=true elseif storySeen then backToTitle=true end
        splitFrames=splitFrames+1
        if not last then
            wrongLine=wrongLine+1
        else
            if last.line~=143 then wrongLine=wrongLine+1 end
            if last.dot<minDot then minDot=last.dot end
            if last.dot>maxDot then maxDot=last.dot end
            if last.dot<254 or last.dot>317 then lateOrEarly=lateOrEarly+1 end
            -- Same row the native $2007 reads reached: fine Y 5, coarse X 0.
            local a=last.a27
            local want=0x5000|(((a>>2)&3)<<10)|((a&3)<<8)
            if last.t~=want then wrongAddr=wrongAddr+1 end
            phases[a]=true
        end
        local px=emu.getScreenBuffer()
        seamFrames=seamFrames+1
        for x=208,215 do
            if lava[pix(px,x,143)] then seamLava=seamLava+1;break end
        end
        -- Title hold (scroll $60): the sky seam at col 26 (x=208..215, between
        -- the particle zones x=142..207 and x=217+) stays solid black on line 143.
        if mode==3 and r(0xFC)==0x60 then
            holdFrames=holdFrames+1
            local s={}
            for x=208,215 do s[#s+1]=pix(px,x,143) end
            local key=table.concat(s,',')
            if holdLine and key~=holdLine then holdChanged=holdChanged+1 end
            holdLine=key
        end
        -- The right border above the cliff stays black (rows 64-71 are the
        -- transparent top of the highest cliff sprite).
        borderFrames=borderFrames+1
        local dirty=false
        for y=0,71 do
            for x=248,255 do
                if pix(px,x,y)~=0 then dirty=true end
            end
        end
        if dirty then borderDirty=borderDirty+1 end
        if frame==1200 then
            local shot=assert(io.open(OUTPUT_DIR..'/title-split.png','wb'))
            shot:write(emu.takeScreenshot());shot:close()
        end
    end
    last=nil
    if frame==LAST_FRAME then
        local n=0
        for _ in pairs(phases) do n=n+1 end
        check(splitFrames>3500,'title/story frames sampled ('..splitFrames..')')
        check(storySeen and backToTitle,'story scroll ran and returned to the title')
        check(wrongLine==0,'final $2006 write on scanline 143 every frame ('..wrongLine..' misses)')
        check(lateOrEarly==0,'final $2006 write inside HBlank dots 254-317 (seen '..minDot..'-'..maxDot..')')
        check(wrongAddr==0 and n==4,'split targets fine Y 5 for all '..n..' story nametable phases')
        check(reads==0,'no $2007 reads during rendering ('..reads..')')
        check(seamLava==0,'line 143 x 208-215 never shows lava ('..seamLava..'/'..seamFrames..' frames)')
        check(holdFrames>500 and holdChanged==0,'line 143 sky is stable on the title hold ('..holdChanged..' changes in '..holdFrames..')')
        check(borderDirty==0,'right border x 248-255, rows 0-71 stay black ('..borderDirty..'/'..borderFrames..' frames)')
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close()
        local stop=emu.exit or emu.stop
        stop(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
