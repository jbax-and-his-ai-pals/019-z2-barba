-- Dark cave firelight flicker + fireball glow halo regression.
-- Warps to West Hyrule dark grotto ($0707=0, $0769=1, $0561=$0E) without
-- the Candle ($0785=0, $07AF=$08) and checks:
--   1. Idle before firing: dark palette stays $0F, CAVE_GLOW_ON=0.
--   2. First fireball ($6540): 0-frame delay lighting (next VBlank), halo around
--      $6540, and clean dark restore after the volley expires.
--   3. Full volley: halos in $6560..$65FC and steady 16-frame Peak/Mid/Low/Mid
--      pulse across $3F05..$3F0F, $3F11..$3F13, and $3F19..$3F1F.
--   4. Walking + scrolling ($0725!=0) while firing: steady lighting, $0301 < $60,
--      Buffer 1 ($0362/$0363) intact.
--   5. Spell flash ($074B) during fireballs: BG/enemy light keeps pulsing,
--      and Barba ($3F11..$3F13) restores to firelight immediately after.
--   6. Busy cave (6 active enemies + enemy projectiles): single allowed shot
--      still lights immediately with 0 delay.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local pal=emu.memType.nesPaletteRam
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local function rp(a)return emu.read(a,pal)end
local report=assert(io.open(OUTPUT_DIR..'/cave-light.txt','w'))
local errors=0
local function check(ok,msg)
    report:write((ok and 'PASS ' or 'FAIL ')..msg..string.char(10))
    if not ok then errors=errors+1 end
end
local frame=0
local idleDarkOk=true
local singleSpawnFrame,singleLitFrame,singleHalo,singleOffFrame,singleRestored=nil,nil,false,nil,false
local singleCapOk=true
local sawFireball,sawHalo,sawPal1,sawPal2,sawPal3,sawGlowOn=false,false,false,false,false,false
local sawEmphDim,sawEmphRed=false,false
local sawEnemyBright,sawEnemyDim=false,false
local glowOffAfter,restoredDark=false,false
local bufSafeOk,maxBufLen,sawScroll=true,0,false
local scrollLitOk,prevHadFb=true,false
local flashBgLit,flashBarbaRestored=false,false
local flashStarted,flashClearedFrame=false,nil
local busySpawnFrame,busyLitFrame=nil,nil

