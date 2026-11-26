-- Barba stress + profiler probe. Driven by tools/perf_stress.py, which prepends PK_PACK,
-- PK_CASES, PK_PROFILE, PK_TAG (and optionally PK_PATCHES, PK_OVERLAY, PK_DROPS).
-- Per case: load a checkpoint, play aggressively (fire every few frames, jump, approach/back
-- off the nearest enemy, crouch and up fire) and record per frame: lag, NMI wall cycles,
-- estimated NMI/IRQ cycles, stage costs, live shots, enemies, enemy shots, roar, and the
-- DMA-shadow (8x16, 8 per scanline) drops by object class. With PK_PROFILE every executed
-- instruction is charged base 6502 cycles (+branch taken/page) to (phase, context, bank, pc).
-- Outputs build/<tag>-frames.csv, <tag>-cases.txt, <tag>-profile.csv.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local NL=string.char(10)
local TAG=PK_TAG or 'stress'
local C,age=nil,0
local csv=assert(io.open(OUTPUT_DIR..'/'..TAG..'-frames.csv','w'))
local sum=assert(io.open(OUTPUT_DIR..'/'..TAG..'-cases.txt','w'))
local prof=PK_PROFILE and assert(io.open(OUTPUT_DIR..'/'..TAG..'-profile.csv','w')) or nil
csv:write('case,age,gate,lag,nmis,wall,est,irqEst,irqN,stEnemyLoop,stEnemy,stEShot,stBarba,stPhys,stDraw,stBlocks,stMode,stTail,stPre,stPost,stClear,swaps,'..
  'shotsN,shotsX,enemies,eshots,roar,room,maxLine,linesOver8,dropEntries,dropLines,dropBarba,dropFire,dropEnemy,dropEShot,dropOther,'..
  'togBarba,togEnemy,togFire,hudBad,late,px,py,excess,excessNoB,exNoFire,exNoHead,exNoBody,exNoTrail,enDrop,trDrop,enDropTL,trDropTL'..NL)
if prof then prof:write('case,kind,ctx,bank,pc,cycles'..NL) end

if PK_PATCHES then
  local plog=assert(io.open(OUTPUT_DIR..'/'..TAG..'-patches.txt','w'))
  for _,pt in ipairs(PK_PATCHES) do
    local off=pt[1]
    for i=2,#pt do
      local before=emu.read(off+i-2,emu.memType.nesPrgRom)
      emu.write(off+i-2,pt[i],emu.memType.nesPrgRom)
      plog:write(string.format('prg $%05X: %02X -> %02X (readback %02X)'..NL,off+i-2,before,pt[i],emu.read(off+i-2,emu.memType.nesPrgRom)))
    end
  end
  plog:close()
end
-- 6502 base cycles (official + unofficial), index op+1.
local CYC={
7,6,2,8,3,3,5,5,3,2,2,2,4,4,6,6, 2,5,2,8,4,4,6,6,2,4,2,7,4,4,7,7,
6,6,2,8,3,3,5,5,4,2,2,2,4,4,6,6, 2,5,2,8,4,4,6,6,2,4,2,7,4,4,7,7,
6,6,2,8,3,3,5,5,3,2,2,2,3,4,6,6, 2,5,2,8,4,4,6,6,2,4,2,7,4,4,7,7,
6,6,2,8,3,3,5,5,4,2,2,2,5,4,6,6, 2,5,2,8,4,4,6,6,2,4,2,7,4,4,7,7,
2,6,2,6,3,3,3,3,2,2,2,2,4,4,4,4, 2,6,2,6,4,4,4,4,2,5,2,5,5,5,5,5,
2,6,2,6,3,3,3,3,2,2,2,2,4,4,4,4, 2,5,2,5,4,4,4,4,2,4,2,4,4,4,4,4,
2,6,2,8,3,3,5,5,2,2,2,2,4,4,6,6, 2,5,2,8,4,4,6,6,2,4,2,7,4,4,7,7,
2,6,2,8,3,3,5,5,2,2,2,2,4,4,6,6, 2,5,2,8,4,4,6,6,2,4,2,7,4,4,7,7}
local BR={[0x10]=true,[0x30]=true,[0x50]=true,[0x70]=true,[0x90]=true,[0xB0]=true,[0xD0]=true,[0xF0]=true}

