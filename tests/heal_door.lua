-- Test Rauru room 2 healing lady ($17): emerges, talks on B, heals Barba on entering her door.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local frame,errors=0,0
local healerSlot,emerged,talked,healerText,doorOpened,healed=nil,false,false,false,false,false
local doorColAddr=nil
local saw16,saw4=false,false
local f=assert(io.open(OUTPUT_DIR..'/heal-door.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
local function findHealer()
    for x=0,5 do
        if r(0xB6+x)==1 and r(0xA1+x)==0x17 then return x end
    end
    return nil
end
local function playerWorldX() return r(0x3B)*256+r(0x4D) end
local function actorWorldX(x) return r(0x3C+x)*256+r(0x4E+x) end
emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then
        b={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
        if r(0x74C)~=0 then
            if r(0x524)>=6 and r(0x524)<=9 and (frame%16)<3 then b.b=true end
        elseif frame>=1150 and r(0x736)==11 and r(0x726)==0 then
            if not healerSlot then
                b.right=true
            elseif not emerged then
                local dx=actorWorldX(healerSlot)-playerWorldX()
                if dx>24 then b.right=true elseif dx<-24 then b.left=true end
            elseif not talked then
                local dx=actorWorldX(healerSlot)-playerWorldX()
                if dx>12 then b.right=true
                elseif dx<-12 then b.left=true
                elseif frame%4==0 then b.b=true end
            elseif not doorOpened then
                local dx=actorWorldX(healerSlot)-playerWorldX()
                if dx>4 then b.right=true elseif dx<-4 then b.left=true end
            elseif not healed and r(0x561)==2 and doorColAddr then
                local page=math.floor((doorColAddr-0x6000)/(13*16))
                local rem=(doorColAddr-0x6000)%(13*16)
                local col=rem%16
                local doorX=page*256+col*16-4
                local dx=doorX-playerWorldX()
                if dx>2 then b.right=true
                elseif dx<-2 then b.left=true
                elseif r(doorColAddr)==0x54 then b.up=true end
            elseif not healed and r(0x561)~=2 then
                b.right=true
            end
        end
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        w(0x707,1);w(0x706,0);w(0x769,3);w(0x561,2);w(0xC9,0)
        w(0x701,0);w(0x75C,1);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1)
        w(0x774,0x20) -- damage player so we can verify healing restores HP to $FF
    end
    if r(0x74C)==4 then saw4=true end
    if frame>=1150 and r(0x736)==11 and r(0x726)==0 then
        if r(0x561)~=2 and not saw16 then
            saw16=true
            f:write(string.format('inside room=%02X\n',r(0x561)))
            for x=0,5 do
                if r(0xB6+x)==1 then
                    f:write(string.format('  actor slot=%d kind=%02X af=%02X x=%d\n',x,r(0xA1+x),r(0xAF+x),actorWorldX(x)))
                end
            end
        end
        if not healerSlot then healerSlot=findHealer() end
        if healerSlot and r(0xB6+healerSlot)==1 and r(0xA1+healerSlot)==0x17 then
            if r(0xAF+healerSlot)==0 and r(0x2A+healerSlot)>=168 then emerged=true end
            if r(0x74C)~=0 and r(0x48B)==healerSlot then
                talked=true
                if r(0x569)+256*r(0x56A)==LABELS.TownHealerText then healerText=true end
            end
            if talked and not doorOpened then
                for off=0,13*16*4-1 do
                    if r(0x6000+off)==0x54 then
                        local page=math.floor(off/(13*16))
                        local col=(off%(13*16))%16
                        local cx=page*256+col*16
                        if math.abs(cx-actorWorldX(healerSlot))<32 then
                            doorOpened=true; doorColAddr=0x6000+off; break
                        end
                    end
                end
            end
        end
        if r(0x774)>0x40 then healed=true end
    end
    if frame==2800 then
        f:write(string.format('healerSlot=%s emerged=%s talked=%s healerText=%s doorOpened=%s saw16=%s saw4=%s healed=%s hp=%02X px=%d door=%s val=%s mode=%d dlg=%d\n',
            tostring(healerSlot),tostring(emerged),tostring(talked),tostring(healerText),
            tostring(doorOpened),tostring(saw16),tostring(saw4),tostring(healed),r(0x774),playerWorldX(),
            doorColAddr and string.format('%04X',doorColAddr) or 'nil',
            doorColAddr and string.format('%02X',r(doorColAddr)) or 'nil',r(0x736),r(0x74C)))
        check(healerSlot~=nil,'Rauru room 2 $17 healer spawned')
        check(emerged,'$17 healer emerged from closed door')
        check(talked,'B triggers conversation with $17 healer')
        check(healerText,'$17 healer uses TownHealerText')
        check(doorOpened,'$17 healer opens doorway ($54)')
        check(healed,'Entering $17 healer doorway heals Barba')
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close();stopScenario(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
