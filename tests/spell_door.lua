-- Rauru magic-house opener ($18): emerges from closed door, invulnerable to fire,
-- talks on Up (TownMagicText), opens door, and Barba enters to learn Shield/Scales ($077B bit 0).
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local frame,errors=0,0
local openerSlot,openerEmerged,shotFired,talked,magicText,doorOpened,enteredHouse,learnedSpell=nil,false,false,false,false,false,false,false
local emergeDoorBad=false
local doorColAddr,doorRoom=nil,nil
local talkFrame,doorFrame=nil,nil
local f=assert(io.open(OUTPUT_DIR..'/spell-door.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
local function findOpener()
    for x=0,5 do
        local k=r(0xA1+x)
        if r(0xB6+x)==1 and k>=0x13 and k<=0x18 then return x end
    end
    return nil
end
local function playerWorldX() return r(0x3B)*256+r(0x4D) end
local function actorWorldX(x) return r(0x3C+x)*256+r(0x4E+x) end
emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then
        b={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
        if r(0x74C)~=0 and not enteredHouse then
            -- Dismiss any dialogue with B (Zelda II uses B to close/skip dialogue)
            if r(0x524)<=9 and (frame%16)<3 then b.b=true end
        elseif frame>=1150 and r(0x736)==11 and r(0x726)==0 then
            if not openerSlot then
                -- Walk right down Rauru street until the $18 magic-house opener spawns
                b.right=true
            elseif not openerEmerged then
                local dx=actorWorldX(openerSlot)-playerWorldX()
                if dx>24 then b.right=true elseif dx<-24 then b.left=true end
            elseif not shotFired then
                -- Breathe fire toward the opener to verify she is invulnerable
                local dx=actorWorldX(openerSlot)-playerWorldX()
                if dx>0 and r(0x9F)~=1 then b.right=true
                elseif dx<0 and r(0x9F)~=2 then b.left=true
                else b.b=true; shotFired=true end
            elseif not talked then
                if r(0x74C)==0 then
                    local dx=actorWorldX(openerSlot)-playerWorldX()
                    if dx>12 then b.right=true
                    elseif dx<-12 then b.left=true
                    elseif frame%4==0 then b.b=true end
                end
            elseif not doorOpened then
                -- Follow the opener back to her door closely so we're at the door when it becomes $54
                local dx=actorWorldX(openerSlot)-playerWorldX()
                if dx>4 then b.right=true elseif dx<-4 then b.left=true end
            elseif not enteredHouse then
                -- Stand at the opened door and press Up immediately while it is $54
                if doorColAddr then
                    local page=math.floor((doorColAddr-0x6000)/(13*16))
                    local rem=(doorColAddr-0x6000)%(13*16)
                    local col=rem%16
                    local doorX=page*256+col*16
                    local dx=doorX-playerWorldX()
                    if dx>2 then b.right=true
                    elseif dx<-2 then b.left=true
                    elseif r(doorColAddr)==0x54 then b.up=true end
                end
            else
                -- Inside Wise Man's house: walk toward Wise Man and dismiss dialogue
                if r(0x74C)~=0 then
                    if (frame%16)<3 then b.b=true end
                else
                    b.right=true
                end
            end
        end
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        w(0x707,1);w(0x706,0);w(0x769,3);w(0x561,1)
        w(0x701,0);w(0x75C,1);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1)
    end
    if frame>=1150 and r(0x736)==11 and r(0x726)==0 then
        if not enteredHouse then
            if not openerSlot then openerSlot=findOpener() end
            if openerSlot and r(0xB6+openerSlot)==1 and r(0xA1+openerSlot)>=0x13 and r(0xA1+openerSlot)<=0x18 then
                local af=r(0xAF+openerSlot)
                if af>=0x81 and af<=0xB0 then
                    local col=math.floor(r(0x0599+openerSlot)/16)
                    local page=r(0x059F+openerSlot)
                    if r(0x6000+page*0xD0+0xA0+col)~=0x8B then emergeDoorBad=true end
                end
                if af==0 and r(0x2A+openerSlot)>=168 then openerEmerged=true end
                if r(0x74C)~=0 and r(0x48B)==openerSlot then
                    if not talked then talkFrame=frame end
                    talked=true
                    magicText=true
                end
                -- Check if any $8B closed door became $54 (open)
                if talked and not doorOpened then
                    for off=0,13*16*4-1 do
                        local v=r(0x6000+off)
                        if v==0x54 then
                            local page=math.floor(off/(13*16))
                            local col=(off%(13*16))%16
                            local cx=page*256+col*16
                            if math.abs(cx-actorWorldX(openerSlot))<32 then
                                doorOpened=true; doorFrame=frame; doorColAddr=0x6000+off; doorRoom=r(0x561); break
                            end
                        end
                    end
                end
            end
            if doorOpened and r(0x561)~=doorRoom then enteredHouse=true end
        else
            if (r(0x77B)&1)~=0 then learnedSpell=true end
        end
    end
    if frame==3200 then
        f:write(string.format('openerSlot=%s talkF=%s doorF=%s talker=%d emerged=%s shot=%s talked=%s doorOpened=%s doorAddr=%s val=%s px=%d room=%02X mode=%d de=%d dlg=%d entered=%s spell=%02X\n',
            tostring(openerSlot),tostring(talkFrame),tostring(doorFrame),r(0x48B),tostring(openerEmerged),tostring(shotFired),tostring(talked),
            tostring(doorOpened),doorColAddr and string.format('%04X',doorColAddr) or 'nil',
            doorColAddr and string.format('%02X',r(doorColAddr)) or 'nil',playerWorldX(),r(0x561),r(0x736),r(0xDE),r(0x74C),tostring(enteredHouse),r(0x77B)))
        check(openerSlot~=nil,'Rauru $14 house-opener spawned')
        check(openerEmerged,'$14 opener emerged from closed door when Barba approached')
        check(not emergeDoorBad,'$14 opener emerge animation targets the real $8B doorway')
        check(shotFired and r(0xAF+openerSlot)<0xA0,'$14 opener is invulnerable to fireballs')
        check(talked,'B triggers conversation with $14 opener')
        check(magicText,'$14 opener starts dialogue cleanly')
        check(doorOpened,'$14 opener opens doorway in collision RAM')
        check(enteredHouse,'Barba enters the opened spell house on Up')
        check(learnedSpell,'Barba learns the first Shield/Scales spell ($077B bit 0)')
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close();stopScenario(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
