-- Battle performance probe: Palace 1 corridor (same fixture as hud_timing.lua),
-- idle versus repeated five-shot volleys with enemies present. Reports lag
-- frames (no NMI game update that frame), NMI work cycles and Barba routine
-- costs. Lua callbacks do not consume emulated CPU cycles.
-- python tools/emulator_test.py tests/perf_upward.lua
-- Also run against build/baseline/barba.nes: that build emits forward shots.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local frame=0
local report=assert(io.open(OUTPUT_DIR..'/perf-upward.txt','w'))
local csv=assert(io.open(OUTPUT_DIR..'/perf-upward.csv','w'))
csv:write('frame,phase,nmis,nmiCycles,projCycles,extraCycles,collisionCalls,nativeEnemyCalls,liveShots,enemies,maxLineSprites,overLines\n')
local START,IDLE_END,STOP=1300,1600,2500
local phases={'idle','upward'}
local function phase()return frame<IDLE_END and 'idle' or 'upward'end
local function active()return frame>=START and frame<STOP end
local stats={}
for _,p in ipairs(phases)do
    stats[p]={frames=0,lag=0,maxNmi=0,sumNmi=0,nmis=0,maxProj=0,sumProj=0,maxExtra=0,sumExtra=0,
        maxColl=0,maxBlocks=0,sumBlocks=0,maxLine=0,overFrames=0,overLines=0,overBudget=0}
end
local cur={nmis=0,nmi=0,proj=0,extra=0,coll=0,native=0,blocks=0}
local function cycles()return emu.getState()['cpu.cycleCount']end
local nmiStart,projStart,extraStart
local L=LABELS or {}
local nmiRti=L.NmiRti or 0xC1B2
emu.addMemoryCallback(function()nmiStart=cycles();cur.nmis=cur.nmis+1 end,emu.callbackType.exec,0xC07B)
emu.addMemoryCallback(function()
    if nmiStart then cur.nmi=cur.nmi+cycles()-nmiStart;nmiStart=nil end
end,emu.callbackType.exec,nmiRti)
local upwardShots=0
local sixEnemyFrames=0
if L.BarbaVolleyPlaced then
 emu.addMemoryCallback(function()
  if active() and frame>=IDLE_END then
   local x=emu.getState()['cpu.x']
   if (r(0x5FC+x)&0x40)~=0 then upwardShots=upwardShots+1 end
  end
 end,emu.callbackType.exec,L.BarbaVolleyPlaced)
end
-- Fixture edits occur outside emulated timing; all six enemy AIs and collision
-- paths run normally. Keep six palace Bots alive, arranged ahead of Barba.
emu.addMemoryCallback(function()
 if not active() then return end
 w(0x4D,96);w(0x3B,0);w(0xCC,96);w(0x29,176);w(0x57D,0);w(0x479,1)
 w(0x796,0x14);w(0x9F,1);w(0x5F,1);w(0x70,0)
 for i=0,5 do
  w(0xB6+i,1);w(0xA1+i,0x04);w(0xA8+i,0);w(0xAF+i,0);w(0xC2+i,127);w(0x40E+i,0)
  w(0x4E+i,144+i*16);w(0x3C+i,0);w(0x2A+i,176);w(0x71+i,0)
 end
end,emu.callbackType.exec,0xD4FE)
-- Set air/attack inputs after native movement, before the real scheduler.
emu.addMemoryCallback(function()
 if not active() then return end
 w(0x479,1);w(0x17,1);w(0xF7,r(0xF7)|0x08)
 if frame>=IDLE_END then
  local t=(frame-IDLE_END)%90
  if t==2 then w(0x400,2);w(0x495,1);w(0x50A,5)end
  if t>=12 then w(0x400,0)end
 end
end,emu.callbackType.exec,L.BarbaProjectiles)

-- Final RTS of each routine is the byte before the next exported label.
local function span(entry,exitLabel,key)
    if not(L[entry] and L[exitLabel])then return end
    local start
    emu.addMemoryCallback(function()start=cycles()end,emu.callbackType.exec,L[entry])
    emu.addMemoryCallback(function()
        if start then cur[key]=cur[key]+cycles()-start;start=nil end
    end,emu.callbackType.exec,L[exitLabel]-1)
end
span('BarbaProjectiles','BarbaEmitOne','proj')
span('BarbaExtraUpdate','BarbaEnemyFire','extra')
span('BarbaBlocks','ExtraOam','blocks')
if L.ExtraCollision then
    emu.addMemoryCallback(function()cur.coll=cur.coll+1 end,emu.callbackType.exec,L.ExtraCollision)
end
if L.NativeEnemyFire then
    emu.addMemoryCallback(function()cur.native=cur.native+1 end,emu.callbackType.exec,L.NativeEnemyFire)
