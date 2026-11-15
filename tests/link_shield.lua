-- Lava Link shield experiment: fire that reaches the boss outside its beam window
-- (closed, shield-up head) clanks and does no damage; fire inside the window
-- (hold phase, timer $30-$5F: half/open heads) damages it normally.
dofile(TEST_DIR..'/newgame.lua')
local frame=0
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/link_shield.txt','w'))
local errors=0
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n')
    if not ok then errors=errors+1 end
end
local bossSlot=nil
local function inWindow(slot)
    local t=r(0x0504+slot)
    return r(0x0499)==2 and t>=0x30 and t<0x60
end
local openHits,shieldHits,clanks,hurt,leaks=0,0,0,0,0
local lastWasShield=false
local prevHp=nil
local shot={}
-- The damage routine (bank 7 $E726-$E735) stores the new HP; classify each hit.
emu.addMemoryCallback(function(addr,value)
    local pc=emu.getState()['cpu.pc']
    local slot=addr-0xC2
    if r(0xA1+slot)~=0x21 or pc<0xE700 or pc>=0xE800 then return end
    if inWindow(slot) then openHits=openHits+1;lastWasShield=false
    else shieldHits=shieldHits+1;lastWasShield=true end
end,emu.callbackType.write,0xC2,0xC7)
emu.addMemoryCallback(function(addr,value)
    local pc=emu.getState()['cpu.pc']
    if value==2 and pc>=0xA7A9 and pc<0xA7E9 then clanks=clanks+1 end
end,emu.callbackType.write,0xEC,0xEC)
emu.addMemoryCallback(function(addr,value)
    local pc=emu.getState()['cpu.pc']
    if value==1 and pc>=0xA795 and pc<0xA7A9 then hurt=hurt+1 end
end,emu.callbackType.write,0xE9,0xE9)

emu.addEventCallback(function()
    local buttons=newGameInput(frame)
    if bossSlot~=nil and frame>1200 then
        local bx=r(0x4E+bossSlot)
        local by=r(0x2A+bossSlot)
        local px=r(0x4D)
        local py=r(0x29)
        if bx<px-16 then buttons.left=(frame%16<2)
        elseif bx>px+16 then buttons.right=(frame%16<2) end
        buttons.a=buttons.a or (py>by+8 and frame%40<20)
        buttons.b=(math.abs(py-by)<=20 and frame%10<3)
    end
    emu.setInput(buttons,0)
end,emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        w(0x707,4);w(0x706,2);w(0x769,4);w(0x561,0x3A)
        w(0x568,5);w(0x56B,6);w(0x56C,1);w(0x701,0);w(0x75C,1);w(0x704,0)
        w(0x736,0);w(0x73D,0);w(0x726,1)
        w(0x774,255);w(0x784,8);w(0x777,8);w(0x778,8)
    end
    if frame>1200 then
        if frame%60==0 then w(0x774,255) end
        bossSlot=nil
        for slot=0,5 do
            if r(0xB6+slot)>0 and r(0xA1+slot)==0x21 then bossSlot=slot end
        end
        if bossSlot~=nil then
            local hp=r(0xC2+bossSlot)
            if prevHp~=nil and hp<prevHp and lastWasShield then leaks=leaks+1 end
            prevHp=hp
        end
    end
    if shieldHits>0 and not shot.block then shot.block=true;screenshot('link_shield_block') end
    if openHits>0 and not shot.open then shot.open=true;screenshot('link_shield_open') end
    if frame==3400 then
        report:write(string.format('open_hits=%d shield_hits=%d clanks=%d hurt=%d leaks=%d hp=%s\n',
            openHits,shieldHits,clanks,hurt,leaks,tostring(prevHp)))
        check(shieldHits>0,'fire reached Lava Link while the shield was up')
        check(clanks==shieldHits,'every shielded hit clanks ('..clanks..'/'..shieldHits..')')
        check(leaks==0,'shielded hits never lower HP')
        check(openHits>0,'fire damages Lava Link in its beam window')
        check(hurt==openHits,'Link hurt sound only for real hits ('..hurt..'/'..openHits..')')
        report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
        report:close()
        emu.stop()
    end
end,emu.eventType.endFrame)
