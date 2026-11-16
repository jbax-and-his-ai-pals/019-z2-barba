-- Hidden house-opener ($13..$18, AF=$80) must emerge only when Barba is really
-- within native 96 px of it. Native L97E1 judges distance from $C9/$CD, which
-- belong to whichever actor drew last, so an opener could emerge while its door
-- was pages away and paint a phantom door into the visible nametable.
-- Pre-fix this emerged at dx=223; TownOpenerGate holds it until dx<=96.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local frame,errors=0,0
local doorPage,doorCol=nil,nil
local farEmerged,nearEmerged=false,false
local f=assert(io.open(OUTPUT_DIR..'/opener_far.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
local function findDoor(minPage)
    for page=3,minPage,-1 do
        for row=0,12 do
            for col=0,15 do
                if r(0x6000+page*0xD0+row*16+col)==0x8B then return page,col end
            end
        end
    end
end
local function spawnOpener(slot,page,col)
    w(0xB6+slot,1);w(0xA1+slot,0x13);w(0xAF+slot,0x80);w(0x5BD+slot,0);w(0x5C3+slot,0)
    w(0x1A+slot,1);w(0x4E+slot,col*16);w(0x3C+slot,page);w(0x2A+slot,0xA8);w(0x71+slot,0);w(0x60+slot,1)
end
emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then b={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=frame>1300 and not nearEmerged} end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        w(0x707,1);w(0x706,0);w(0x769,3);w(0x561,1)
        w(0x701,0);w(0x75C,1);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1)
    end
    if frame==1150 then
        doorPage,doorCol=findDoor(2)
        f:write(string.format('room=%02X door page=%s col=%s player=%d:%d scroll=%d:%d\n',r(0x561),
            tostring(doorPage),tostring(doorCol),r(0x3B),r(0x4D),r(0x72A),r(0x72C)))
        check(doorPage~=nil,'Rauru street has a closed door on page 2 or 3')
        for x=0,5 do w(0xB6+x,0) end
        -- Slot 0: on-screen walking opener next to Barba leaves $C9=0 and $CD near Link.
        w(0xB6,1);w(0xA1,0x13);w(0xAF,0);w(0x5C3,0);w(0x5BD,0x40);w(0x5B7,0)
        w(0x1A,1);w(0x4E,r(0x4D)+24);w(0x3C,r(0x3B));w(0x2A,0xB0);w(0x71,0)
        if doorPage then spawnOpener(1,doorPage,doorCol) end
    end
    if frame>1150 and frame<1300 and doorPage then
        local af=r(0xAF+1)
        if r(0xB6+1)==1 and r(0xA1+1)==0x13 and af~=0x80 then
            if not farEmerged then
                f:write(string.format('far opener left AF=$80 at frame %d: AF=%02X door=%d:%02X scroll=%d:%d\n',
                    frame,af,r(0x59F+1),r(0x599+1),r(0x72A),r(0x72C)))
            end
            farEmerged=true
        end
    end
    if frame==1300 then
        check(not farEmerged,'opener whose door is 512 px away stays hidden (no phantom door macro)')
    end
    if frame>1300 and doorPage and r(0xAF+1)~=0x80 and r(0xA1+1)==0x13 and not nearEmerged then
        nearEmerged=true
        local dx=doorPage*256+doorCol*16-(r(0x3B)*256+r(0x4D))
        f:write(string.format('opener emerged at frame %d, door dx=%d door=%d:%02X\n',frame,dx,r(0x59F+1),r(0x599+1)))
        check(math.abs(dx)<=112,'opener emerges only once Barba is near its doorway')
        check(r(0x59F+1)==doorPage and math.floor(r(0x599+1)/16)==doorCol,'emerging opener targets its own doorway')
    end
    if frame==1900 then
        check(nearEmerged,'opener still emerges when Barba walks up to its door')
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close();stopScenario(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
