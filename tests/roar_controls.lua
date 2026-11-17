-- Real controller pause/resume during a roar: pausing mutes DMC and skips the
-- audio tick, so early polling must resume native reads when hardware stops.
dofile(TEST_DIR..'/newgame.lua')
local frame,errors=0,0
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local f=assert(io.open(OUTPUT_DIR..'/roar-controls.txt','w'))
local function check(ok,msg)f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');if not ok then errors=errors+1 end end
emu.addEventCallback(function()
 local b=newGameInput(frame)
 if frame>=1000 then
  b={start=(frame>=1150 and frame<1153) or (frame>=1220 and frame<1223),
   select=false,a=false,b=false,up=false,down=false,left=false,right=false}
 end
 emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
 frame=frame+1
 if frame==1100 then emu.write(0x5EE,0x40,mem)end
 if frame==1110 then check(r(0x736)==11 and (r(0x4015)&0x10)~=0,'real gameplay starts full roar')end
 if frame==1190 then check(r(0x524)~=0,'Start opens pause pane during roar')end
 if frame==1300 then
  check(r(0x524)==0 and r(0x736)==11,'Start resumes; sampled input cache cannot trap pause')
  check(r(0x5EE)==0 and (r(0x4015)&0x10)==0,'interrupted roar retires after pause')
  f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close();stopScenario(errors==0 and 0 or 1)
 end
end,emu.eventType.endFrame)
