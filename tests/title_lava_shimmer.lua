-- Title screen: the open lava and forest-edge masks shimmer across four R0
-- banks. The cliff renders intact and Start restores R0 for file select.
local m=emu.memType.nesDebug
local p=emu.memType.nesPpuDebug
local function r(a)return emu.read(a,m)end
local frame,errors=0,0
local f=assert(io.open(OUTPUT_DIR..'/title_lava_shimmer.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
local function readRange(baseAddr,len)
    local bytes={}
    for i=0,len-1 do bytes[#bytes+1]=string.char(emu.read(baseAddr+i,p)) end
    return table.concat(bytes)
end

local lavaHashes,lavaCount={},0
local shoreHashes,shoreCount={},0
local shoreMask,shoreMaskChanged=nil,false
local otherBase,otherChanged=nil,false
local lateWrites,banks=0,{}
local cliffMatches,cliffFrames=true,0
local afterStart=false
local writesAfterStart=0
local restored=false

-- MMC3 R0 writes: bank select $8000 = 0, then $8001 = bank.
emu.addMemoryCallback(function(addr,value)
    if r(0x64D5)~=0 then return end
    if value==4 and frame>=900 and frame<960 then restored=true end
    if value<238 or value>244 then return end
    local st=emu.getState()
    local line=st['ppu.scanline']
    if line>=0 and line<240 then lateWrites=lateWrites+1 end
    banks[value]=true
    if afterStart then writesAfterStart=writesAfterStart+1 end
end,emu.callbackType.write,0x8001,0x8001)

emu.addEventCallback(function()
    local press=frame>=900 and frame<904
    emu.setInput(press and {start=true} or {},0)
end,emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame=frame+1
    if frame>=300 and frame<900 and r(0x0736)>=3 then
        local lava=readRange(0x0680,0x30)
        if not lavaHashes[lava] then lavaHashes[lava]=true;lavaCount=lavaCount+1 end
        local shore=readRange(0x06D0,0x40)
        if not shoreHashes[shore] then shoreHashes[shore]=true;shoreCount=shoreCount+1 end
        -- Green tree pixels (color 2: hi=1, lo=0) stay fixed while lava shimmers.
        local mask={}
        for tile=0,3 do
            for row=1,8 do
                local lo,hi=shore:byte(tile*16+row),shore:byte(tile*16+row+8)
                mask[#mask+1]=string.char(hi&~lo)
            end
        end
        local fixed=table.concat(mask)
        if not shoreMask then shoreMask=fixed elseif fixed~=shoreMask then shoreMaskChanged=true end
        local other=readRange(0x0000,0x680)..readRange(0x06B0,0x20)..readRange(0x0710,0xF0)
        if not otherBase then otherBase=other elseif other~=otherBase then otherChanged=true end
        if frame>=400 and frame<432 then
            -- These two cliff columns use the same vanilla sprite and backdrop.
            -- Before the fix, the NES dropped the right copy behind Barba.
            local pixels=emu.getScreenBuffer()
            cliffFrames=cliffFrames+1
            for y=128,143 do
                for x=0,7 do
                    if pixels[y*256+241+x]~=pixels[y*256+217+x] then cliffMatches=false end
                end
            end
        end
        if frame==400 then
            local trail={{0x65,0x37,0x84},{0x61,0x35,0x7C},{0x5D,0x15,0x8C},
                         {0x25,0x3F,0x94},{0x45,0x45,0x9C},{0x69,0x31,0xA4}}
            for _,sprite in ipairs(trail) do
                local slot,tile,x=table.unpack(sprite)
                check(r(0x6500+slot-1)==0x9F and r(0x6500+slot)==tile
                    and r(0x6502+slot)==x,'title elbow/trail tile '..string.format('$%02X',tile))
            end
            local shot=assert(io.open(OUTPUT_DIR..'/title-lava.png','wb'))
            shot:write(emu.takeScreenshot());shot:close()
        end
    end
    if frame==906 then afterStart=true end
    if frame==1100 then
        local n=0
        for b in pairs(banks) do if b>=238 and b<=244 then n=n+1 end end
        check(lavaCount>=4,'lava tiles show '..lavaCount..' distinct shimmer patterns')
        check(shoreCount==4 and not shoreMaskChanged,'lava shimmers through a fixed forest-edge mask')
        check(cliffFrames==32 and cliffMatches,'right cliff sprite renders in every shimmer phase')
        check(not otherChanged,'logo/scenery tiles in R0 stay byte-identical')
        check(n==4,'R0 cycled through '..n..' title lava banks (238-244)')
        check(lateWrites==0,'R0 writes during visible scanlines: '..lateWrites)
        check(writesAfterStart==0,'no lava R0 writes after Start')
        check(restored,'Start restores base R0 bank 4 for file select')
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close()
        local stop=emu.exit or emu.stop
        stop(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
