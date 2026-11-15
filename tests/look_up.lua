-- Looking-up head: an airborne Up+B attack (windup and attack) and rising with
-- Up held draw tall frame 8; forward air and ground attacks keep frames 4/5.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local frame,errors=0,0
local DRAW_INDEX=0x05FA -- tall frame * 9 after BarbaDisplay
local seen={}
local f=assert(io.open(OUTPUT_DIR..'/look-up.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n')
    if not ok then errors=errors+1 end
end
local function note(key)
    seen[key]=seen[key] or {}
    seen[key][math.floor(r(DRAW_INDEX)/9)]=true
end
local function has(p,v)return seen[p]~=nil and seen[p][v]==true end
-- Phases by hundreds of frames: 10 upward jump+attack, 11 rising Up-hold only,
-- 12 forward air attack, 13 ground attack. Jump at t=30, Up from t=33, B at t=36.
emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then
        local t=frame%100
        local phase=math.floor(frame/100)
        b={start=false,select=false,left=false,right=false,down=false,
           a=t>=30 and t<52 and phase<=12,
           up=(phase==10 or phase==11) and t>=33 and t<60,
           b=(phase==10 or phase==12 or phase==13) and t>=36 and t<38}
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        check(r(0x736)==11,'fresh castle gameplay')
        w(0x0796,r(0x0796)|0x04) -- Upward tech
    end
    local t=frame%100
    local phase=math.floor(frame/100)
    local atk=r(0x400)
    if frame>=1000 and t>=30 and t<60 then
        if phase==11 and r(0x80)==8 then note(11) end
        if phase~=11 and (atk==1 or atk==2) then note(phase) end
    end
    if frame==1040 then screenshot('look-up-windup')end
    if frame==1045 then screenshot('look-up-volley')end
    if frame==1135 then screenshot('look-up-rising')end
    if frame==1245 then screenshot('look-up-forward-air')end
    if frame==1400 then
        check(has(10,8),'airborne upward attack draws looking-up frame 8')
        check(not has(10,4) and not has(10,5),'airborne upward attack never shows forward windup/jaw')
        check(has(11,8),'rising with Up held draws looking-up frame 8')
        check(has(12,5) and not has(12,8),'forward air attack keeps open-jaw frame 5')
        check(has(13,5) and not has(13,8),'ground attack keeps open-jaw frame 5')
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close();stopScenario(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
