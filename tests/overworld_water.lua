-- Verify Overworld Water Animation:
-- On the overworld ($0736 == 5, $0726 == 0), VBlank swaps R0 between base
-- bank 68 and variants 230/232/234/236 so water/lava tile $6E ripples across
-- 5 distinct patterns while neighboring terrain tiles ($6D grass, $68 forest)
-- remain unchanged.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local ppu=emu.memType.nesPpuMemory
local function r(a)return emu.read(a,mem)end
local report=assert(io.open(OUTPUT_DIR..'/overworld-water.txt','w'))
local errors=0
local frame=0
local worldAt=nil
local waterSeen={}
local waterCount=0
local grassBase,forestBase=nil,nil
local grassChanged,forestChanged=false,false

local function check(ok,msg)
    report:write((ok and 'PASS ' or 'FAIL ')..msg..'\n')
    if not ok then errors=errors+1 end
end

local function readTile(tile)
    local t={}
    for i=0,15 do t[#t+1]=string.char(emu.read(tile*16+i,ppu)) end
    return table.concat(t)
end

local function input()
    local b=newGameInput(frame)
    if frame>=1000 and worldAt==nil then
        b.right=(frame>=1250 and frame<2050)
    end
    emu.setInput(b,0)
end

local function tick()
    frame=frame+1
    if frame>1250 and worldAt==nil and r(0x0736)==5 and r(0x0726)==0 then
        worldAt=frame
    end
    if worldAt and frame>=worldAt+4 and frame<worldAt+140 then
        if r(0x0736)==5 and r(0x0726)==0 then
            local w=readTile(0x6E)
            if not waterSeen[w] then
                waterSeen[w]=true
                waterCount=waterCount+1
            end
            local g=readTile(0x6D)
            local f=readTile(0x68)
            if grassBase==nil then grassBase=g elseif g~=grassBase then grassChanged=true end
            if forestBase==nil then forestBase=f elseif f~=forestBase then forestChanged=true end
        end
    end
    if worldAt and frame==worldAt+145 then
        check(r(0x0736)==5,'remained on overworld ($0736 == 5)')
        check(waterCount==5,'observed all 5 overworld water tile $6E ripple phases (got '..waterCount..')')
        check(not grassChanged,'adjacent grass tile $6D stayed identical across all phases')
        check(not forestChanged,'adjacent forest tile $68 stayed identical across all phases')
        report:write(string.format('RESULT overworld_water phases=%d errors=%d\n',waterCount,errors))
        report:close()
        emu.stop(errors==0 and 0 or 1)
    end
end

emu.addEventCallback(input,emu.eventType.inputPolled)
emu.addEventCallback(tick,emu.eventType.endFrame)
