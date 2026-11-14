-- Real-loop full-body jump, crouch and castle-exit regression.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local frame,errors=0,0
local startY,peak=nil,nil
local rose,fell,landed,ducked,world=false,false,false,false,false
local f=assert(io.open(OUTPUT_DIR..'/breath-height.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n')
    if not ok then errors=errors+1 end
end
local function fullBody()
    local head,tail=false,false
    for _,a in ipairs({0x228,0x22C,0x230})do if r(a)<0xF0 then head=true end end
    for _,a in ipairs({0x214,0x218,0x21C})do if r(a)<0xF0 then tail=true end end
    return head and tail
end
emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then
        b={start=false,select=false,a=frame>=1030 and frame<1052,b=false,
            up=false,down=frame>=1130 and frame<1160,left=false,
            right=frame>=1200 and frame<2100 and not world}
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then check(r(0x736)==11,'fresh castle gameplay');startY=r(0x29);peak=startY end
    if frame>=1030 and frame<1120 then
        peak=math.min(peak,r(0x29))
        if r(0x479)>0 and fullBody()then
            if r(0x57D)>=128 then rose=true else fell=true end
        end
        if rose and r(0x479)==0 and math.abs(r(0x29)-startY)<=1 then landed=true end
    end
    if frame==1048 then screenshot('breath-height-jump')end
    if frame>=1130 and frame<1160 and r(0x80)==6 then ducked=true end
    if frame>=1200 and r(0x736)==5 then world=true end
    if frame==2100 then
        check(rose and fell and peak<startY-8,'whole body remains visible through ascent and descent')
        check(landed,'jump returns to original floor')
        check(ducked,'grounded crouch remains available')
        check(world and r(0xB5)==1,'player clears castle side exit alive')
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close();stopScenario(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
