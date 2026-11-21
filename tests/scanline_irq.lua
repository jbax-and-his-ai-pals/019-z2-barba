-- Verify MMC3 Scanline IRQ features:
-- 1) Zero-jitter HUD split at scanline 31 & OAM slot 0 freed
-- 2) Parallax scrolling in Overworld bridges ($0707=0) and Palaces ($0707>=3)
-- 3) Heat shimmer over palace lava ($64E8=1) and absent in non-lava rooms
-- 4) Cinematic letterbox ($2001=0 at line 215) on Title roar, Dark Barba entrance, and Ending
dofile(TEST_DIR..'/newgame.lua')
local frame=0
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/scanline-irq.txt','w'))
local fails=0
local function check(ok,msg)
    report:write((ok and 'PASS ' or 'FAIL ')..msg..'\n')
    if not ok then fails=fails+1 end
end

local sawTitleLetterbox=false
local sawBridgeParallax=false
local sawHblankMaskWrite=true
local minDot,maxDot=999,-1
local sawPalaceNoLava=false
local sawLavaShimmer=false
local sawLavaHaze=false
local hazeX1={}
local hazeX2={}
local shimmerValues={}
local sawOam0Free=false
local sawHud31=false
local sawDarkBarbaLetterbox=false
local sawEndingLetterbox=false

local irqLines={}
emu.addMemoryCallback(function()
    local s=emu.getState()
    local st=r(0x64D6)
    irqLines[st]=s['ppu.scanline']
end,emu.callbackType.exec,0xD4BE)
emu.addMemoryCallback(function()
    local s=emu.getState()
    local dot=s['ppu.cycle']
    local mask=r(0x64E4+r(0x64D6))
    if mask~=r(0xFE) then
        if dot<minDot then minDot=dot end
        if dot>maxDot then maxDot=dot end
        -- STA $2001 writes on its 4th cycle (+9..12 dots); require write cycle in HBlank (256..340).
        if dot+9<256 or dot+12>340 then sawHblankMaskWrite=false end
    end
end,emu.callbackType.exec,0xC197)

