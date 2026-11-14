-- Native open-door entry and return, with a generated villager nearby.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local frame,errors=0,0
local entered,returned,stolen=false,false,false
local f=assert(io.open(OUTPUT_DIR..'/doors.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then
        b={start=false,select=false,a=false,b=false,up=frame>=1180 and frame<1183,
            down=false,left=false,right=frame>=1450 and frame<2200 and not returned}
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        w(0x707,1);w(0x706,0);w(0x769,3);w(0x561,1)
        w(0x701,0);w(0x75C,1);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1)
    end
    if frame==1150 then
        for x=0,5 do w(0xB6+x,0)end
        w(0x4D,40);w(0x70,0)
        check(r(0x60D0+0xB3)==0x54,'street contains the original open door')
        w(0xB6,1);w(0xA1,0x19);w(0xBC,255);w(0xAF,0x80)
        w(0x4E,48);w(0x3C,1);w(0x2A,176);w(0x71,0);w(0x5C3,0)
    end
    if frame>=1180 and frame<1300 and r(0x74C)~=0 then stolen=true end
    if frame>=1250 and r(0x561)==0x1C and r(0x736)==11 then entered=true end
    if entered and frame>=1450 and r(0x561)==1 and r(0x736)==11 then returned=true end
    if frame==2300 then
        f:write(string.format('end room=%02X page=%d x=%d y=%d mode=%d world=%d\n',r(0x561),r(0x3B),r(0x4D),r(0x29),r(0x736),r(0x707)))
        check(entered,'Up enters the configured interior room 1C, not the village entrance')
        check(not stolen,'nearby villager does not intercept doorway Up')
        check(returned,'leaving the interior returns to its original street')
        check(r(0xB5)==1 and r(0x774)>0,'player remains alive through both transitions')
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close();stopScenario(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
