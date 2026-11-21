-- Controlled CPU tests of the real assembled coordinator and native hooks.
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local f=assert(io.open(OUTPUT_DIR..'/roar-gameplay.txt','w'))
local cases,index,failures,frame={},0,0,0
local rate,length,activeCase=nil,nil,false
local pulseValue=nil
local ready=false
local function check(ok,msg)
 f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');if not ok then failures=failures+1 end
end
local function add(name,bank,entry,setup,verify)
 cases[#cases+1]={name=name,bank=bank,entry=entry,setup=setup,verify=verify}
end
local function playing()return r(0x4015)&0x10~=0 end
-- RoarGemEnd keeps its floor-pulse timer in $04A0,x (0 = fanfare, 33 = pulse done).
local function gemTimer(v)for a=0x4A0,0x4A5 do w(a,v)end end
local function gemBody()
 w(0x5EE,0x88);w(0x5FA,72);w(0x5F6,1);w(0x5F4,0x80);w(0x5F5,0x54);w(0x5FB,0)
 for _,a in ipairs({0x204,0x24C,0x2C4})do w(a,0x80)end
 for a=0x208,0x210,4 do w(a,0x90)end
 for a=0x214,0x21C,4 do w(a,0xA0)end
 w(0x220,0xF8);w(0x224,0xF8)
end
for _,facing in ipairs({0,0x40})do
 local attr=facing
 add('gem torso facing '..attr,6,LABELS.RoarGemTorso,function()
  gemBody();w(0x5FB,attr)
 end,function()
  check(r(0x204)==0x78 and r(0x208)==0x88 and r(0x214)==0x98,'gem lifts existing rows by 8 pixels to complete the partial torso segment')
  check(r(0x220)==0xA0 and r(0x224)==0xA0,'gem extra torso keeps the original feet height')
  check(r(0x221)==(attr==0 and 6 or 8) and r(0x225)==(attr==0 and 8 or 6), 'gem torso tile columns match facing')
  check(r(0x223)==(attr==0 and 0x5C or 0x54) and r(0x227)==(attr==0 and 0x64 or 0x5C)
   and r(0x222)==attr and r(0x226)==attr,'gem torso alignment and flip match facing')
 end)
end
for _,guard in ipairs({'frozen','ceiling','hud','edge','other pose'})do
 local reason=guard
 add('gem torso skips '..reason,6,LABELS.RoarGemTorso,function()
  gemBody()
  if reason=='frozen' then w(0x204,0x70)
  elseif reason=='ceiling' then w(0x5F6,3)
  elseif reason=='hud' then w(0x5F4,0x20);w(0x204,0x20)
  elseif reason=='edge' then w(0x5F5,0xF8)
  else w(0x5FA,27)end
 end,function()
  check(r(0x220)==0xF8 and r(0x224)==0xF8 and r(0x208)==0x90,'gem torso safely skips '..reason)
 end)
end
for random=0,7 do
 local seed=random
 add('attack stays quiet for RNG bucket '..seed,6,LABELS.RoarAudio,function()
  w(0x5EE,1);w(0x51B,seed);w(0x12,0)
 end,function()
  check(not playing(),'attacks never start a roar for RNG bucket '..seed)
 end)
end
add('breath keeps native fire sound',0,LABELS.BarbaBreathSfx,function()
 w(0x5EE,0);w(0x5F0,0);w(0xED,0)
end,function()
 check(r(0x5EE)==0 and r(0xED)==0x40,'breath plays fireball SFX without requesting a roar')
end)
add('cooldown blocks fire',6,LABELS.RoarAudio,function()
 w(0x5EE,1);w(0x5EF,200);w(0x51B,0);w(0x12,0)
end,function()check(not playing() and r(0x5EF)==199,'cooldown suppresses another fire roar')end)
add('player hurt hook',0,0xE314,function()w(0x00,0)end,function()
 check(r(0x5EE)==4 and r(0xE9)==0 and r(0)==1,'Barba injury queues grunt and retains native recoil argument')
end)
add('hurt overrides active roar/cooldown',6,LABELS.RoarAudio,function()
 w(0x5EE,0x84);w(0x5EF,200)
end,function()
 check(playing() and rate==9 and length==46,'hurt uses the extended 0.527-second sample prefix')
end)
add('Lava Link keeps native hurt',6,LABELS.RoarAudio,function()
 w(0xE9,1);w(0x5EE,0x80)
end,function()
 check(playing() and rate==15 and length==12 and r(0x5EE)==0,'Lava Link original hurt sample/rate wins over active roar')
end)
for _,point in ipairs({{255,9},{239,8},{235,7},{231,6},{227,5},{210,5}})do
 local timer,expected=point[1],point[2]
 add('hurt pitch tail '..timer,6,LABELS.RoarAudio,function()
  w(0x5EE,0xA0);w(0x5EF,timer)
 end,function()check(rate==expected,'injury tail rate '..expected..' at timer '..timer)end)
end
add('full roar keeps pitch',6,LABELS.RoarAudio,function()
 w(0x5EE,0x80);w(0x5EF,210)
end,function()check(rate==nil,'full roar never applies injury pitch descent')end)
add('native hurt rate unchanged',6,LABELS.RoarNativeRate,function()
 w(0x7FA,1)
end,function()check(rate==15,'native Link hurt retains rate 15 with descending laughs')end)
add('gem fanfare still playing',4,0x9B47,function()
 gemTimer(0);w(0x7FB,0x40);w(0x70C,0);w(0x70D,0);w(0xAF,2)
end,function()
 check(r(0x5EE)==0 and r(0xAF)==2,'gem stays quiet until victory fanfare ends')
end)
add('gem fanfare finished',4,0x9B47,function()
 gemTimer(0);w(0x7FB,0);w(0x70C,0);w(0x70D,0);w(0xAF,2)
end,function()
 check(r(0x5EE)==0x48 and r(0xAF)==2,'fanfare end queues the victory roar and keeps the statue waiting')
 check(r(0x70C)==0 and r(0x70D)==0,'fanfare end defers magic and life refill')
end)
add('gem voice before refill and XP',6,LABELS.RoarAudio,function()
 w(0x5EE,0x48);w(0x70C,255);w(0x70D,255);w(0x756,20);w(0x74C,1)
end,function()
 check(playing() and length==136 and r(0x5EE)==0x88,'gem roar starts immediately without waiting for refill, XP or level-up')
end)
add('gem voice drains its final bits',6,LABELS.RoarAudio,function()
 w(0x5EE,0x88)
end,function()
 check(r(0x5EE)==0x98,'gem holds its pose for another audio tick when the DMC reports empty')
end)
add('gem voice retires pose after drain',6,LABELS.RoarAudio,function()
 w(0x5EE,0x98)
end,function()
 check(r(0x5EE)==0x10,'finished gem voice clears the pose and signals the statue')
end)
add('finished gem waits for the statue',6,LABELS.RoarAudio,function()
 w(0x5EE,0x10)
end,function()
 check(not playing() and r(0x5EE)==0x10,'audio leaves the completed gem latched until the statue runs')
end)
for _,phase in ipairs({0x48,0x88,0x98})do
 add('gem waits in phase '..phase,4,0x9B47,function()
  w(0x5EE,phase);w(0x7FB,0);w(0x70C,0);w(0x70D,0);w(0xDE,1);w(0xAF,2)
 end,function()
  check(r(0xDE)==1 and r(0xAF)==2 and r(0x5EE)==phase and r(0x70C)==0 and r(0x70D)==0,
   'gem keeps control locked and refill deferred in phase '..phase)
 end)
end
add('gem refills after the roar',4,0x9B47,function()
 gemTimer(33);w(0x5EE,0x10);w(0x70C,0);w(0x70D,0);w(0xAF,2);w(0xDE,1)
end,function()
 check(r(0x5EE)==0 and r(0xAF)==3 and r(0xDE)==1,'statue consumes the completed roar and advances to the native XP stage')
 check(r(0x70C)==255 and r(0x70D)==255,'completed roar starts native magic and life refill')
end)
add('gem native final step',4,0x9B56,function()
 w(0x70C,0);w(0x70D,0);w(0x770,1);w(0x771,0);w(0x775,0);w(0x776,0)
 w(0xBC,0);w(0xD6,0);w(0xD7,0x64);w(0x10,0);w(0x707,4);w(0x706,0);w(0x561,0);w(0xDE,1)
end,function()
 check(r(0x5EE)==0 and r(0xA1)==0x15 and r(0xDE)==0,'native gem completion removes crystal and releases control without queuing a second roar')
 check(r(0x755)==1 and r(0x756)==0 and r(0xEB)==2,'gem completion keeps native experience award and music restart')
end)
add('victory overrides cooldown',6,LABELS.RoarAudio,function()
 w(0x5EE,0x40);w(0x5EF,200)
end,function()check(playing() and length==136,'gem victory always plays the full roar')end)
add('victory waits for XP',6,LABELS.RoarAudio,function()
 w(0x5EE,0x40);w(0x756,20)
end,function()check(not playing() and r(0x5EE)==0x40,'victory roar waits for experience tally to finish')end)
add('victory waits for level pane',6,LABELS.RoarAudio,function()
 w(0x5EE,0x40);w(0x74C,1)
end,function()check(not playing() and r(0x5EE)==0x40,'victory roar survives the level-up pane')end)
add('transition cleanup',6,LABELS.RoarAudio,function()
 w(0x736,0);w(0x5EE,0x80);w(0x5EF,200)
end,function()check(not playing() and r(0x5EE)==0 and r(0x5EF)==0,'scene change clears gameplay roar state')end)
for _,channel in ipairs({1,2})do
 for _,on in ipairs({true,false})do
  local ch,roaring=channel,on
  add('gameplay pulse '..ch..' duck='..tostring(roaring),6,ch==1 and LABELS.RoarPulse1 or LABELS.RoarPulse2,
   function()w(0x5EE,roaring and 0x80 or 0)end,function()
    check(pulseValue==(roaring and 0x97 or 0x9F) and emu.getState()['cpu.x']==0x9F,
     'gameplay melody '..ch..' '..(roaring and 'halves volume' or 'restores original volume')..' and retains X')
   end)
  cases[#cases].x=0x9F
 end
end

local function nextCase()
 index=index+1
 local c=cases[index]
 if not c then
  activeCase=false;f:write('RESULT '..(failures==0 and 'PASS' or 'FAIL')..'\n');f:close()
  local stop=emu.exit or emu.stop;stop(failures==0 and 0 or 1);return
 end
 activeCase=true;rate=nil;length=nil;pulseValue=nil
 w(0x2000,0);w(0x4015,0x0F);w(0x736,11);w(0x5EE,0);w(0x5EF,0);w(0xE9,0);w(0x7FA,0)
 w(0x755,0);w(0x756,0);w(0x74C,0);w(0x524,0);w(0x13,0)
 c.setup()
 local program={0xA9,c.bank,0x20,0xCC,0xFF,0x20,c.entry%256,math.floor(c.entry/256),0x4C,0x08,0x06}
 for i,v in ipairs(program)do w(0x5FF+i,v)end
 emu.setState({['cpu.pc']=0x0600,['cpu.sp']=0xFD,['cpu.x']=c.x or 0,['cpu.ps']=0x24})
end
emu.addMemoryCallback(function(a,v)if a==0x4010 then rate=v end;if a==0x4013 then length=v end end,
 emu.callbackType.write,0x4010,0x4013)
emu.addMemoryCallback(function(a,v)if a==0x4000 or a==0x4004 then pulseValue=v end end,
 emu.callbackType.write,0x4000,0x4004)
emu.addMemoryCallback(function()
 if activeCase and cases[index].name=='player hurt hook' then emu.setState({['cpu.pc']=0x0608})end
end,emu.callbackType.exec,0xE31A)
emu.addMemoryCallback(function()
 if activeCase then cases[index].verify();nextCase()end
end,emu.callbackType.exec,0x0608)
emu.addEventCallback(function()
 frame=frame+1;if frame==120 then ready=true end
end,emu.eventType.endFrame)
emu.addMemoryCallback(function()
 if ready then ready=false;nextCase()end
end,emu.callbackType.exec,0xC07B)
