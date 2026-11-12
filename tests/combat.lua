-- Controlled enemy fixtures in the original game loop. No projectile can
-- interfere: health is below full and the Fire spell is inactive.
dofile(TEST_DIR..'/newgame.lua')
local frame=0
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/combat.txt','w'))
local errors=0
local cases={{dir=1,duck=false},{dir=2,duck=false},{dir=1,duck=true},{dir=2,duck=true}}
local current=0
local hit=false
local function input()
    local buttons=newGameInput(frame)
    if frame>=1000 and current>0 then
        local start=1000+(current-1)*100
        buttons.down=cases[current].duck
        buttons.b=(frame>=start+10 and frame<start+13)
    end
    emu.setInput(buttons,0)
end
local function tick()
    frame=frame+1
    if frame>=1000 and frame<1400 then
        local index=math.floor((frame-1000)/100)+1
        if index~=current then
            current=index;hit=false
            local test=cases[current]
            w(0x5F,test.dir);w(0x9F,test.dir);w(0x70,0);w(0x400,0)
            w(0x76F,0);w(0x774,100);w(0x784,8)
            for address=0xB6,0xBB do w(address,0) end
            w(0xB6,1);w(0xA1,4);w(0xC2,8);w(0xA8,0);w(0x1A,1)
            w(0x444,0);w(0x40E,0);w(0x518,0)
        end
        local test=cases[current]
        -- Keep the Bot fixture stationary; its vulnerability and damage handlers
        -- run unchanged. Place it near the extended end of the flame plume.
        local offset=test.dir==1 and 36 or -24
        w(0x4E,(r(0x4D)+offset)%256);w(0x3C,r(0x3B))
        w(0x2A,r(0x29)+(test.duck and 20 or 4));w(0x71,0);w(0x57E,0)
        if r(0xC2)<8 or r(0x40E)>0 then hit=true end
        local elapsed=frame-(1000+(current-1)*100)
        if elapsed==30 then
            screenshot('combat-'..current)
            report:write((hit and 'PASS ' or 'FAIL ')..'flame damages enemy: direction '..test.dir..' crouch '..tostring(test.duck)..' HP '..r(0xC2)..'\n')
            if not hit then errors=errors+1 end
        end
    end
    if frame==1400 then
        report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
        report:close();stopScenario(errors==0 and 0 or 1)
    end
end
emu.addEventCallback(input,emu.eventType.inputPolled)
emu.addEventCallback(tick,emu.eventType.endFrame)
