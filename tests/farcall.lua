-- All PRG banks, mismatched $0769, flags/registers/scratch, nesting,
-- target low-byte borrow, inline operand page crossing, and stack balance.
local mem=emu.memType.nesMemory
local report=assert(io.open(OUTPUT_DIR..'/farcall.txt','w'))
local failures,frame,index=0,0,0
local ready,active=false,false
local tests={}
local L=LABELS
local function w(a,v)emu.write(a,v,mem)end
local function r(a)return emu.read(a,mem)end
local function mappedBank()
 local address=emu.convertAddress(0x8506,mem)
 return address and address.address//0x4000
end
local function check(ok,msg)
 report:write((ok and 'PASS ' or 'FAIL ')..msg..'\n')
 if not ok then failures=failures+1 end
end
for bank=0,7 do
 for _,ps in ipairs({0x24,0xE5,0x6C})do
  tests[#tests+1]={bank=bank,ps=ps}
 end
end
tests[#tests+1]={bank=3,ps=0xE5,nested=true}
tests[#tests+1]={bank=0,ps=0x24,borrow=true}
tests[#tests+1]={bank=3,ps=0xE5,page=true}
local current,startCycles,entryCycles
local target=L.LavaSurfaceBody
local function bytes(a,data)for i,v in ipairs(data)do w(a+i-1,v)end end
local function nextTest()
 index=index+1;current=tests[index]
 if not current then
  active=false
  report:write('RESULT '..(failures==0 and 'PASS' or 'FAIL')..'\n');report:close()
  stopScenario(failures==0 and 0 or 1);return
 end
 w(0x769,(current.bank+2)%8);w(0x00,0x39);w(0x01,0xD7)
 current.site=current.page and 0x6FD or 0x620
 current.dest=current.borrow and 0x700 or target
 -- RAM instructions and operands remain visible through every bank mapping.
 bytes(0x600,{0xA9,current.bank,0x20,0xCC,0xFF,0xA9,current.ps,0x48,
              0xA9,0xA6,0xA2,0x53,0xA0,0xC7,0x28,
              0x4C,current.site%256,current.site//256})
 bytes(current.site,{0x20,L.FarCall0%256,L.FarCall0//256,current.dest%256,current.dest//256,
                     0x4C,(current.site+5)%256,(current.site+5)//256})
 -- Target body: 26 cycles including RTS. Deliberately different outputs.
 bytes(0x680,{0xA9,0x5A,0x85,0x00,0xA9,0x83,0x48,
              0xA9,0x42,0xA2,0x96,0xA0,0x17,0x28,0x60})
 active=true
 emu.setState({['cpu.pc']=0x600,['cpu.sp']=0xFD,['cpu.ps']=0x24})
end
local function started()
 if active then startCycles=emu.getState()['cpu.cycleCount']end
end
emu.addMemoryCallback(started,emu.callbackType.exec,0x620)
emu.addMemoryCallback(started,emu.callbackType.exec,0x6FD)
local function targetEntry()
 if not active then return end
 local s=emu.getState()
 check(mappedBank()==0,'target mapped bank0 from '..current.bank)
 check(s['cpu.a']==0xA6 and s['cpu.x']==0x53 and s['cpu.y']==0xC7,'input registers')
 check((s['cpu.ps'] & 0xCF)==(current.ps & 0xCF),'input flags')
 check(r(0)==0x39 and r(1)==0xD7,'input scratch preserved')
 entryCycles=s['cpu.cycleCount']
 -- Redirect the real bank0 target into controlled RAM code, or a nested call.
 if current.nested then
  bytes(0x6A0,{0x20,L.FarCall0%256,L.FarCall0//256,target%256,target//256,0x60})
  current.nested=false;current.inner=true
  emu.setState({['cpu.pc']=0x6A0})
 else emu.setState({['cpu.pc']=0x680})end
end
emu.addMemoryCallback(targetEntry,emu.callbackType.exec,target)
emu.addMemoryCallback(targetEntry,emu.callbackType.exec,0x700)
local function returned()
 if not active then return end
 local s=emu.getState()
 check(mappedBank()==current.bank,'restored actual bank '..current.bank)
 check(s['cpu.a']==0x42 and s['cpu.x']==0x96 and s['cpu.y']==0x17,'output registers')
 check((s['cpu.ps'] & 0xCF)==0x83,'output flags')
 check(r(0)==0x5A and r(1)==0xD7,'target scratch output retained')
 check(s['cpu.sp']==0xFD,'balanced stack')
 report:write(string.format('CYCLES bank=%d total=%d entry=%d nested=%s borrow=%s page=%s\n',current.bank,
  s['cpu.cycleCount']-startCycles,entryCycles-startCycles,tostring(current.inner or false),
  tostring(current.borrow or false),tostring(current.page or false)))
 nextTest()
end
emu.addMemoryCallback(returned,emu.callbackType.exec,0x625)
emu.addMemoryCallback(returned,emu.callbackType.exec,0x702)
dofile(TEST_DIR..'/newgame.lua')
emu.addEventCallback(function()frame=frame+1;if frame==120 then ready=true end end,emu.eventType.endFrame)
emu.addMemoryCallback(function()
 if ready and not active then ready=false;w(0x2000,0);nextTest()end
end,emu.callbackType.exec,0xC07B)
