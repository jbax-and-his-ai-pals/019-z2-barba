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
local waveHashes,waveCount={},0
local shoreHashes,shoreCount={},0
local shoreMask,shoreMaskChanged=nil,false
local otherBase,otherChanged=nil,false
local lateWrites,banks=0,{}
local r5Mapped,r5Restored=false,false
local particleTiles,particleMinY,particleFront={},255,0
local prevPartVis={[0x48]=false,[0x4C]=false}
local particleXs,soloSpawns,syncSpawns,sameSideFrames,badParticleX={},0,0,0,0
local cliffMatches,cliffFrames,prevShake=true,0,0
local afterStart=false
local writesAfterStart=0
local restored=false

-- MMC3 R0/R5 writes: bank select $8000 = 0/5, then $8001 = bank.
emu.addMemoryCallback(function(addr,value)
    local reg=r(0x64D5)
    if reg==5 then
        if value==154 and frame<900 then r5Mapped=true end
        if value==3 and frame>=900 and frame<960 then r5Restored=true end
        return
    end
    if reg~=0 then return end
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
    if frame>=100 and frame<900 and r(0x0736)>=3 and r(0x0726)==0 then
        local spawnsNow=0
        local xsNow={}
        local shake=r(0x64FA)
        for _,slot in ipairs({0x48,0x4C}) do
            local py=r(0x6500+slot)
            local vis=py<0xEF
            if vis then
                local px=(r(0x6503+slot)+shake)&0xFF
                xsNow[#xsNow+1]=px
                if not prevPartVis[slot] then
                    spawnsNow=spawnsNow+1
                    particleXs[px]=true
                end
                if px<7 or (px>110 and px<140) or (px>203 and px<214) or px>219 then
                    badParticleX=badParticleX+1
                end
            end
            prevPartVis[slot]=vis
        end
        if spawnsNow==1 then soloSpawns=soloSpawns+1
        elseif spawnsNow==2 then syncSpawns=syncSpawns+1 end
        if #xsNow==2 and ((xsNow[1]<116 and xsNow[2]<116) or (xsNow[1]>=140 and xsNow[2]>=140)) then
            sameSideFrames=sameSideFrames+1
        end
    end
    if frame>=300 and frame<900 and r(0x0736)>=3 then
        local lava=readRange(0x0680,0x30)
        if not lavaHashes[lava] then lavaHashes[lava]=true;lavaCount=lavaCount+1 end
        local wave=readRange(0x05A0,0x40)
        if not waveHashes[wave] then waveHashes[wave]=true;waveCount=waveCount+1 end
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
        local other=readRange(0x0000,0x5A0)..readRange(0x05E0,0xA0)..readRange(0x06B0,0x20)..readRange(0x0710,0xF0)
        if not otherBase then otherBase=other elseif other~=otherBase then otherChanged=true end
        for _,slot in ipairs({0x48,0x4C}) do
            local py=r(0x6500+slot)
            if py<0xEF then
                if py<particleMinY then particleMinY=py end
                particleTiles[r(0x6501+slot)]=true
                if (r(0x6502+slot)&0x20)==0 then particleFront=particleFront+1 end
            end
        end
        if frame>=400 and frame<432 then
            -- The remaining cliff columns ($6500 at X=248 and $6550 at X=232) share
            -- tile $F0/$F1 and must both render intact in every shimmer phase.
            local pixels=emu.getScreenBuffer()
            local s=prevShake
            cliffFrames=cliffFrames+1
            for y=128,143 do
                for x=0,7 do
                    if pixels[y*256+249-s+x]~=pixels[y*256+233-s+x] then cliffMatches=false end
                end
            end
        end
        if frame==400 then
            local trail={{0x65,0x37,0x84},{0x61,0x35,0x7C},{0x5D,0x15,0x8C},
                         {0x25,0x3F,0x94},{0x45,0x45,0x9C},{0x69,0x31,0xA4}}
            local shake=r(0x64FA)
            for _,sprite in ipairs(trail) do
                local slot,tile,x=table.unpack(sprite)
                local y=r(0x6500+slot-1)
                check(y>=0x9D and y<=0x9F and r(0x6500+slot)==tile
                    and r(0x6502+slot)==x-shake,'title elbow/trail tile '..string.format('$%02X',tile))
            end
            local shot=assert(io.open(OUTPUT_DIR..'/title-lava.png','wb'))
            shot:write(emu.takeScreenshot());shot:close()
        end
    end
    prevShake=r(0x64FA)
    if frame==906 then afterStart=true end
    if frame==1100 then
        local n=0
        for b in pairs(banks) do if b>=238 and b<=244 then n=n+1 end end
        local ptCount=0
        for _ in pairs(particleTiles) do ptCount=ptCount+1 end
        check(lavaCount>=4,'lava tiles show '..lavaCount..' distinct shimmer patterns')
        check(waveCount>=3,'lava surface wave tiles show '..waveCount..' distinct phases')
        check(shoreCount==4 and not shoreMaskChanged,'lava shimmers through a fixed forest-edge mask')
        check(cliffFrames==32 and cliffMatches,'right cliff sprite renders in every shimmer phase')
        check(not otherChanged,'logo/scenery tiles in R0 stay byte-identical')
        check(n==4,'R0 cycled through '..n..' title lava banks (238-244)')
        check(r5Mapped and r5Restored,'R5 swaps to bank 154 on title and restores 3 on Start')
        local pxCount=0
        for _ in pairs(particleXs) do pxCount=pxCount+1 end
        check(particleMinY<=0x85 and ptCount>=2 and particleFront==0,'lava pixels/bubbles float behind text from lava line (minY=$'..string.format('%02X',particleMinY)..', tiles='..ptCount..', front='..particleFront..')')
        check(soloSpawns>=20 and syncSpawns<=5 and pxCount>=20 and sameSideFrames>0 and badParticleX==0,
              'lava specks stay desynced and full-width random (solo='..soloSpawns..', sync='..syncSpawns..', xs='..pxCount..', sameSide='..sameSideFrames..', badX='..badParticleX..')')
        check(lateWrites==0,'R0 writes during visible scanlines: '..lateWrites)
        check(writesAfterStart==0,'no lava R0 writes after Start')
        check(restored,'Start restores base R0 bank 4 for file select')
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close()
        local stop=emu.exit or emu.stop
        stop(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
