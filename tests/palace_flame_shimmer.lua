-- Palaces 1/2/5 ($076E=$0A), 3/4/6 ($076E=$0C), and Great Palace ($076E=$0E):
-- $52/$53 flame sprites in R3 shimmer across 8 CHR variants during VBlank
-- while non-flame R3 tiles stay identical.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local p=emu.memType.nesPpuMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local frame,age,errors=0,0,0
local base,pending=nil,false
local f=assert(io.open(OUTPUT_DIR..'/palace_flame_shimmer.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
local function countKeys(t)
    local n=0
    for _ in pairs(t) do n=n+1 end
    return n
end
local function readRange(baseAddr,len)
    local bytes={}
    for i=0,len-1 do bytes[#bytes+1]=string.char(emu.read(baseAddr+i,p)) end
    return table.concat(bytes)
end

local scenes={
    {name='Palace 1 ($0A)',     world=3, region=0, number=1, code=1, room=0,    expectChr=0x0A},
    {name='Palace 5 ($16/b89)', world=3, region=2, number=5, code=0, room=44,   expectChr=0x16},
    {name='Palace 6 ($18)',     world=4, region=2, number=6, code=1, room=0x32, expectChr=0x18},
    {name='Great Palace ($0C)', world=5, region=2, number=7, code=2, room=0,    expectChr=0x0C},
}
local idx=0
local flameHashes,otherHashes={},{}

local function loadScene(s)
    w(0x707,s.world);w(0x706,s.region);w(0x769,s.world);w(0x561,s.room)
    w(0x568,s.number);w(0x56B,s.number);w(0x56C,s.code)
    w(0x701,0);w(0x75C,0);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1);w(0x748,0x35)
    w(0x770,0xFF);w(0x771,0xFF)
    age=0;flameHashes={};otherHashes={}
end

emu.addEventCallback(function()
    emu.setInput(not base and newGameInput(frame) or {},0)
end,emu.eventType.inputPolled)

emu.addMemoryCallback(function()
    if not pending then return end
    pending=false
    if not base then
        base=emu.createSavestate()
        idx=1
    else
        emu.loadSavestate(base)
    end
    loadScene(scenes[idx])
end,emu.callbackType.exec,0xC07B)

emu.addEventCallback(function()
    frame=frame+1
    if not base then if frame==1000 then pending=true end return end
    if pending then return end
    age=age+1
    local s=scenes[idx]
    if age==100 then
        check(r(0x736)==11 and r(0x707)==s.world and (r(0x76E)&0xFE)==s.expectChr,
            string.format('%s loaded ($0736=%d $0707=%d $076E=%02X)',s.name,r(0x736),r(0x707),r(0x76E)))
    end
    if age>=100 and age<140 then
        flameHashes[readRange(0x1520,32)]=true
        otherHashes[readRange(0x17A0,32)]=true
    end
    if age==140 then
        local nf=countKeys(flameHashes)
        local no=countKeys(otherHashes)
        check(nf==8,string.format('%s flame ($52/$53) cycles through 8 CHR variants (got %d)',s.name,nf))
        check(no==1,string.format('%s non-flame R3 tile ($7A/$7B) stays identical (got %d)',s.name,no))
        idx=idx+1
        if idx<=#scenes then
            pending=true
        else
            f:write(string.format('RESULT errors=%d\n',errors))
            f:close()
            emu.stop(errors==0 and 0 or 1)
        end
    end
end,emu.eventType.endFrame)
