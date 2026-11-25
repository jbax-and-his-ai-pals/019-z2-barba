-- Verify Overworld Scenery CHR & Foliage Animation:
-- 1) On the overworld ($0736 == 5, $0726 == 0), VBlank swaps R0 between base
--    bank 124 (CHR 31) and variants 230/232/234/236 so water/lava ($6E, 5 phases)
--    and swamp ($6F, 5 phases) animate while static base grass ($6D), forest ($68),
--    and desert ($6C) remain unchanged in R0.
-- 2) Individual grass ($6D -> $9E..$A3) and forest ($68 -> $A4..$A9, $6A -> $AA..$AF)
--    tiles in the nametable animate asynchronously via CHR 31 R1 on independent
--    randomized intervals, desynced from each other and from the 16-frame water tick.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local ppu=emu.memType.nesPpuMemory
local function r(a)return emu.read(a,mem)end
local report=assert(io.open(OUTPUT_DIR..'/overworld-water.txt','w'))
local errors=0
local frame=0
local worldAt=nil
local waterSeen,swampSeen={},{}
local waterCount,swampCount=0,0
local desertBase,desertChanged=nil,false
local staticGrassBase,staticGrassChanged=nil,false
local staticForestBase,staticForestChanged=nil,false

local prevNt={}
local grassAddrs,forestAddrs={},{}
local grassAddrCount,forestAddrCount=0,0
local grassFrames,forestFrames={},{}
local grassOnlyFrames,forestOnlyFrames=0,0
local grassOffWaterTick,forestOffWaterTick=0,0
local grassIntervals,forestIntervals={},{}
local lastGrassFrame,lastForestFrame=nil,nil
local sawGrassRevert,sawForestRevert=false,false
local sawScrollOk=true
local latePpuWrites=0

emu.addMemoryCallback(function(addr,val)
    if worldAt and frame>=worldAt+4 and r(0x0736)==5 and r(0x0726)==0 then
        local st=emu.getState()
        local sl=st['ppu.scanline'] or -1
        local pc=st['cpu.pc'] or -1
        if (sl==261 or (sl>=0 and sl<241)) and pc~=0xC1B1 then
            latePpuWrites=latePpuWrites+1
        end
    end
end,emu.callbackType.write,0x2000,0x2007)

local function check(ok,msg)
    report:write((ok and 'PASS ' or 'FAIL ')..msg..'\n')
    if not ok then errors=errors+1 end
end