end
local function liveShots()
    local n=0
    for s=0,1 do local v=r(0x8D+s);if v>0 and v<0x80 then n=n+1 end end
    for _,b in ipairs({0x6400,0x6410,0x6420})do local v=r(b);if v>0 and v<0x80 then n=n+1 end end
    return n
end
local function enemies()
    local n=0
    for s=0,5 do if r(0xB6+s)~=0 then n=n+1 end end
    return n
end
local function scanlines()
    local count={}
    local mx,over=0,0
    for i=0,63 do
        local y=r(0x200+i*4)
        if y<0xEF then
            for line=y+1,y+16 do count[line]=(count[line] or 0)+1 end
        end
    end
    for line,c in pairs(count)do
        if line<240 then
            if c>mx then mx=c end
            if c>8 then over=over+1 end
        end
    end
    return mx,over
end
emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then
        b={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
        if frame>=IDLE_END then
            local t=(frame-IDLE_END)%60
            b.b=t>=2 and t<5
            -- Controller input plus an explicit scheduler gate below.
            b.up=true -- hold Up; pin airborne geometry below for a repeatable stress fixture
        end
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        w(0x707,3);w(0x706,0);w(0x769,3);w(0x561,5)
        w(0x568,0);w(0x56B,1);w(0x56C,0);w(0x701,0);w(0x75C,0);w(0x704,0)
        w(0x736,0);w(0x73D,0);w(0x726,1)
        w(0x777,4);w(0x778,8);w(0x779,8);w(0x783,8);w(0x784,8)
        w(0x775,0);w(0x776,0);w(0x770,7);w(0x771,0xD0)
    end
    if frame==1080 then w(0x4D,96);w(0x3B,0);w(0x29,144);w(0x57D,0);w(0x479,0)end
    if active()then
        -- Keep the fixture alive and comparable; Fire off (ordinary breath).
        w(0x774,255);w(0x773,255);w(0x76F,0)
        local p=stats[phase()]
        if enemies()==6 then sixEnemyFrames=sixEnemyFrames+1 end
        local mx,over=scanlines()
        p.frames=p.frames+1
        if cur.nmis==0 then p.lag=p.lag+1 end
        p.nmis=p.nmis+cur.nmis
        p.maxNmi=math.max(p.maxNmi,cur.nmi);p.sumNmi=p.sumNmi+cur.nmi
        if cur.nmi>27000 then p.overBudget=p.overBudget+1 end
        p.maxProj=math.max(p.maxProj,cur.proj);p.sumProj=p.sumProj+cur.proj
        p.maxExtra=math.max(p.maxExtra,cur.extra);p.sumExtra=p.sumExtra+cur.extra
        p.maxColl=math.max(p.maxColl,cur.coll)
        p.maxBlocks=math.max(p.maxBlocks,cur.blocks);p.sumBlocks=p.sumBlocks+cur.blocks
        p.maxLine=math.max(p.maxLine,mx)
        if over>0 then p.overFrames=p.overFrames+1;p.overLines=p.overLines+over end
        csv:write(string.format('%d,%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n',frame,phase(),cur.nmis,cur.nmi,
            cur.proj,cur.extra,cur.coll,cur.native,liveShots(),enemies(),mx,over))
        if frame==IDLE_END+150 or frame==IDLE_END+400 then screenshot('perf-upward-'..frame)end
    end
    cur={nmis=0,nmi=0,proj=0,extra=0,coll=0,native=0,blocks=0}
    if frame==STOP then
        for _,name in ipairs(phases)do
            local p=stats[name];local n=math.max(1,p.frames)
            report:write(string.format('%s frames=%d lagFrames=%d nmiAvg=%d nmiMax=%d nearBudget(>27000)=%d projAvg=%d projMax=%d extraAvg=%d extraMax=%d collisionCallsMax=%d blocksAvg=%d blocksMax=%d maxSpritesOnLine=%d framesOver8=%d linesOver8=%d\n',
                name,p.frames,p.lag,p.sumNmi//n,p.maxNmi,p.overBudget,p.sumProj//n,p.maxProj,
                p.sumExtra//n,p.maxExtra,p.maxColl,p.sumBlocks//n,p.maxBlocks,p.maxLine,p.overFrames,p.overLines))
        end
        local ok=stats.upward.lag==0 and stats.upward.maxNmi<29700 and sixEnemyFrames>=1198
            and (not L.BarbaSetThrusts or upwardShots>=25)
        report:write('upwardShots='..upwardShots..' sixEnemyFrames='..sixEnemyFrames..'\n')
        report:write('RESULT '..(ok and 'PASS' or 'FAIL')..'\n')
        report:close();csv:close();stopScenario(ok and 0 or 1)
    end
end,emu.eventType.endFrame)