-- MMC3 PRG tracking (SwapPRG writes R6 then R7).
local sel,R6,R7=0,0,1
SWAP_SAME,SWAP_ALL=0,0
local SWAP_SITE_SAME={}
emu.addMemoryCallback(function(a,v)
  if (a&1)==0 then sel=v&7
  elseif sel==6 then
    if PK_MEASURING then SWAP_ALL=SWAP_ALL+1;if v==R6 then SWAP_SAME=SWAP_SAME+1 end end
    R6=v
  elseif sel==7 then R7=v end
end,emu.callbackType.write,0x8000,0x9FFF)
local function syncBanks()
  local s=emu.getState();R6=s['mapper.mmc3Registers6'] or 0;R7=s['mapper.mmc3Registers7'] or 1
end
local function cycles()return emu.getState()['cpu.cycleCount']end

-- Inclusive stage spans (fixed-bank JSR site -> return point), measured in NMI-context est cycles.
local SPANS={ {'enemyLoop',0xD504,0xD507},{'enemy',0xD5CC,0xD5CF},{'eshot',0xD5D1,0xD5D4},
  {'barba',0xD50D,0xD510},{'phys',0xD510,0xD513},{'draw',0xD52D,0xD530},{'blocks',0xD535,0xD538},
  {'mode',0xC185,0xC188},{'tail',0xC188,0xC18B},{'pre',0xC07B,0xC182},{'post',0xC188,0xC1B2},
  {'clear',0xC182,0xC185} }
local spanStart,spanEnd={},{}
for i,s in ipairs(SPANS) do
  spanStart[s[2]]=spanStart[s[2]] or {};table.insert(spanStart[s[2]],i)
  spanEnd[s[3]]=spanEnd[s[3]] or {};table.insert(spanEnd[s[3]],i)
end
-- bank-switch call sites: JSR/JMP to SwapPRG ($FFCC), SwapToPRG0 ($FFC5), SwapToSavedPRG ($FFC9)
local SWAPT={[0xFFCC]=true,[0xFFC5]=true,[0xFFC9]=true}
local swapSites={}
local swapFrame=0

local PROF=PK_PROFILE and true or false
local depth,curCtx=0,0          -- ctx: 0 main, 1 NMI, 2 IRQ
local stack={}
local popPending=false
local prevBr,prevPc,prevKey,prevCtx=false,0,0,0
local lastPc,lastBank=0,0
local nestLog=assert(io.open(OUTPUT_DIR..'/'..TAG..'-nested.txt','w'))
local nestCount=0
local nmiEst,irqEst,irqN,irqFrame=0,0,0,0
local phase=0
local PHASEAT={[0xC07B]=0,[0xC182]=1,[0xC185]=2,[0xC188]=3}
local inst={}                   -- per NMI instance: key -> cycles (ctx folded into key)
local win={}                    -- per case window
local heavy={}                  -- NMI instances with wall >= HEAVY
local HEAVY=PK_HEAVY or 25000
local worst={}                  -- top instances {wall=,tab=}
local spanAcc,spanBeg={},{}
local nmiStartCyc=nil
local measuring=false
local frameNmis,frameWall,frameEst,frameSpans,frameIrqN,frameLate=0,0,0,{},0,0
local function charge(key,c)
  if curCtx==1 then nmiEst=nmiEst+c;if PROF then local k=key+phase*0x200000;inst[k]=(inst[k] or 0)+c end
  elseif curCtx==2 then irqEst=irqEst+c;irqFrame=irqFrame+c
    if PROF then local k=key+0x100000;inst[k]=(inst[k] or 0)+c end
  end