local function readTile(tile)
    local t={}
    for i=0,15 do t[#t+1]=string.char(emu.read(tile*16+i,ppu)) end
    return table.concat(t)
end

local function isGrassVar(t) return t>=0x9E and t<=0xA3 end
local function isForestVar(t) return t>=0xA4 and t<=0xAF end

local function scanNametables(f)
    local grassChanged,forestChanged=false,false
    for _,base in ipairs({0x2000,0x2800}) do
        for off=0,0x3BF do
            local addr=base+off
            local val=emu.read(addr,ppu)
            local prev=prevNt[addr]
            if prev~=nil and prev~=val then
                if isGrassVar(val) or (isGrassVar(prev) and val==0x6D) then
                    grassChanged=true
                    if isGrassVar(val) and not grassAddrs[addr] then
                        grassAddrs[addr]=true; grassAddrCount=grassAddrCount+1
                    end
                    if isGrassVar(prev) and val==0x6D then sawGrassRevert=true end
                elseif isForestVar(val) or (isForestVar(prev) and (val==0x68 or val==0x6A)) then
                    forestChanged=true
                    if isForestVar(val) and not forestAddrs[addr] then
                        forestAddrs[addr]=true; forestAddrCount=forestAddrCount+1
                    end
                    if isForestVar(prev) and (val==0x68 or val==0x6A) then sawForestRevert=true end
                end
            end
            prevNt[addr]=val
        end
    end
    local f12=r(0x12)
    if grassChanged then
        grassFrames[#grassFrames+1]=f
        if not forestChanged then grassOnlyFrames=grassOnlyFrames+1 end
        if (f12&0x0F)~=0 then grassOffWaterTick=grassOffWaterTick+1 end
        if lastGrassFrame then grassIntervals[f-lastGrassFrame]=true end
        lastGrassFrame=f
    end
    if forestChanged then
        forestFrames[#forestFrames+1]=f
        if not grassChanged then forestOnlyFrames=forestOnlyFrames+1 end
        if (f12&0x0F)~=0 then forestOffWaterTick=forestOffWaterTick+1 end
        if lastForestFrame then forestIntervals[f-lastForestFrame]=true end
        lastForestFrame=f
    end
end

local function countKeys(tbl)
    local n=0
    for _ in pairs(tbl) do n=n+1 end
    return n
end

local function input()
    local b=newGameInput(frame)
    if frame>=1000 then
        if worldAt==nil then
            b.right=(frame>=1250 and frame<2050)
        elseif frame>=worldAt+185 and frame<worldAt+245 then
            b.right=true
        end
    end
    emu.setInput(b,0)
end

local function tick()
    frame=frame+1
    if frame>1250 and worldAt==nil and r(0x0736)==5 and r(0x0726)==0 then
        worldAt=frame
    end
    if worldAt and frame>=worldAt+4 and frame<worldAt+180 then
        if r(0x0736)==5 and r(0x0726)==0 then
            local w=readTile(0x6E)
            if not waterSeen[w] then waterSeen[w]=true; waterCount=waterCount+1 end
            local sw=readTile(0x6F)
            if not swampSeen[sw] then swampSeen[sw]=true; swampCount=swampCount+1 end
            local sg=readTile(0x6D)
            if staticGrassBase==nil then staticGrassBase=sg elseif sg~=staticGrassBase then staticGrassChanged=true end
            local sf=readTile(0x68)
            if staticForestBase==nil then staticForestBase=sf elseif sf~=staticForestBase then staticForestChanged=true end
            local d=readTile(0x6C)
            if desertBase==nil then desertBase=d elseif d~=desertBase then desertChanged=true end
            scanNametables(frame)
        end
    end
    if worldAt and frame>=worldAt+185 and frame<worldAt+250 then
        if r(0x0736)~=5 then sawScrollOk=false end
    end
    if worldAt and frame==worldAt+255 then
        local blankVariants=0
        local zeroTile=string.rep(string.char(0),16)
        for tid=0x9E,0xAF do
            if readTile(tid)==zeroTile then blankVariants=blankVariants+1 end
        end
        local gInt=countKeys(grassIntervals)
        local fInt=countKeys(forestIntervals)
        check(blankVariants==0,'all overworld R1 foliage variant tiles $9E-$AF are populated in PPU memory (blank='..blankVariants..')')
        check(r(0x0736)==5 and sawScrollOk,'remained stably on overworld while still and scrolling ($0736 == 5)')
        check(latePpuWrites==0,'all overworld PPU writes finished strictly inside VBlank (late='..latePpuWrites..')')
        check(waterCount==5,'observed all 5 overworld water tile $6E ripple phases (got '..waterCount..')')
        check(swampCount==5,'observed all 5 overworld swamp tile $6F ooze phases (got '..swampCount..')')
        check(not staticGrassChanged,'static base grass tile $6D stayed identical across all R0 phases')
        check(not staticForestChanged,'static base forest tile $68 stayed identical across all R0 phases')
        check(not desertChanged,'adjacent desert tile $6C stayed identical across all R0 phases')
        check(grassAddrCount>=3,'animated multiple independent grass tiles in nametable (got '..grassAddrCount..')')
        check(forestAddrCount>=3,'animated multiple independent forest tiles in nametable (got '..forestAddrCount..')')
        check(sawGrassRevert,'observed animated grass tiles reverting cleanly back to $6D')
        check(sawForestRevert,'observed animated forest tiles reverting cleanly back to $68/$6A')
        check(grassOnlyFrames>=2 and forestOnlyFrames>=2,
            string.format('grass and forest animate on desynced frames (grassOnly=%d, forestOnly=%d)',grassOnlyFrames,forestOnlyFrames))
        check(grassOffWaterTick>=2 and forestOffWaterTick>=2,
            string.format('grass and forest animate off the 16-frame water tick (grassOff=%d, forestOff=%d)',grassOffWaterTick,forestOffWaterTick))
        check(gInt>=2 and fInt>=2,
            string.format('grass and forest use varied randomized intervals (gIntervals=%d, fIntervals=%d)',gInt,fInt))
        report:write(string.format(
            'RESULT overworld_water phases=%d grassAddrs=%d forestAddrs=%d grassOnly=%d forestOnly=%d gInt=%d fInt=%d errors=%d\n',
            waterCount,grassAddrCount,forestAddrCount,grassOnlyFrames,forestOnlyFrames,gInt,fInt,errors))
        report:close()
        emu.stop(errors==0 and 0 or 1)
    end
end

emu.addEventCallback(input,emu.eventType.inputPolled)
emu.addEventCallback(tick,emu.eventType.endFrame)
