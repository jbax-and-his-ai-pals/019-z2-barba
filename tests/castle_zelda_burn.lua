-- North Palace: shooting Zelda scorches her (flame -> char) without breaking
-- metatiles, and triggers Barba's "OOPS..." sprite shout above him.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local p=emu.memType.nesPpuMemory
local function r(a)return emu.read(a,m)end
local FLAME={[0x56]=true,[0x57]=true,[0x58]=true,[0x59]=true}
local CHAR={[0x5A]=true,[0x5B]=true,[0x5C]=true,[0x5D]=true}
local frame,errors=0,0
local metatiles,nametable=nil,nil
local maxFlame,maxChar,blanked,foreign=0,0,0,0
local flameSeenAt,charSeenAt,shoutSeenAt=nil,nil,nil
local shoutTiles={}
local f=assert(io.open(OUTPUT_DIR..'/castle_zelda_burn.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
local function snapMeta()local t={} for a=0x6000,0x633F do t[#t+1]=r(a) end return t end
local function snapNT()local t={} for a=0x2000,0x27BF do t[a]=emu.read(a,p) end return t end
local function counts()
    local fl,ch=0,0
    for a=0x2000,0x27BF do
        if (a%0x400)<0x3C0 then
            local t=emu.read(a,p)
            if FLAME[t] then fl=fl+1 elseif CHAR[t] then ch=ch+1 end
        end
    end
    return fl,ch
end
emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then
        b={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
        -- Walk slightly left, then turn right, jump, and breathe across Zelda on the altar.
        if frame<1020 then
            b.left=true
        elseif frame<1024 then
            b.right=true
        elseif frame>=1034 then
            local t=frame-1034
            if t>=0 and t<30 then
                b.a=t<18
                b.b=t>=8 and t<12
            end
        end
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if frame==1030 then
        check(r(0x736)==11 and r(0x707)==0 and r(0x706)==0 and r(0x561)==0,'North Palace loaded')
        metatiles=snapMeta();nametable=snapNT()
    end
    if frame>=1034 and frame<=1190 then
        local fl,ch=counts()
        if fl>maxFlame then maxFlame=fl end
        if ch>maxChar then maxChar=ch end
        if fl>0 and not flameSeenAt then flameSeenAt=frame end
        if ch>0 and not charSeenAt then charSeenAt=frame end
        if fl>0 and frame-(flameSeenAt or frame)==4 then screenshot('castle-zelda-flame') end
        if ch>0 and frame-(charSeenAt or frame)==4 then screenshot('castle-zelda-char') end
        if r(0x6467)==10 and r(0x6465)==0xFF then
            if not shoutSeenAt then
                shoutSeenAt=frame
            elseif #shoutTiles==0 then
                for _,o in ipairs({0x28,0x2C,0x30,0x34,0x40}) do
                    if r(0x200+o)<0xF8 then shoutTiles[#shoutTiles+1]=r(0x201+o) end
                end
            end
        end
    end
    if frame==1190 then
        local fl,ch=counts()
        local metaOk=true
        for i,v in ipairs(metatiles) do if r(0x5FFF+i)~=v then metaOk=false;break end end
        for a,before in pairs(nametable) do
            if (a%0x400)<0x3C0 then
                local now=emu.read(a,p)
                if now~=before and not FLAME[now] and not CHAR[now] then
                    if now==0x2C then blanked=blanked+1 else foreign=foreign+1 end
                end
            end
        end
        check(metaOk,'metatiles unchanged')
        check(maxFlame>=4,'flame tiles appeared on Zelda ('..maxFlame..')')
        check(maxChar>=4,'char tiles replaced flame ('..maxChar..')')
        check(charSeenAt and flameSeenAt and charSeenAt>flameSeenAt,'flame precedes char')
        check(blanked==0 and foreign==0,'only scorch tiles changed in nametable (blanked='..blanked..' foreign='..foreign..')')
        check(shoutSeenAt~=nil,'Barba shout word 10 triggered')
        check(#shoutTiles==5,'shout drew 5 visible OAM glyphs (got '..#shoutTiles..')')
        check(r(0x6467)==0,'shout expired cleanly by frame 1180')
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close()
        stopScenario(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