emu.addEventCallback(function()
    local b=newGameInput(frame)
    if (frame>=1200 and frame<1350) or (frame>=1790 and frame<1970) then b.right=true end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame=frame+1
    -- Phase 1: Title roar letterbox (force ROAR_TIMER=10 briefly on title)
    if frame==120 then
        w(0x05F0,10)
    end
    if frame==122 then
        sawTitleLetterbox=(r(0x64D7)==1 and r(0x64D8)==215 and r(0x64E4)==0)
        check(sawTitleLetterbox,'title roar arms bottom letterbox at line 215')
        w(0x05F0,0)
    end

    -- Phase 2: Overworld bridge ($0707=0, room $01) parallax + OAM0 free + HUD split 31
    if frame==1050 then
        w(0x707,0);w(0x706,0);w(0x769,1);w(0x561,0x01)
        w(0x568,0);w(0x56B,0);w(0x56C,0);w(0x701,0);w(0x75C,0);w(0x704,0)
        w(0x736,7);w(0x73D,0);w(0x726,1)
        w(0x774,255);w(0x784,8)
    end
    if frame>=1220 and frame<1350 and r(0x736)==11 and r(0x726)==0 then
        if irqLines[0]==31 then sawHud31=true end
        if r(0x0200)==0xF8 then sawOam0Free=true end
        if r(0x64D7)==2 and r(0xFD)>=16 then
            local p0=r(0x64E0)*256+r(0x64DC)
            local p1=r(0x64E1)*256+r(0x64DD)
            if p0<p1 then sawBridgeParallax=true end
        end
    end

    if frame==1355 then
        check(sawBridgeParallax and r(0x64EE)>=63,string.format('Overworld bridge uses 3-band parallax (fd=%d cnt=%d line=%d x0=%d x1=%d x2=%d)',
            r(0xFD),r(0x64D7),r(0x64EE),r(0x64DC),r(0x64DD),r(0x64DE)))
        -- Phase 2b: Overworld forest ($0707=0, room $03) disables parallax (OW_PARALLAX_LINE=0)
        w(0x707,0);w(0x706,0);w(0x769,1);w(0x561,0x03)
        w(0x568,0);w(0x56B,0);w(0x56C,0);w(0x701,0);w(0x75C,0);w(0x704,0)
        w(0x736,7);w(0x73D,0);w(0x726,1)
        w(0x774,255);w(0x784,8)
    end
    if frame==1430 then
        check(r(0x736)==11 and r(0x64EE)==0 and r(0x64D7)==1,
            string.format('Overworld forest disables parallax (line=%d cnt=%d)',r(0x64EE),r(0x64D7)))
    end
    if frame==1435 then
        -- Phase 3: Non-lava Palace 1 corridor ($0707=3, room 5)
        w(0x707,3);w(0x706,0);w(0x769,3);w(0x561,5)
        w(0x568,0);w(0x56B,1);w(0x56C,0);w(0x701,0);w(0x75C,0);w(0x704,0)
        w(0x736,0);w(0x73D,0);w(0x726,1)
    end
    if frame==1575 then
        sawPalaceNoLava=(r(0x736)==11 and r(0x64E8)==0 and r(0x64D7)==1)
        check(sawPalaceNoLava,'non-lava palace uses single HUD split with ROOM_HAS_LAVA=0')
    end

    -- Phase 4: Palace 6 lava room ($0707=4, room $33) heat shimmer
    if frame==1580 then
        w(0x707,4);w(0x706,2);w(0x769,4);w(0x561,0x33)
        w(0x568,5);w(0x56B,6);w(0x56C,1);w(0x701,0);w(0x75C,0);w(0x704,0)
        w(0x736,0);w(0x73D,0);w(0x726,1)
    end
    if frame>=1690 and frame<1740 and r(0x736)==11 and r(0x726)==0 then
        if r(0x64E8)==1 and r(0x64D7)==2 then
            sawLavaShimmer=true
            shimmerValues[r(0x64EF)]=true
            if irqLines[1]==207 and r(0x64DD)==r(0xFD) and (r(0x64E5)&0x20)~=0 then
                sawLavaHaze=true
            end
        end
    end
    if frame==1740 then
        local distinct=0
        for _ in pairs(shimmerValues)do distinct=distinct+1 end
        check(sawLavaShimmer and distinct==4,
            string.format('palace lava room animates 4 R1 CHR banks (distinct=%d)', distinct))
        check(sawLavaHaze,
            'palace lava room arms 207 red-emphasis split without X scroll wobble')
    end

    -- Phase 5: Dark Barba entrance letterbox ($0707=5, $B6=1, $A1=$23, $0505>0)
    if frame==1750 then
        w(0x707,5);w(0x706,2);w(0x769,5);w(0x561,0x36)
        w(0x568,6);w(0x56B,7);w(0x56C,2);w(0x701,0);w(0x75C,1);w(0x704,0)
        w(0x736,0);w(0x73D,0);w(0x726,1)
    end
    if frame>=1790 and frame<1990 and r(0x736)==11 and r(0xB6)==1 and r(0xA1)==0x23 and (r(0x0505)>0 or r(0x63)<3) then
        if r(0x64D7)>=2 and r(0x64E4 + r(0x64D7) - 1)==0 then
            sawDarkBarbaLetterbox=true
        end
    end
    if frame==1990 then
        check(sawDarkBarbaLetterbox,string.format('Dark Barba entrance enables bottom letterbox bar (b6=%d a1=%02X p63=%d p505=%d cnt=%d)',
            r(0xB6),r(0xA1),r(0x63),r(0x0505),r(0x64D7)))
    end

    -- Phase 6: Ending letterbox ($0736=8, $076C=3, $0726=0)
    if frame==2000 then
        w(0x736,0x08);w(0x76C,0x03);w(0x726,0x00)
    end
    if frame>=2001 and frame<=2020 then
        if r(0x64D7)==1 and r(0x64D8)==215 and r(0x64E4)==0 then
            sawEndingLetterbox=true
        end
    end
    if frame==2020 then
        check(sawEndingLetterbox,'ending enables bottom letterbox bar at line 215')
        check(sawHud31,'HUD split fires on scanline 31')
        check(sawHblankMaskWrite,string.format('tinted/letterbox $2001 writes land in HBlank (dots %d..%d)',minDot,maxDot))
        check(sawOam0Free,'OAM slot 0 ($0200) is freed ($F8 when unused)')
        report:write('RESULT '..(fails==0 and 'PASS' or 'FAIL')..'\n')
        report:close()
        stopScenario(fails==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
