-- Busy-room probe over generated checkpoints (driven by tools/busy_rooms.py,
-- which prepends BUSY_PACK, BUSY_STATES and BUSY_FRAMES). Autopilot: walk,
-- turn, breathe every 6 frames, jump, look up. Per checkpoint it reports:
--   lag        frames with no NMI game update
--   workMax    worst side-view NMI through the final bank-restore entry
--   nmiMax     worst full side-view NMI (budget ~29,780)
--   otherNmiMax  worst full NMI outside steady side-view play, including room loads
--   hudBad     side-view frames that start with a non-zero status-bar scroll
--   late       NMIs that reached the next VBlank recovery handler
--   maxLine / framesOver8   shadow OAM candidates per scanline
--   peak       cycle breakdown on the worst full side-view NMI. Mode includes
--              enemy, enemyShot, update and playerDraw.
-- RESULT PASS when hudBad is 0 everywhere.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/busy-rooms.txt','w'))
local NL=string.char(10)
local idx,age,frame,pending=0,0,0,false
local cur,load
local nmiStart,nmis=nil,0
local nmiSideView=false
local stageStarts,stageCycles={},{}
local totalBad=0
local function cycles()return emu.getState()['cpu.cycleCount']end
local function gateOn()return r(0x736)==0x0B and r(0x74C)<2 and r(0x726)==0 end
emu.addMemoryCallback(function()
    if pending then pending=false;load();return end
    nmiStart=cycles();nmis=nmis+1;nmiSideView=gateOn()
    stageStarts,stageCycles={},{}
end,emu.callbackType.exec,0xC07B)
local function profile(name,entry,exit)
    if not entry or not exit then return end
    emu.addMemoryCallback(function()
        if nmiSideView and nmiStart and age>20 then stageStarts[name]=cycles() end
    end,emu.callbackType.exec,entry)
    emu.addMemoryCallback(function()
        local start=stageStarts[name]
        if start then
            stageCycles[name]=(stageCycles[name] or 0)+cycles()-start
            stageStarts[name]=nil
        end
    end,emu.callbackType.exec,exit)
end
profile('clear',0xC182,0xC185)
profile('mode',0xC185,0xC188)
profile('enemy',0xD5CC,0xD5CF)
profile('enemyShot',0xD5D1,0xD5D4)
profile('update',0xD50D,0xD510)
profile('playerDraw',0xD52D,0xD530)
profile('copy',LABELS.CopyOamShadow6,LABELS.PrioritizeRoomOam6)
emu.addMemoryCallback(function()
    if nmiStart and nmiSideView and cur and age>20 and gateOn() then
        cur.workMax=math.max(cur.workMax,cycles()-nmiStart)
    end
end,emu.callbackType.exec,0xC1A3)
emu.addMemoryCallback(function()
    if not(nmiStart and cur and age>20)then nmiStart=nil;return end
    local n=cycles()-nmiStart;nmiStart=nil
    if nmiSideView and gateOn() then
        if n>cur.nmiMax then
            cur.nmiMax=n
            cur.peak=stageCycles
        end
    else
        cur.otherNmiMax=math.max(cur.otherNmiMax,n)
    end
end,emu.callbackType.exec,0xC1B5)
if LABELS.VblankOverrun6 then
    emu.addMemoryCallback(function()
        if cur and age>20 and nmiSideView and gateOn() and r(0x8506)==0 then cur.late=cur.late+1 end
    end,emu.callbackType.exec,LABELS.VblankOverrun6)
end
emu.addEventCallback(function()
    if not cur or age<=20 or not gateOn()then return end
    local s=emu.getState()
    if (s['ppu.tmpVideoRamAddr']&0x041F)~=0 or s['ppu.xScroll']~=0 then cur.hudBad=cur.hudBad+1 end
end,emu.eventType.startFrame)
local function scanlines()
    local count,mx,over={},0,0
    for i=0,63 do
        local y=r(0x6500+i*4)
        if y<0xEF then for line=y+1,y+16 do count[line]=(count[line] or 0)+1 end end
    end
    for line,c in pairs(count)do if line<240 then mx=math.max(mx,c);if c>8 then over=over+1 end end end
    return mx,over
end
load=function()
    if cur then
        report:write(string.format('%-26s frames=%d lag=%d workMax=%d nmiMax=%d otherNmiMax=%d late=%d hudBad=%d maxLine=%d framesOver8=%d'..NL,
            cur.name,cur.frames,cur.lag,cur.workMax,cur.nmiMax,cur.otherNmiMax,cur.late,cur.hudBad,cur.maxLine,cur.over8))
        if cur.peak then
            report:write('  peak')
            for _,name in ipairs({'clear','mode','enemy','enemyShot','update','playerDraw','copy'}) do
                report:write(string.format(' %s=%d',name,cur.peak[name] or 0))
            end
            report:write(NL)
        end
        report:flush();totalBad=totalBad+cur.hudBad
    end
    idx=idx+1
    if not BUSY_STATES[idx]then
        report:write('RESULT '..(totalBad==0 and 'PASS' or 'FAIL')..NL);report:close()
        stopScenario(totalBad==0 and 0 or 1);return
    end
    local f=assert(io.open(BUSY_PACK..'/'..BUSY_STATES[idx]..'.mss','rb'))
    assert(emu.loadSavestate(f:read('*a')),BUSY_STATES[idx]..' loads');f:close()
    cur={name=BUSY_STATES[idx],frames=0,lag=0,workMax=0,nmiMax=0,otherNmiMax=0,late=0,hudBad=0,maxLine=0,over8=0}
    age=0;nmis=0;nmiStart=nil
end
emu.addEventCallback(function()
    local b={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
    if cur and age>20 then
        local t=age%240
        b.right=t<150 or t>=200;b.left=t>=150 and t<200
        b.b=(age%6)<2;b.a=(age%70)<10
        b.up=(age%180)>=100 and (age%180)<130
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if idx==0 then if frame==30 then pending=true end return end
    age=age+1
    if r(0x736)==0x0B and age>20 then
        w(0x774,255);w(0x773,255) -- keep meters up so the fixture stays alive
        cur.frames=cur.frames+1
        if nmis==0 then cur.lag=cur.lag+1 end
        local mx,over=scanlines();cur.maxLine=math.max(cur.maxLine,mx)
        if over>0 then cur.over8=cur.over8+1 end
    end
    nmis=0
    if age==BUSY_FRAMES then pending=true end
end,emu.eventType.endFrame)
