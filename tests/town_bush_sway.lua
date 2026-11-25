dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local frame,errors=0,0
local f=assert(io.open(OUTPUT_DIR..'/town_bush_sway.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end

local bushHashes={}
local baseSignGround=nil
local eastR0Seen={}

local function hashRect(px,x0,y0,x1,y1)
    local h=5381
    for y=y0,y1 do
        local row=y*256
        for x=x0,x1 do
            h=(h*33+px[row+x+1])%4294967296
        end
    end
    return h
end

emu.addMemoryCallback(function()
    if frame>=1150 and frame<1300 then
        local a=r(0x64D5)
        -- Capture R0 writes during VBlank if needed; simpler: read $8001? No, check screen buffer!
    end
end,emu.callbackType.exec,LABELS.UpdateGrassPhase6)

emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then
        b={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        w(0x707,1);w(0x706,0);w(0x769,3);w(0x561,1)
        w(0x701,0);w(0x75C,0);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1)
    end
    if frame>=1140 and frame<1272 and (frame-1140)%16==0 then
        local px=emu.getScreenBuffer()
        -- Bush 1 at x=112..127, y=192..203
        local bh=hashRect(px,112,192,127,203)
        bushHashes[bh]=true
        -- Static regions: bush base y=204..207, sign x=160..175 y=184..207, ground x=96..223 y=208..220
        local sg=string.format('%u:%u:%u',
            hashRect(px,112,204,127,207),
            hashRect(px,160,184,175,207),
            hashRect(px,96,208,223,220))
        if not baseSignGround then baseSignGround=sg
        elseif sg~=baseSignGround then check(false,'static base/sign/ground unchanged at frame '..frame) end
    end
    if frame==1280 then
        local n=0
        for _ in pairs(bushHashes) do n=n+1 end
        check(n==3,'Rauru bush cycles through all 3 sway phases (got '..n..')')
        check(baseSignGround~=nil,'bush base, sign post, and ground stay pixel-identical')
        -- Switch to East Hyrule town (world 2, region 2)
        w(0x707,2);w(0x706,2);w(0x769,3);w(0x561,1)
        w(0x701,0);w(0x75C,0);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1)
    end
    if frame>=1420 and frame<1552 and (frame-1420)%16==0 then
        local px=emu.getScreenBuffer()
        local bh=hashRect(px,112,192,127,203)
        eastR0Seen[bh]=true
    end
    if frame==1560 then
        local n=0
        for _ in pairs(eastR0Seen) do n=n+1 end
        check(n>=3,'East Hyrule town bushes also sway (got '..n..' phases)')
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close()
        stopScenario(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
