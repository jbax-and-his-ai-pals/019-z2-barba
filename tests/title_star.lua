-- Title screen: the former sword glint (OAM $F8) beside Barba's head is a sky
-- star now. It draws behind the background like the other stars, so the story
-- text covers it, while the water glints ($D4-$F4, $FC) stay in front.
local m=emu.memType.nesDebug
local function r(a)return emu.read(a,m)end
local frame,errors=0,0
local f=assert(io.open(OUTPUT_DIR..'/title_star.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end

local samples,starFront,starsFront,glintsBehind=0,0,0,0
local attrs={}
local storySeen=false

emu.addEventCallback(function()
    frame=frame+1
    if frame>=300 and r(0x0736)>=3 then
        samples=samples+1
        if r(0x0736)==4 then storySeen=true end
        local a=r(0x65FA)
        attrs[a]=true
        if (a&0x20)==0 then starFront=starFront+1 end
        for s=0x6C,0xD0,4 do
            if r(0x6500+s)<0xEF and (r(0x6502+s)&0x20)==0 then starsFront=starsFront+1 end
        end
        for s=0xD4,0xFC,4 do
            if s~=0xF8 and r(0x6500+s)<0xEF and (r(0x6502+s)&0x20)~=0 then glintsBehind=glintsBehind+1 end
        end
    end
    if frame==3000 then
        local n=0
        for _ in pairs(attrs) do n=n+1 end
        check(samples>2000,'title frames sampled ('..samples..')')
        check(storySeen,'story scroll reached')
        check(r(0x6500+0xF8)==0x78 and r(0x6503+0xF8)==0x95,'sky glint stays at Y $78 X $95')
        check(starFront==0,'sky glint never drawn in front ('..starFront..' frames)')
        check(n>=3,'sky glint still twinkles ('..n..' palettes)')
        check(starsFront==0,'other stars stay behind background')
        check(glintsBehind==0,'water glints stay in front')
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close()
        emu.stop()
    end
end,emu.eventType.endFrame)
