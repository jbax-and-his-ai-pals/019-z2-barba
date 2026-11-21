-- North Palace: candle flames ($52/$53 in R3) shimmer across 4 CHR variants
-- during VBlank while all other R3 tiles remain identical.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local p=emu.memType.nesPpuMemory
local function r(a)return emu.read(a,m)end
local frame,errors=0,0
local flameHashes,otherHashes={},{}
local f=assert(io.open(OUTPUT_DIR..'/castle_flame_shimmer.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
local function countKeys(t)
    local n=0
    for _ in pairs(t) do n=n+1 end
    return n
end
local function readRange(base,len)
    local bytes={}
    for i=0,len-1 do bytes[#bytes+1]=string.char(emu.read(base+i,p)) end
    return table.concat(bytes)
end
emu.addEventCallback(function()
    emu.setInput(newGameInput(frame),0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if frame==1030 then
        check(r(0x736)==11 and r(0x707)==0 and r(0x706)==0 and r(0x561)==0 and r(0x76E)==2,
            'North Palace loaded with CHR pair 1')
    end
    if frame>=1030 and frame<1070 then
        flameHashes[readRange(0x1520,32)]=true
        otherHashes[readRange(0x17A0,32)]=true
    end
    if frame==1070 then
        local nf=countKeys(flameHashes)
        local no=countKeys(otherHashes)
        check(nf==8,'North Palace flame ($52/$53) cycles through 8 CHR variants (got '..nf..')')
        check(no==1,'Non-flame R3 tile ($7A/$7B) stays identical across all variants (got '..no..')')
        f:write(string.format('RESULT errors=%d flameVariants=%d otherVariants=%d\n',errors,nf,no))
        f:close()
        emu.stop(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
