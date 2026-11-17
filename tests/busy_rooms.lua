-- Busy-room probe over generated checkpoints (driven by tools/busy_rooms.py,
-- which prepends BUSY_PACK, BUSY_STATES and BUSY_FRAMES). Autopilot: walk,
-- turn, breathe every 6 frames, jump, look up. Per checkpoint it reports:
--   lag        frames with no NMI game update
--   nmiMax     worst NMI work in cycles (budget ~29,780)
--   hudBad     side-view frames that START with a non-zero status-bar scroll
--              (the lag-frame jitter LateSplit fixes; an overrun longer than
--              vblank is the known uncatchable case)
--   late       NMIs that ended in the next vblank and were recovered
--   maxLine / framesOver8   sprites per scanline (flicker pressure)
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
local totalBad=0
local function cycles()return emu.getState()['cpu.cycleCount']end
local function gateOn()return r(0x736)==0x0B and r(0x74C)<2 and r(0x726)==0 end
emu.addMemoryCallback(function()
    if pending then pending=false;load();return end
    nmiStart=cycles();nmis=nmis+1
end,emu.callbackType.exec,0xC07B)
emu.addMemoryCallback(function()
    if not(nmiStart and cur and age>20)then nmiStart=nil;return end
    local n=cycles()-nmiStart;nmiStart=nil
    cur.nmiMax=math.max(cur.nmiMax,n)
end,emu.callbackType.exec,0xC1B5)
if LABELS and LABELS.LateSplit then
    emu.addMemoryCallback(function()
        if cur and age>20 and r(0x8506)==0x2E then cur.late=cur.late+1 end
    end,emu.callbackType.exec,LABELS.LateSplit)
end
emu.addEventCallback(function()
    if not cur or age<=20 or not gateOn()then return end
    local s=emu.getState()
    if (s['ppu.tmpVideoRamAddr']&0x041F)~=0 or s['ppu.xScroll']~=0 then cur.hudBad=cur.hudBad+1 end
end,emu.eventType.startFrame)
local function scanlines()
    local count,mx,over={},0,0
    local tall=emu.getState()['ppu.control.largeSprites'] and 16 or 8
    for i=0,63 do
        local y=r(0x200+i*4)
        if y<0xEF then for line=y+1,y+tall do count[line]=(count[line] or 0)+1 end end
    end
    for line,c in pairs(count)do if line<240 then mx=math.max(mx,c);if c>8 then over=over+1 end end end
    return mx,over
end
load=function()
    if cur then
        report:write(string.format('%-26s frames=%d lag=%d nmiMax=%d late=%d hudBad=%d maxLine=%d framesOver8=%d'..NL,
            cur.name,cur.frames,cur.lag,cur.nmiMax,cur.late,cur.hudBad,cur.maxLine,cur.over8))
        report:flush();totalBad=totalBad+cur.hudBad
    end
    idx=idx+1
    if not BUSY_STATES[idx]then
        report:write('RESULT '..(totalBad==0 and 'PASS' or 'FAIL')..NL);report:close()
        stopScenario(totalBad==0 and 0 or 1);return
    end
    local f=assert(io.open(BUSY_PACK..'/'..BUSY_STATES[idx]..'.mss','rb'))
    assert(emu.loadSavestate(f:read('*a')),BUSY_STATES[idx]..' loads');f:close()
    cur={name=BUSY_STATES[idx],frames=0,lag=0,nmiMax=0,late=0,hudBad=0,maxLine=0,over8=0}
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