local FB_OAM={0x38,0x3C,0x40,0x44,0x48}
local function liveFbs()
    local fbs={}
    for _,off in ipairs(FB_OAM) do
        local y=r(0x6500+off)
        if y<0xF0 and r(0x6501+off)==0x85 then
            fbs[#fbs+1]={off=off,x=r(0x6503+off),y=y}
        end
    end
    return fbs
end
local function hasHaloFor(fb)
    for off=0x60,0xFC,4 do
        local hy=r(0x6500+off)
        if hy<0xF0 and r(0x6501+off)==0x87 and (r(0x6502+off)%64)==0x22 then
            local hx=r(0x6503+off)
            if math.abs(hx-fb.x)<=1 and math.abs(hy-fb.y)<=1 then
                return true
            end
        end
    end
    return false
end

emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then
        b={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
        if frame>=1150 and frame<1153 then
            b.b=true -- single tap -> spawns shot #1 in native slot 1 ($6540)
        elseif frame>=1290 and frame<1340 then
            b.b=(frame-1290)%10<3 -- full volley
        elseif frame>=1490 and frame<1560 then
            b.left=true -- walk left continuously so camera scrolls across 16px columns ($0725!=0)
            b.b=(frame>=1492 and frame<1495) or (frame>=1525 and frame<1528)
        elseif frame>=1676 and frame<1682 then
            b.right=true -- face back into the room after walking left
        elseif frame>=1684 and frame<1740 then
            b.b=(frame-1684)%10<3 -- spell flash overlap test
        elseif frame>=1840 and frame<1890 then
            b.b=(frame-1840)%10<3 -- busy 6-enemy cave test
        end
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        w(0x707,0);w(0x706,0);w(0x769,1);w(0x561,0x0E)
        w(0x568,0);w(0x56B,0);w(0x56C,0);w(0x701,0);w(0x75C,0);w(0x704,0)
        w(0x736,7);w(0x73D,0);w(0x726,1)
        w(0x785,0) -- no Candle
        w(0x777,4);w(0x778,8);w(0x779,8);w(0x783,8);w(0x784,8)
        w(0x774,255);w(0x773,255)
    end
    if frame==1060 then
        w(0x785,0)
        -- Start on page 1 solid entrance/mid floor so walking left scrolls cleanly without falling
        w(0x72A,1);w(0x72C,0x20);w(0x3B,1);w(0x4D,0x80)
    end
    if frame>=1080 and frame<1145 then
        if r(0x64FF)~=0 or r(0x6741)~=0 or rp(0x09)~=0x0F or rp(0x1A)~=0x0F or rp(0x1E)~=0x0F then idleDarkOk=false end
    end
    -- Phase 2: Single tap (shot #1 at $6540) -> immediate dim ember, caps below Pal 3, smooth fadeout
    if frame>=1150 and frame<1280 then
        local fbs=liveFbs()
        if #fbs>0 then
            if not singleSpawnFrame then singleSpawnFrame=frame end
            if rp(0x05)==0x06 and not singleLitFrame then singleLitFrame=frame end
            if singleSpawnFrame and not singleLitFrame and rp(0x05)==0x27 then singleCapOk=false end
            for _,fb in ipairs(fbs) do
                if fb.off==0x40 and hasHaloFor(fb) then singleHalo=true end
            end
        elseif singleSpawnFrame and not singleOffFrame then
            singleOffFrame=frame
        end
        if singleOffFrame and frame==singleOffFrame+20 then
            if r(0x64FF)==0 and r(0x6741)==0 and rp(0x05)==0x12 and rp(0x09)==0x0F and rp(0x11)==0x01 then
                singleRestored=true
            end
        end
    end
    -- Phase 3: Full volley -> swells through Pal 1 -> Pal 2 -> Pal 3 (max crescendo) + $E0/$20 emphasis
    if frame>=1290 and frame<1460 then
        local fbs=liveFbs()
        if #fbs>0 then
            sawFireball=true
            if (r(0x64FF)%16)>=1 then sawGlowOn=true end
            local emph=math.floor(r(0x6741)/32)*32
            if emph==0xE0 then sawEmphDim=true end
            if emph==0x20 then sawEmphRed=true end
            local p5=rp(0x05)
            if p5==0x06 then
                sawPal1=true
                if rp(0x19)==0x0F and rp(0x1A)==0x06 and rp(0x1B)==0x16 then sawEnemyDim=true end
            elseif p5==0x16 then
                sawPal2=true
            elseif p5==0x27 then
                sawPal3=true
                if rp(0x19)==0x07 and rp(0x1A)==0x17 and rp(0x1B)==0x27
                   and rp(0x1D)==0x0F and rp(0x1E)==0x07 and rp(0x1F)==0x17 then
                    sawEnemyBright=true
                end
            end
            for _,fb in ipairs(fbs) do
                if hasHaloFor(fb) then sawHalo=true end
            end
        end
    end
    if frame>=1470 and frame<1488 then
        if r(0x64FF)==0 and r(0x6741)==0 then glowOffAfter=true end
        if rp(0x05)==0x12 and rp(0x06)==0x01 and rp(0x09)==0x0F and rp(0x0D)==0x0F
           and rp(0x11)==0x01 and rp(0x12)==0x21 and rp(0x13)==0x11
           and rp(0x1A)==0x0F and rp(0x1B)==0x0F and rp(0x1E)==0x0F and rp(0x1F)==0x0F then
            restoredDark=true
        end
    end
    -- Phase 4: Walking left + scrolling ($0725!=0) while firing
    if frame>=1490 and frame<1560 then
        if r(0x0725)~=0 then sawScroll=true end
        local b0=r(0x0301)
        if b0>maxBufLen then maxBufLen=b0 end
        if b0>=0x60 or r(0x0362)~=0 or r(0x0363)~=0xFF then
            bufSafeOk=false
        end
        local hadFb=#liveFbs()>0
        if prevHadFb and hadFb and rp(0x05)==0x12 then
            scrollLitOk=false
        end
        prevHadFb=hadFb
    end
    -- Phase 5: Spell flash ($074B) overlap while fireballs active
    if frame>=1684 and frame<1745 and #liveFbs()>0 then
        if not flashStarted then
            w(0x074B,0x0C)
            flashStarted=true
        elseif r(0x074B)>0 then
            if rp(0x05)==0x06 or rp(0x05)==0x16 or rp(0x05)==0x27 then flashBgLit=true end
        else
            if not flashClearedFrame then flashClearedFrame=frame end
            if frame==flashClearedFrame+1 and rp(0x11)==0x07 then
                flashBarbaRestored=true
            end
        end
    end
    -- Phase 6: Busy 6-enemy cave + enemy projectiles (wait until Phase 5 shots clear)
    if frame==1838 then
        w(0x774,255)
        for k=0,5 do
            w(0xB6+k,1); w(0xA1+k,0x0A); w(0x3C+k,r(0x3B)); w(0x4E+k,(r(0x4D)+32+k*12)%256); w(0x2A+k,0xB0)
            w(0x87+k,1); w(0x30+k,0xA0)
        end
    end
    if frame>=1840 and frame<1900 then
        w(0x774,255) -- keep alive under 6-enemy pressure
        local fbs=liveFbs()
        if #fbs>0 then
            if not busySpawnFrame then busySpawnFrame=frame end
            if (rp(0x05)==0x06 or rp(0x05)==0x16 or rp(0x05)==0x27) and not busyLitFrame then
                busyLitFrame=frame
            end
        end
    end
    if frame==1905 then
        local singleDelay = (singleLitFrame and singleSpawnFrame) and (singleLitFrame - singleSpawnFrame) or 99
        local busyDelay = (busyLitFrame and busySpawnFrame) and (busyLitFrame - busySpawnFrame) or 99
        report:write(string.format('dbg singleDelay=%d busyDelay=%d maxBuf=%02X sawScroll=%s\n',
            singleDelay, busyDelay, maxBufLen, tostring(sawScroll)))
        check(r(0x736)==11 and r(0xB5)==1,'alive in West Hyrule dark grotto')
        check(idleDarkOk,'idle dark cave stays cold/black ($0F) with CAVE_GLOW_ON=0')
        check(singleDelay<=1 and singleCapOk and singleHalo and singleRestored,'single fireball ($6540) ignites to dim ember (delay<=1), caps below max, places $87 halo, and fades back to cold blue')
        check(sawFireball,'fireballs spawned in dark cave')
        check(sawHalo,'rounded behind-BG Pal-2 glow halo ($87) placed around fireballs')
        check(sawGlowOn,'CAVE_GLOW_ON active during firelight envelope')
        check(sawPal1 and sawPal2 and sawPal3 and sawEmphDim and sawEmphRed,'full volley swells smoothly through Pal 1 -> Pal 2 -> Pal 3 with $E0/$20 emphasis')
        check(sawEnemyBright and sawEnemyDim,'dark enemy/halo palettes ($3F19..$3F1F) track dim and max firelight')
        check(glowOffAfter and restoredDark,'dark grotto BG and enemy palettes fade back to cold/black ($0F) after fireballs expire')
        check(bufSafeOk and sawScroll and scrollLitOk,'walking + scrolling ($0725!=0) + firing keeps $0301 < $60, Buffer 1 intact, and lighting uninterrupted')
        check(flashBgLit and flashBarbaRestored,'spell flash keeps BG lit and restores Barba firelight immediately when flash ends')
        check(busyDelay<=1,'busy 6-enemy cave lights immediately with same delay (<=1 frame) as empty cave')
        report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..string.char(10))
        report:close()
        stopScenario(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
