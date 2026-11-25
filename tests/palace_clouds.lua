-- Palace entrance parallax clouds: behind-background sprites, stripped static BG clouds,
-- half-speed camera parallax + idle drift, and no interference inside palace rooms.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/palace-clouds.txt','w'))
local fails=0
local function check(ok,msg)
    report:write((ok and 'PASS ' or 'FAIL ')..msg..'\n')
    if not ok then fails=fails+1 end
end

local cases={
    {name='p1-entrance',world=3,region=0,num=1,code=0,room=0,expectClouds=true,walk=120,busy=180},
    {name='p2-entrance',world=3,region=0,num=2,code=1,room=0x0E,expectClouds=true},
    {name='p3-entrance',world=4,region=0,num=3,code=2,room=0,expectClouds=true},
    {name='p4-entrance',world=4,region=1,num=4,code=0,room=0x0F,expectClouds=true,east=true},
    {name='p5-entrance',world=3,region=2,num=5,code=0,room=0x23,expectClouds=true,east=true},
    {name='p6-entrance',world=4,region=2,num=6,code=1,room=0x24,expectClouds=true,east=true},
    {name='gp-entrance',world=5,region=2,num=7,code=2,room=0,expectClouds=true,east=true},
    {name='p3-courtyard',world=4,region=0,num=3,code=2,room=0x06,expectClouds=true},
    {name='gp-bridge',world=5,region=2,num=7,code=2,room=0x37,expectClouds=true,east=true},
    {name='rauru-street',world=1,region=0,num=1,code=0,room=0,expectClouds=true,town=true,walk=50},
    {name='nabooru-street',world=2,region=2,num=1,code=0,room=0,expectClouds=true,town=true,east=true},
    {name='rauru-house',world=1,region=0,num=1,code=0,room=0x19,expectClouds=false,town=true},
    {name='p1-corridor',world=3,region=0,num=1,code=0,room=5,expectClouds=false},
    {name='p3-boss',world=4,region=0,num=3,code=2,room=0x0E,expectClouds=false},
    {name='p2-corridor',world=3,region=0,num=2,code=1,room=0x0F,expectClouds=false},
}

local frame,idx,age,base,done=0,0,0,nil,false
local startDriftX,startCloudX,walkStartCam,walkStartCloudX,walkStartDriftX
local holdRight,holdJump,holdFire=false,false,false
local busyClips=0

local function countCloudSprites(c)
    local n,badAttr,firstX=0,0,nil
    local t0=c.town and 0x89 or 0xC1
    local t1=t0+2
    local t2=t0+4
    local wantAttr=(c.town and 0x21 or 0x23)+(c.east and 0x40 or 0)
    for o=0x68,0xFC,4 do
        local y=r(0x6500+o)
        local t=r(0x6501+o)
        local a=r(0x6502+o)
        local x=r(0x6503+o)
        if y<0xF0 and (t==t0 or t==t1 or t==t2) then
            n=n+1
            if a~=wantAttr then badAttr=badAttr+1 end
            if not firstX then firstX=x end
        end
    end
    return n,badAttr,firstX
end

local function countStaticClouds(c)
    local n=0
    local lo=c.town and 0xC4 or 0xC2
    local hi=c.town and 0xC6 or 0xC4
    for p=0,r(0xD1) do
        for off=0,0xCF do
            local t=r(0x6000+p*0xD0+off)
            if t>=lo and t<=hi then n=n+1 end
        end
    end
    return n
end

