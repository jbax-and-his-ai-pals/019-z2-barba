-- Valley of Death wall encounter with native enemy spawns and controller-fired breath.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local function playerX()return r(0x3B)*256+r(0x4D)end
local function enemyX(slot)return r(0x3C+slot)*256+r(0x4E+slot)end
local report=assert(io.open(OUTPUT_DIR..'/rock_lizalfos.txt','w'))
local frame,slot,jumpAt,killedAt=0,nil,nil,nil
local rockSeen,upwardHit,finished=false,false,false
local errors=0
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n')
    if not ok then errors=errors+1 end
end

emu.addMemoryCallback(function()
    if slot and emu.getState()['cpu.x']==slot and r(0x0B)==1 then
        upwardHit=(r(0x5FC+r(0x11))&0xC0)==0x40 and (r(0xAF+slot)&3)==3
    end
end,emu.callbackType.exec,0xE726)

emu.addMemoryCallback(function()
    if slot and r(0x769)==2 and emu.getState()['cpu.x']==slot then rockSeen=true end
end,emu.callbackType.exec,0x9A18)

emu.addEventCallback(function()
    local buttons=newGameInput(frame)
    if slot and frame>=1140 and not killedAt then
        buttons.left=not jumpAt and playerX()-enemyX(slot)>43
        buttons.up=true
        if jumpAt and frame>=jumpAt then
            local age=(frame-jumpAt)%70
            buttons.a=age<34
            buttons.b=age>=15 and age<21
        end
    end
    emu.setInput(buttons,0)
end,emu.eventType.inputPolled)

emu.addEventCallback(function()
    if finished then return end
    frame=frame+1
    if frame==1000 then
        w(0x707,0);w(0x706,2);w(0x769,2);w(0x561,2)
        w(0x701,0);w(0x75C,0);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1)
        w(0x748,2);w(0x796,0x14);w(0x774,255)
    elseif frame==1080 then
        check(r(0x736)==11 and r(0x707)==0 and r(0x706)==2 and r(0x561)==2,
            'Valley of Death wall encounter loaded')
        for i=0,5 do
            if r(0xA1+i)==0x1D and r(0xB6+i)==1 then slot=i end
        end
        check(slot~=nil,'native rock-tossing Lizalfos spawned')
    end
    if slot and not killedAt then
        if frame>=1140 and not jumpAt and playerX()-enemyX(slot)<=43 then
            jumpAt=frame+14
        end
        if r(0xB6+slot)==2 then
            killedAt=frame
            screenshot('rock-lizalfos-hit')
        end
    end
    if frame==1800 or (killedAt and frame==killedAt+60) then
        check(rockSeen,'Lizalfos throws native rocks before the hit')
        check(upwardHit and killedAt~=nil,'airborne Up+B kills an exposed Lizalfos with upward breath')
        check(killedAt and r(0xB6+slot)~=2 and r(0x736)==11 and r(0xB5)==1,
            'death animation completes and play continues')
        report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
        finished=true
        report:close();stopScenario(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