end
local function mergeInto(dst,src)for k,v in pairs(src)do dst[k]=(dst[k] or 0)+v end end
local nmiLevel=1
local nestedNmis=0
local function nmiBegin(level)
  nmiLevel=level or 1
  nmiStartCyc=cycles();nmiEst=7;irqN=0;spanAcc={};spanBeg={};phase=0
  if PROF then inst={} end
  frameNmis=frameNmis+1
end
local function nmiEnd()
  if not nmiStartCyc then return end
  local wall=cycles()-nmiStartCyc;nmiStartCyc=nil
  if measuring then
    if wall>frameWall then frameWall=wall;frameEst=nmiEst;frameSpans=spanAcc end
    if PROF then
      mergeInto(win,inst)
      if wall>=HEAVY then mergeInto(heavy,inst) end
      if #worst<3 or wall>worst[#worst].wall then
        worst[#worst+1]={wall=wall,est=nmiEst,tab=inst}
        table.sort(worst,function(a,b)return a.wall>b.wall end)
        if #worst>3 then worst[4]=nil end
      end
    end
  end
end
local function ctxPush(c)
  if c==1 and depth>0 then nestCount=nestCount+1;nestLog:write(string.format('nested NMI #%d case=%s age=%d lastPc=%04X bank=%d depth=%d ctx=%d'..NL,nestCount,C and C.name or '?',age or -1,lastPc,lastBank,depth,curCtx));nestLog:flush() end
  if c==1 and depth>0 then nmiEnd();if measuring then nestedNmis=nestedNmis+1 end end
  depth=depth+1;stack[depth]=curCtx;curCtx=c
  if c==1 then nmiBegin(depth) end
  if c==2 then irqN=irqN+1;frameIrqN=frameIrqN+1 end
  charge(0,7) -- interrupt entry sequence
end
local function ctxPop()
  if depth==0 then curCtx=0;return end
  curCtx=stack[depth];depth=depth-1
end
emu.addMemoryCallback(function(pc,op)
  if prevBr then
    local fall=(prevPc+2)&0xFFFF
    if pc~=fall then
      local c=((pc&0xFF00)~=(fall&0xFF00)) and 2 or 1
      if prevCtx==1 then nmiEst=nmiEst+c;if PROF then local k=prevKey+phase*0x200000;inst[k]=(inst[k] or 0)+c end
      elseif prevCtx==2 then irqEst=irqEst+c;irqFrame=irqFrame+c
        if PROF then local k=prevKey+0x100000;inst[k]=(inst[k] or 0)+c end end
    end
    prevBr=false
  end
  if popPending then popPending=false;ctxPop() end
  if pc==0xC07B then ctxPush(1) elseif pc==0xD4AE then ctxPush(2) end
  local bank
  if pc>=0xC000 then bank=7 elseif pc>=0xA000 then bank=R7>>1 elseif pc>=0x8000 then bank=R6>>1 else bank=8 end
  local key=bank*65536+pc
  if curCtx==1 then
    local ph=PHASEAT[pc];if ph then phase=ph end
    local el=spanEnd[pc]
    if el then for _,e in ipairs(el) do
      if spanBeg[e] then spanAcc[e]=(spanAcc[e] or 0)+nmiEst-spanBeg[e];spanBeg[e]=nil end end end
    local sl=spanStart[pc]
    if sl then for _,sx in ipairs(sl) do spanBeg[sx]=nmiEst end end
  end
  if (op==0x20 or op==0x4C) and measuring then
    local t=r(pc+1)+r(pc+2)*256
    if SWAPT[t] then local k=bank*65536+pc;swapSites[k]=(swapSites[k] or 0)+1;swapFrame=swapFrame+1 end
  end
  local c=CYC[op+1]
  if pc==0xC0BF then c=c+513 end -- OAM DMA
  charge(key,c)
  if BR[op] then prevBr=true;prevPc=pc;prevKey=key;prevCtx=curCtx end
  lastPc=pc;lastBank=bank
  if op==0x40 then
    if curCtx==1 and depth==nmiLevel then nmiEnd() end
    popPending=true
  end
end,emu.callbackType.exec,0x0000,0xFFFF)
if PK_WATCH then
  local wlog=assert(io.open(OUTPUT_DIR..'/'..TAG..'-watch.txt','w'))
  for _,wa in ipairs(PK_WATCH) do
    emu.addMemoryCallback(function(a,v)
      if measuring then wlog:write(string.format('case=%s age=%d write $%04X=%02X lastPc=%d:%04X'..NL,C and C.name or '?',age,a,v,lastBank,lastPc));wlog:flush() end
    end,emu.callbackType.write,wa,wa)
  end
end
if LABELS.VblankOverrun6 then
  emu.addMemoryCallback(function()if measuring and (R6>>1)==6 then frameLate=frameLate+1 end end,emu.callbackType.exec,LABELS.VblankOverrun6)
end

-- ---------------------------------------------------------------------------------------
-- OAM analysis on the DMA shadow ($6500): 8x16 sprites cover Y+1..Y+16; per scanline the
-- first eight in OAM order draw. Classes from native ownership at the same index.
local BARBA={[0x04]=1,[0x08]=1,[0x0C]=1,[0x10]=1,[0x14]=1,[0x18]=1,[0x1C]=1,[0x4C]=1,[0xC4]=1}
local FIRE={[0x34]=1,[0x38]=1,[0x3C]=1,[0x44]=1,[0x48]=1}
local prevVis={barba=0,enemy={},fire=0}
local dropLog=nil
local lastExcess,lastExcessNoB=0,0
local lastExSub={fire=0,head=0,body=0,trail=0}
local lastAlt={0,0,0,0}
local function oamFrame()
  local cls={}
  -- enemy and enemy-shot blocks from native ownership
  for k=0,5 do
    if r(0xB6+k)~=0 then local b=r(0x91+k);for o=0,0x14,4 do cls[(b+o)&0xFF]='E'..k end end
    if r(0x87+k)~=0 then local b=r(0x97+k);cls[b&0xFF]='S';cls[(b+4)&0xFF]='S' end
  end
  local cnt={}
  local bcnt={}
  local subcnt={fire={},head={},body={},trail={}}
  local ents={}
  local dropE,dropL=0,0
  local byCls={B=0,F=0,E=0,S=0,O=0}
  local entDrop={}
  local maxLine,over=0,0
  for i=0,63 do
    local base=0x6500+i*4
    local y=r(base)
    if y<0xEF then
      local off=i*4
      local nat=r(0x200+off)
      local same=(nat==y and r(0x203+off)==r(base+3))
      local c
      if (r(base+2)&0x20)~=0 then c='O'
      elseif same and BARBA[off] then c='B'
      elseif same and FIRE[off] then c='F'
      elseif same and cls[off] then c=cls[off]
      elseif (r(base+2)&3)==0 then c='B' -- moved player-palette entry (trail, swapped body)
      else c='O' end
      local d=0
      local last=y+16;if last>239 then last=239 end
      local isB=(c=='B' or c=='F')
      local sub=nil
      if c=='F' then sub='fire'
      elseif c=='B' then
        if same and (off==0x4C or off==0xC4) then sub='head'
        elseif same and BARBA[off] then sub='body'
        else sub='trail' end
      end
      local sc=sub and subcnt[sub]
      ents[#ents+1]={y=y,last=(y+16>239) and 239 or y+16,trail=(sub=='trail'),enemy=(c:sub(1,1)=='E' or c=='O' or c=='S')}
      for line=y+1,last do
        local n=(cnt[line] or 0)+1;cnt[line]=n
        if isB then bcnt[line]=(bcnt[line] or 0)+1 end
        if sc then sc[line]=(sc[line] or 0)+1 end
        if n>8 then d=d+1 end
      end
      if d>0 and PK_DROPS and C and C.cs.dumpDrops then
        dropLog=dropLog or assert(io.open(OUTPUT_DIR..'/'..TAG..'-drops.csv','w'))
        dropLog:write(string.format('%s,%d,%d,%d,%d,%d,%d,%s,%d,%d,%d,%d'..NL,C.name,age,i,y,r(base+1),r(base+2),r(base+3),c,d,last-y,r(0x29),r(0x4D)))
      end
      if d>0 then
        dropE=dropE+1;dropL=dropL+d
        local k=c:sub(1,1);byCls[k]=(byCls[k] or 0)+d
        entDrop[c]=true
      end
    end
  end
  local excess,excessNoB=0,0
  local exSub={fire=0,head=0,body=0,trail=0}
  for line,n in pairs(cnt)do
    if n>maxLine then maxLine=n end;if n>8 then over=over+1;excess=excess+n-8 end
    local nb=n-(bcnt[line] or 0);if nb>8 then excessNoB=excessNoB+nb-8 end
    for k,t in pairs(subcnt)do local m=n-(t[line] or 0);if m>8 then exSub[k]=exSub[k]+m-8 end end
  end
  lastExcess,lastExcessNoB=excess,excessNoB
  lastExSub=exSub
  -- alternative order: trail entries last (lowest priority)
  local c2={}
  local enemyDrop2,trailDrop2,enemyDrop1,trailDrop1=0,0,0,0
  local function run(e,second)
    local d=0
    for line=e.y+1,e.last do local n=(c2[line] or 0)+1;c2[line]=n;if n>8 then d=d+1 end end
    return d
  end
  for _,e in ipairs(ents) do if not e.trail then local d=run(e);if e.enemy then enemyDrop2=enemyDrop2+d end end end
  for _,e in ipairs(ents) do if e.trail then trailDrop2=trailDrop2+run(e) end end
  c2={}
  for _,e in ipairs(ents) do local d=run(e);if e.enemy then enemyDrop1=enemyDrop1+d elseif e.trail then trailDrop1=trailDrop1+d end end
  lastAlt={enemyDrop1,trailDrop1,enemyDrop2,trailDrop2}
  -- toggles: entity visibility state change vs previous frame
  local tb=(entDrop['B'] and 1 or 0)
  local togB=(tb~=prevVis.barba) and 1 or 0;prevVis.barba=tb
  local tf=(entDrop['F'] and 1 or 0)
  local togF=(tf~=prevVis.fire) and 1 or 0;prevVis.fire=tf
  local togE=0
  for k=0,5 do
    local key='E'..k
    local v=(r(0xB6+k)~=0) and (entDrop[key] and 1 or 0) or -1
    if v>=0 and prevVis.enemy[k] and prevVis.enemy[k]>=0 and v~=prevVis.enemy[k] then togE=togE+1 end
    prevVis.enemy[k]=v
  end
  return maxLine,over,dropE,dropL,byCls,togB,togE,togF
end

-- ---------------------------------------------------------------------------------------
local idx,frame,pending=0,0,false
local done=false
local hudBad=0
local function gateOn()
  if C and C.cs and C.cs.gate=='ow' then return r(0x736)==0x05 end
  return r(0x736)==0x0B and r(0x74C)<2 and r(0x726)==0
end
local function liveShots()
  local n,x=0,0
  for s=0,1 do local v=r(0x8D+s);if v>0 and v<0x80 then n=n+1 end end
  for _,b in ipairs({0x6400,0x6410,0x6420})do local v=r(b);if v>0 and v<0x80 then x=x+1 end end
  return n,x
end
local function counts()
  local e,s=0,0
  for k=0,5 do if r(0xB6+k)~=0 then e=e+1 end;if r(0x87+k)~=0 then s=s+1 end end
  return e,s
end
local function roomId()return r(0x707)*4096+r(0x706)*256+r(0x561)end
local function finishCase()
  if not C then return end
  local n=math.max(1,C.frames)
  sum:write(string.format('%-34s frames=%d lag=%d late=%d wallAvg=%d wallMax=%d over27k=%d estAvg=%d irqAvg=%d '..
    'shotsAvg=%.2f shotsMax=%d enemiesAvg=%.2f eshotsMax=%d roarFrames=%d maxLine=%d framesDrop=%d dropLinesAvg=%.1f '..
    'dropBarbaFrames=%d togBarba=%d togEnemy=%d hudBad=%d nested=%d left=%s'..NL,
    C.name,C.frames,C.lag,C.late,C.sumWall//math.max(1,C.nmiFrames),C.maxWall,C.over27,C.sumEst//math.max(1,C.nmiFrames),
    C.sumIrq//n,C.sumShots/n,C.maxShots,C.sumEnemies/n,C.maxEShots,C.roar,C.maxLine,C.dropFrames,C.sumDropL/n,
    C.barbaDropFrames,C.togB,C.togE,C.hudBad,nestedNmis,tostring(C.left)))
  nestedNmis=0
  sum:write(string.format('   swaps: R6 writes=%d redundant=%d (%.1f%%) per frame=%.1f'..NL,SWAP_ALL,SWAP_SAME,100*SWAP_SAME/math.max(1,SWAP_ALL),SWAP_ALL/math.max(1,C.frames)))
  SWAP_ALL,SWAP_SAME=0,0
  sum:flush()
  if prof then PK_DUMP() end
  win,heavy,worst,swapSites={},{},{},{}
end
function PK_DUMP()
  if prof then
    local function dump(kind,tab)
      for k,v in pairs(tab)do
        local ctx=((k//0x100000)%2==1) and 2 or 1
        local ph=k//0x200000
        local kk=k%0x100000
        prof:write(string.format('%s,%s,%d,%d,%d,%d'..NL,C.name,kind,ctx+ph*10,kk//65536,kk%65536,v))
      end
    end
    dump('win',win);dump('heavy',heavy)
    for k,v in pairs(swapSites)do prof:write(string.format('%s,swapsite,0,%d,%d,%d'..NL,C.name,k//65536,k%65536,v))end
    for i,wv in ipairs(worst)do if i==1 then dump('worst'..i..':'..wv.wall..':'..wv.est,wv.tab) end end
    prof:flush()
  end
end
function PK_FLUSH(final)
  if not C then return end
  local f=assert(io.open(OUTPUT_DIR..'/'..TAG..'-overlay.txt','w'))
  local n=math.max(1,C.frames)
  f:write(string.format('%s frames=%d lag=%d wallAvg=%d wallMax=%d over27k=%d shotsAvg=%.2f shotsMax=%d enemiesAvg=%.2f eshotsMax=%d roarFrames=%d maxLine=%d framesDrop=%d dropLinesAvg=%.1f dropBarbaFrames=%d togEnemy=%d hudBad=%d nested=%d final=%s'..NL,
    C.name,C.frames,C.lag,C.sumWall//math.max(1,C.nmiFrames),C.maxWall,C.over27,C.sumShots/n,C.maxShots,C.sumEnemies/n,C.maxEShots,C.roar,C.maxLine,C.dropFrames,C.sumDropL/n,C.barbaDropFrames,C.togE,C.hudBad,nestedNmis,tostring(final)))
  f:close();csv:flush()
  if final and prof and PK_DUMP then PK_DUMP() end
end
local function loadNext()
  finishCase()
  idx=idx+1
  local cs=PK_CASES[idx]
  if not cs then
    sum:write('RESULT PASS'..NL);sum:close();csv:close();if prof then prof:close()end
    done=true;stopScenario(0);return
  end
  local f=assert(io.open(PK_PACK..'/'..cs.state..'.mss','rb'))
  assert(emu.loadSavestate(f:read('*a')),cs.state..' loads');f:close()
  syncBanks()
  depth,curCtx,popPending,prevBr=0,0,false,false;nmiStartCyc=nil
  C={name=cs.state..'#'..(cs.phase or 0)..(cs.label and ('/'..cs.label) or ''),cs=cs,frames=0,lag=0,late=0,sumWall=0,
    nmiFrames=0,maxWall=0,over27=0,sumEst=0,sumIrq=0,sumShots=0,maxShots=0,sumEnemies=0,maxEShots=0,roar=0,maxLine=0,
    dropFrames=0,sumDropL=0,barbaDropFrames=0,togB=0,togE=0,hudBad=0,left=false,room=nil}
  age=0;prevVis={barba=0,enemy={},fire=0}
end
emu.addMemoryCallback(function()
  if PK_OVERLAY then return end
  if pending then pending=false;loadNext() end
end,emu.callbackType.exec,0xC07B)
emu.addEventCallback(function()
  if not C or age<=20 or not gateOn() then return end
  local s=emu.getState()
  if (s['ppu.tmpVideoRamAddr']&0x041F)~=0 or s['ppu.xScroll']~=0 then hudBad=hudBad+1 end
end,emu.eventType.startFrame)

-- Autopilot ------------------------------------------------------------------------------
local held={}
local function pilot(cs,t)
  local b={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
  local p=cs.phase or 0
  local pat=cs.pattern or 'fight'
  local cad=cs.cadence or 10
  local tt=t+p*7
  if pat=='idle' then return b end
  if pat=='ow' then
    local dirs={'right','down','left','up'}
    b[dirs[((tt//48)%4)+1]]=true
    b.b=(tt%20)<2
    return b
  end
  b.b=(tt%cad)<2
  if pat=='stand' then return b end
  local px=r(0x3B)*256+r(0x4D)
  local best=nil
  for k=0,5 do
    if r(0xB6+k)==1 then
      local ex=r(0x3C+k)*256+r(0x4E+k)
      local d=ex-px-8
      if not best or math.abs(d)<math.abs(best) then best=d end
    end
  end
  local face=held.face or 'right'
  if best then
    local ad=math.abs(best)
    local toward=best>0 and 'right' or 'left'
    local away=best>0 and 'left' or 'right'
    if ad>56 then b[toward]=true;face=toward
    elseif ad<28 then
      if (tt%12)<8 then b[away]=true else b[toward]=true;face=toward end
    else
      if (tt%30)<3 then b[toward]=true;face=toward end
    end
  else
    if cs.seek=='right' then b.right=true;face='right'
    elseif cs.seek=='left' then b.left=true;face='left'
    else
      -- no enemy: pace around the start X so the room stays loaded
      local dx=px-(C.startX or px)
      if dx>40 then b.left=true elseif dx<-40 then b.right=true
      elseif (tt%160)<80 then b.right=true else b.left=true end
    end
  end
  held.face=face
  local j=(tt+p*11)%(cs.jump or 46)
  b.a=j<12
  if pat=='fight' then
    if (tt%150)>=110 and (tt%150)<132 then b.down=true;b.a=false end   -- crouch fire
    if j<12 and (tt%92)<46 then b.up=true end                        -- up fire while airborne
  elseif pat=='meteor' then
    if j>=6 and j<30 then b.down=true end
  end
  return b
end
emu.addEventCallback(function()
  if PK_OVERLAY then return end
  local b={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
  if C and age>20 then b=pilot(C.cs,age) end
  emu.setInput(b,0)
end,emu.eventType.inputPolled)

emu.addEventCallback(function()
  if done then return end
  frame=frame+1
  if PK_OVERLAY then
    if not C then
      C={name=PK_TAG,cs={frames=1e9},frames=0,lag=0,late=0,sumWall=0,nmiFrames=0,maxWall=0,over27=0,sumEst=0,sumIrq=0,
        sumShots=0,maxShots=0,sumEnemies=0,maxEShots=0,roar=0,maxLine=0,dropFrames=0,sumDropL=0,barbaDropFrames=0,
        togB=0,togE=0,hudBad=0,left=false,room=nil}
    end
    age=frame
    if frame<(PK_SKIP or 1100) then
      frameNmis,frameWall,frameEst,frameSpans,irqFrame,frameIrqN,frameLate,hudBad,swapFrame=0,0,0,{},0,0,0,0,0
      measuring=false;return
    end
    C.room=roomId()
  else
  if idx==0 then if frame==30 then pending=true end return end
  if not C then return end
  age=age+1
  end
  local cs=C.cs
  if age==20 then C.room=roomId();C.startX=r(0x3B)*256+r(0x4D) end
  measuring=(age>20)
  PK_MEASURING=measuring
  if age>20 then
    if not PK_OVERLAY then w(0x774,255);w(0x773,255) end
    if cs.meteor then w(0x76F,r(0x76F)|0x10) end
    if cs.inferno and (age%cs.inferno)==25 then w(0x6470,0x31) end
    if cs.flags then for a,v in pairs(cs.flags) do w(a,v) end end
    if roomId()~=C.room and not PK_OVERLAY then C.left=true end
    local g=gateOn() and not C.left
    local lag=(frameNmis==0) and 1 or 0
    local sn,sx=liveShots()
    local e,es=counts()
    local roar=((r(0x05EE)&0x80)~=0) and 1 or 0
    local maxLine,over,dropE,dropL,by,togB,togE,togF=oamFrame()
    if g then
      C.frames=C.frames+1;C.lag=C.lag+lag;C.late=C.late+frameLate
      if frameNmis>0 then C.nmiFrames=C.nmiFrames+1;C.sumWall=C.sumWall+frameWall;C.sumEst=C.sumEst+frameEst end
      C.maxWall=math.max(C.maxWall,frameWall);if frameWall>27000 then C.over27=C.over27+1 end
      C.sumIrq=C.sumIrq+irqFrame;C.sumShots=C.sumShots+sn+sx;C.maxShots=math.max(C.maxShots,sn+sx)
      C.sumEnemies=C.sumEnemies+e;C.maxEShots=math.max(C.maxEShots,es);C.roar=C.roar+roar
      C.maxLine=math.max(C.maxLine,maxLine);if dropE>0 then C.dropFrames=C.dropFrames+1 end
      C.sumDropL=C.sumDropL+dropL;if (by.B or 0)>0 then C.barbaDropFrames=C.barbaDropFrames+1 end
      C.togB=C.togB+togB;C.togE=C.togE+togE;C.hudBad=C.hudBad+hudBad
    end
    local sp=frameSpans or {}
    csv:write(string.format('%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d'..NL,
      C.name,age,g and 1 or 0,lag,frameNmis,frameWall,frameEst,irqFrame,frameIrqN,
      sp[1] or 0,sp[2] or 0,sp[3] or 0,sp[4] or 0,sp[5] or 0,sp[6] or 0,sp[7] or 0,sp[8] or 0,sp[9] or 0,
      sp[10] or 0,sp[11] or 0,sp[12] or 0,swapFrame,
      sn,sx,e,es,roar,roomId(),maxLine,over,dropE,dropL,by.B or 0,by.F or 0,by.E or 0,by.S or 0,by.O or 0,
      togB,togE,togF,hudBad,frameLate,r(0x3B)*256+r(0x4D),r(0x29),lastExcess,lastExcessNoB,lastExSub.fire,lastExSub.head,lastExSub.body,lastExSub.trail,lastAlt[1],lastAlt[2],lastAlt[3],lastAlt[4]))
  end
  frameNmis,frameWall,frameEst,frameSpans,irqFrame,frameIrqN,frameLate,hudBad,swapFrame=0,0,0,{},0,0,0,0,0
  if not PK_OVERLAY and (age>=20+(cs.frames or 300) or (C.left and age>20+30)) then pending=true end
  if PK_OVERLAY and frame%120==0 then PK_FLUSH() end
end,emu.eventType.endFrame)