local function cloudPattern(c)
    local bytes={}
    local baseAddr=c.town and 0x1880 or 0x1C00
    for addr=baseAddr,baseAddr+0x5F do
        bytes[#bytes+1]=string.char(emu.read(addr,emu.memType.nesPpuMemory))
    end
    return table.concat(bytes)
end

local expectedPattern

emu.addEventCallback(function()
    if frame<1050 then emu.setInput(newGameInput(frame),0)
    else emu.setInput({right=holdRight,a=holdJump,b=holdFire},0) end
end,emu.eventType.inputPolled)

emu.addMemoryCallback(function()
    if done or frame<1050 or age~=0 then return end
    if not base then base=emu.createSavestate() end
    idx=idx+1
    local c=cases[idx]
    if not c then
        done=true
        report:write('RESULT '..(fails==0 and 'PASS' or 'FAIL')..'\n')
        report:close()
        stopScenario(fails==0 and 0 or 1)
        return
    end
    assert(emu.loadSavestate(base))
    holdRight=false; holdJump=false; holdFire=false; busyClips=0
    w(0x707,c.world); w(0x706,c.region); w(0x769,c.town and 3 or (c.world==5 and 5 or 4))
    w(0x561,c.room); w(0x568,c.num-1); w(0x56B,c.num); w(0x56C,c.code)
    w(0x701,0); w(0x75C,c.town and 1 or 0); w(0x704,0); w(0x736,0); w(0x73D,0); w(0x726,1); w(0x748,0x34+c.code)
    age=1
end,emu.callbackType.exec,0xC07B)

emu.addEventCallback(function()
    frame=frame+1
    if done or age==0 then return end
    age=age+1
    local c=cases[idx]
    if age==90 then
        check(r(0x736)==0x0B and r(0x707)==c.world and r(0x561)==c.room,c.name..' loaded the expected room')
        local n,badAttr,firstX=countCloudSprites(c)
        local staticClouds=countStaticClouds(c)
        local barbaHeadY=r(0x65C4)
        if c.expectClouds then
            check(r(0x64EE)==0,c.name..' leaves OW_PARALLAX_LINE=0 (no building shear)')
            check(staticClouds==0,c.name..' stripped static BG clouds ($C2-$C4)')
            check(n>=4 and badAttr==0,string.format('%s drew %d behind-BG cloud sprites (badAttr=%d)',c.name,n,badAttr))
            local pattern=cloudPattern(c)
            if not expectedPattern then expectedPattern=pattern end
            check(pattern:find('[^%z]') and pattern==expectedPattern,c.name..' selected the cloud sprite patterns')
            check(barbaHeadY<0xF0 and r(0x65C5)~=0xC1 and r(0x65C5)~=0xC3 and r(0x65C5)~=0xC5,
                c.name..' preserved Barba head slot $C4')
            startDriftX=r(0x64FC)
            startCloudX=firstX
            if c.name=='p1-entrance' then
                local png=emu.takeScreenshot()
                local f=assert(io.open(OUTPUT_DIR..'/palace-clouds-p1.png','wb'))
                f:write(png); f:close()
            elseif c.name=='gp-entrance' then
                local png=emu.takeScreenshot()
                local f=assert(io.open(OUTPUT_DIR..'/palace-clouds-gp.png','wb'))
                f:write(png); f:close()
            elseif c.name=='rauru-street' then
                local ashTile,fireTile,cloudLeft={},{},{}
                for i=0,31 do
                    ashTile[i+1]=string.char(emu.read(0x1800+i,emu.memType.nesPpuMemory))
                    fireTile[i+1]=string.char(emu.read(0x1840+i,emu.memType.nesPpuMemory))
                    cloudLeft[i+1]=string.char(emu.read(0x1880+i,emu.memType.nesPpuMemory))
                end
                local cStr=table.concat(cloudLeft)
                check(table.concat(ashTile)~=cStr and table.concat(fireTile)~=cStr,
                    'rauru-street preserved AshTileRight ($80) and fireball ($84) patterns')
                local png=emu.takeScreenshot()
                local f=assert(io.open(OUTPUT_DIR..'/palace-clouds-rauru.png','wb'))
                f:write(png); f:close()
            end
        else
            check(n==0,c.name..' has no entrance cloud sprites inside corridor')
            age=0
        end
    elseif c.expectClouds and age==130 then
        local _,_,x=countCloudSprites(c)
        local drift=(startDriftX-r(0x64FC)+128)%256-128
        local distance=c.east and drift or -drift
        check(distance>=2 and distance<=3 and startCloudX and x and x-startCloudX==drift,
            string.format('%s clouds drift %s while idle (screen delta=%s)',
                c.name,c.east and 'right' or 'left',tostring(x and startCloudX and x-startCloudX)))
        if c.walk then
            holdRight=true
            walkStartCam=r(0x72A)*256+r(0xFD)
            walkStartCloudX=x
            walkStartDriftX=r(0x64FC)
        else
            age=0
        end
    elseif c.walk and age>130 and age<130+c.walk then
        holdJump=(age%32)<18
    elseif c.walk and age==130+c.walk then
        holdRight=false; holdJump=false
        local camNow=r(0x72A)*256+r(0xFD)
        local n,_,xNow=countCloudSprites(c)
        local dCam=camNow-walkStartCam
        local expectedShift=camNow//2-walkStartCam//2+r(0x64FC)-walkStartDriftX
        check(dCam>=10 and n>=4 and xNow and walkStartCloudX and walkStartCloudX-xNow==expectedShift,
            string.format('%s camera walked +%dpx and clouds scrolled at half speed plus drift (%s -> %s)',
                c.name,dCam,tostring(walkStartCloudX),tostring(xNow)))
        local png=emu.takeScreenshot()
        local f=assert(io.open(OUTPUT_DIR..'/palace-clouds-p1-walk.png','wb'))
        f:write(png); f:close()
        if not c.busy then age=0 end
    elseif c.busy and age>130+c.walk and age<130+c.walk+c.busy then
        holdRight=(age%90)<60
        holdJump=(age%36)<20
        holdFire=(age%8)<2
        local t0=c.town and 0x89 or 0xC1
        local t1,t2=t0+2,t0+4
        for o=0x68,0xFC,4 do
            local y=r(0x6500+o)
            local t=r(0x6501+o)
            if y<0xF0 and (t==t0 or t==t1 or t==t2) then
                for dy=0,15 do
                    local sl=y+1+dy
                    local earlier=0
                    for p=0,o-4,4 do
                        local oy=r(0x6500+p)
                        if oy<0xF0 and sl>=oy+1 and sl<=oy+16 then earlier=earlier+1 end
                    end
                    if earlier>=8 then busyClips=busyClips+1 end
                end
            end
        end
    elseif c.busy and age==130+c.walk+c.busy then
        holdRight=false; holdJump=false; holdFire=false
        check(busyClips==0,string.format('%s had zero cloud scanline clips during busy jumps/fireballs (clips=%d)',c.name,busyClips))
        age=0
    end
end,emu.eventType.endFrame)
