-- Controlled CPU acceptance: real scheduler, native motion/collision and backed slots.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/upstab.txt','w'))
local errors,checks,frame,current=0,0,0,0
local running,ready=false,false
local steps={}
local shots,upShots,extraShots,dxSeen,dySeen=0,0,0,false,false
local extra=false
local tracked={}
local function check(ok,msg)
 checks=checks+1;report:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');report:flush()
 if not ok then errors=errors+1 end
end
local function add(entry,setup,verify)steps[#steps+1]={entry=entry,setup=setup,verify=verify}end
local function base(dir,tech,air)
 shots=0;upShots=0;extraShots=0;dxSeen=false;dySeen=false;tracked={}
 for a=0x6000,0x633F do w(a,0x42)end
 for a=0x6400,0x642F do w(a,0)end
 for a=0xB6,0xBB do w(a,0)end
 for _,a in ipairs({0x74C,0x524,0x726,0x13,0xDE,0x8D,0x8E,0x5F1,0x5F7,0x5F8,0x5FC,0x5FD,0x5FE,0x5FF,0x72A,0x72C,0xC8,0xC9})do w(a,0)end
 w(0x769,4);w(0x707,4);w(0x736,11);w(0xB5,1);w(0x777,4)
 w(0x76F,0);w(0x400,2);w(0x495,1);w(0x50A,5)
 w(0x17,1);w(0x80,6);w(0xF7,0x48);w(0x796,tech);w(0x479,air)
 w(0x9F,dir);w(0x5F,dir);w(0xCC,100);w(0x4D,100);w(0x3B,0);w(0x29,160)
 w(0x9D,0x38);w(0x9E,0x40);w(0x645F,0xFF)
end
for _,c in ipairs({{dir=1,tech=4,air=2},{dir=2,tech=4,air=2},
 {dir=1,tech=0,air=2},{dir=1,tech=4,air=0},{dir=1,tech=4,air=0,elevator=true}})do
 for tick=1,65 do
  add(LABELS.BarbaProjectiles,function()
   if tick==1 then base(c.dir,c.tech,c.air);if c.elevator then w(0xB6,1);w(0xA1,0x13)end end
   if tick==2 then w(0xF7,0x40)end -- releasing Up cannot split the volley
   if tick==10 then w(0x400,0)end
  end,function()
   if tick==65 then
    local expected=c.tech==4 and c.air~=0
    check(shots==5,'five emissions dir='..c.dir..' tech='..c.tech..' air='..c.air..' count='..shots)
    check(upShots==(expected and 5 or 0),'airborne + technique gate and volley aim latch count='..upShots)
    check(dxSeen and dySeen,'real native X drift and strict Y trajectory in facing direction')
    if expected then check(extraShots>0,'upward backed-slot allocation count='..extraShots)end
   end
  end)
 end
end
-- Exercise all three backed records explicitly, including alias lifetime expiry.
for record=0,2 do
 add(LABELS.BarbaFireSpell,function()
  base(1,4,2);w(0x8D,1);w(0x8E,1);w(0x5FF,1)
  for n=0,record-1 do w(0x6400+n*16,1)end
 end,function()
  local b=0x6400+record*16
  check(r(b)==1 and r(b+9)==0x5C and r(b+4)==0x10,'upward allocation in backed record '..record)
 end)
 local before
 add(LABELS.BarbaExtraUpdate,function()before=r(0x6401+record*16)end,function()
  check(r(0x6401+record*16)==before-3,'upward motion in backed record '..record)
 end)
 add(LABELS.BarbaExtraUpdate,function()w(0x6401+record*16,0x11)end,function()
  check(r(0x6400+record*16)==0 and r(0x6409+record*16)==0,'top clip clears backed record '..record)
 end)
end
for _,y in ipairs({0,1,0x10,0x11,0x12,0x13})do
 add(LABELS.BarbaStepSlotY,function()w(0x8D,1);w(0x5FC,0x5C);w(0x36,y)end,function()
  check(y>=0x13 and r(0x36)==y-3 and r(0x8D)==1 or y<0x13 and r(0x8D)==0 and r(0x5FC)==0,
   'top clip/borrow without wrap Y='..y)
 end)
end
-- Folded head spawns at its current top even under solid ceiling tiles.
add(LABELS.BarbaFireSpell,function()
 base(1,4,2);for a=0x6000,0x633F do w(a,0x4C)end
end,function()
 check(shots==1 and r(0x5F6)==3 and r(0x37)==r(0x5F3)-12,'folded ceiling head still emits at head top')
end)
-- Real native glove handler: projectile at ceiling above native player head.
for _,glove in ipairs({0,1})do
 add(LABELS.BarbaBlocks,function()
  base(1,4,2);w(0x786,glove);w(0x80,8);w(0x57D,0xFC)
  w(0x47E,0xA6);w(0x70,0x13);w(0x29,0xB0)
  w(0x8D,1);w(0x36,0x90);w(0x5A,0x48);w(0x48,0);w(0x5FC,0x5C)
  w(0x6074,0x4C);for a=0x41A,0x43C do w(a,0)end
 end,function()
  check(r(0x6074)==(glove==1 and 0x42 or 0x4C),'ceiling brick glove='..glove)
  check(r(0x80)==8 and r(0x57D)==0xFC and r(0x70)==0x13,'brick preserves player pose and velocities')
  check(r(0x480)==0xA8 and r(0x47E)==111,'block wrapper restores rising centered head-butt')
 end)
end
-- Native sword detection with enemy hurtbox tables, no collision interception.
for _,velocity in ipairs({0xFC,3})do
 add(LABELS.BarbaSetThrusts,function()
  base(1,4,2);w(0x80,8);w(0x57D,velocity)
 end,function()
  check(r(0x480)==(velocity==0xFC and 152 or 0xF8),'rising-only melee velocity='..velocity)
 end)
 add(0xE677,function()
  w(0x10,0);w(0xA1,3);w(0xB6,1);w(0xA8,0);w(0xC2,32);w(0x40E,0)
  w(0x6E44,0);w(0x6DD8,0);w(0x6DF7,0);w(0xC8,0);w(0xC9,0)
  w(0x2A,144);w(0x4E,111);w(0x3C,0);w(0xCD,111)
 end,function()
  check(velocity==0xFC and r(0xC2)<32 or velocity==3 and r(0xC2)==32,
   'enemy above takes damage only on ascent hp='..r(0xC2))
 end)
end
local function nextStep()
 current=current+1;local t=steps[current]
 if not t then
  running=false;report:write('CHECKS '..checks..' FAILURES '..errors..'\nRESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
  report:close();stopScenario(errors==0 and 0 or 1);return
 end
 if t.setup then t.setup()end
 local e=t.entry
 local p={0x20,0xC5,0xFF,0xA2,0,0x20,e%256,e//256,0x4C,0x08,0x06}
 for i,v in ipairs(p)do w(0x5FF+i,v)end
 emu.setState({['cpu.pc']=0x600,['cpu.sp']=0xFD,['cpu.ps']=0x24})
end
emu.addMemoryCallback(function()
 if not running then return end
 shots=shots+1
 local s=emu.getState()['cpu.x'];local up=(r(0x5FC+s)&0x40)~=0
 if up then upShots=upShots+1 end
 if r(0x8D)==1 and r(0x8E)==1 and s==0 then extraShots=extraShots+1 end
 check(not up or r(0x36+s)==r(0x5F3)-12,'up shot head-top origin')
end,emu.callbackType.exec,LABELS.BarbaVolleyPlaced)
emu.addMemoryCallback(function()extra=false end,emu.callbackType.exec,LABELS.BarbaProjectiles)
emu.addMemoryCallback(function()extra=true end,emu.callbackType.exec,LABELS.BarbaExtraUpdate)
emu.addMemoryCallback(function()
 if not running then return end
 local s=emu.getState()['cpu.x'];if s>1 or r(0x8D+s)==0 then return end
 local key=extra and 2+r(0x6450)//16 or s
 local x=r(0x5A+s)+256*r(0x48+s);local y=r(0x36+s)
 local life=r(0x5FC+s)&0x3F;local old=tracked[key]
 if old and life<old.life then
  local up=(r(0x5FC+s)&0x40)~=0
  check(up and y<old.y or not up and y>old.y,'strict Y motion slot='..key)
  dySeen=true
  if r(0x6D+s)==1 and x>old.x or r(0x6D+s)==2 and x<old.x then dxSeen=true end
 end
 tracked[key]={x=x,y=y,life=life}
end,emu.callbackType.exec,0x9888)
emu.addMemoryCallback(function()
 if running then local t=steps[current];if t.verify then t.verify()end;nextStep()end
end,emu.callbackType.exec,0x608)
emu.addEventCallback(function()frame=frame+1;if frame==120 then ready=true end end,emu.eventType.endFrame)
emu.addMemoryCallback(function()
 if ready and not running then ready=false;running=true;w(0x2000,0);nextStep()end
end,emu.callbackType.exec,0xC07B)
