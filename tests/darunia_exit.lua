-- Run with the generated world/barba-test.nes so the F6 state matches the ROM.
dofile(TEST_DIR..'/newgame.lua')
local folder=assert(emu.getRomInfo().path:match('^(.*)[/\\][^/\\]+$'))
local stateFile=assert(io.open(folder..'/darunia.mss','rb'),
    'Use --rom with the Towns and World test-pack ROM next to darunia.mss')
local state=stateFile:read('*a')
stateFile:close()

local mem=emu.memType.nesMemory
local function r(address) return emu.read(address,mem) end
local function w(address,value) emu.write(address,value,mem) end
local function playerX() return r(0x3B)*256+r(0x4D) end
local report=assert(io.open(OUTPUT_DIR..'/darunia_exit.txt','w'))
local frame,visit,enteredAt,lastX,stuck=0,1,0,0,0
local phase='load'
local jumpAt,sawDownstab,sawGenerator=nil,false,false

local function record(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n')
    report:flush()
end

local function finish(ok,message)
    if phase=='finished' then return end
    phase='finished'
    record(ok,message)
    report:write('RESULT '..(ok and 'PASS' or 'FAIL')..'\n')
    report:close()
    stopScenario(ok and 0 or 1)
end

emu.addMemoryCallback(function()
    if phase~='load' then return end
    assert(emu.loadSavestate(state),'Darunia F6 failed to load')
    phase='town'
end,emu.callbackType.exec,0xC010)

-- The old build stomped the invisible generator while approaching the exit.
emu.addMemoryCallback(function(address,value)
    if value==2 and visit==2 and phase=='crossing' and r(0xA1+address-0xB6)==0x0B then
        finish(false,'stomp sent the bubble generator into its death animation')
    end
end,emu.callbackType.write,0xB6,0xBB)

emu.addEventCallback(function()
    local buttons={}
    if phase=='town' or phase=='detour' then
        buttons.left=true
    elseif phase=='crossing' then
        buttons.right=true
        if visit==2 and not jumpAt and playerX()>=0x3A3 and r(0x479)==0 then jumpAt=frame end
        if jumpAt and (frame-jumpAt<14 or r(0x479)~=0) then
            buttons.a=frame-jumpAt<10
            buttons.down=frame-jumpAt>=10
        elseif stuck>18 then
            buttons.a=stuck%32<12
        end
    end
    emu.setInput(buttons,0)
end,emu.eventType.inputPolled)

emu.addEventCallback(function()
    if phase=='finished' then return end
    frame=frame+1
    local mode=r(0x736)
    local x=playerX()
    if (phase=='town' or phase=='reenter') and mode==5 then
        -- Select the native East Hyrule key-area entry at ($09,$24). Mode 6
        -- loads room $06 from the west on visit one and the east on visit two.
        w(0x748,0x08);w(0x74,0x09);w(0x73,0x24)
        w(0x562,visit==1 and 1 or 2);w(0x736,6)
        phase='enter'
    elseif phase=='enter' and mode==0x0B then
        if r(0x561)~=0x06 or r(0x707)~=0 or r(0x706)~=2 then
            finish(false,'expected the East Hyrule forced encounter in room $06')
            return
        end
        phase=visit==1 and 'crossing' or 'detour'
        enteredAt=frame
    elseif phase=='detour' and (x<0x350 or frame-enteredAt>250) then
        phase='crossing'
    elseif phase=='crossing' then
        if visit==2 and mode==0x0B then
            if r(0x80)==9 then sawDownstab=true end
            if jumpAt and frame-jumpAt>=14 and r(0x479)==0 and not sawDownstab and x<0x3D5 then
                jumpAt=nil
            end
            for slot=0,5 do
                if r(0xB6+slot)==1 and r(0xA1+slot)==0x0B then sawGenerator=true end
            end
        end
        if mode==5 then
            if x<0x3EF or r(0x74)~=0x0A or r(0x73)~=0x24 or r(0x700)~=3 then
                finish(false,'expected a live return through the right exit')
                return
            end
            if visit==2 then
                finish(sawDownstab and sawGenerator,'right exit after re-entry, detour and downstab with bubble generator active')
                return
            end
            record(true,'first traversal returns through the right exit')
            visit=2
            phase='reenter'
        end
    end
    if x==lastX then stuck=stuck+1 else stuck=0;lastX=x end
    if frame>=2200 then finish(false,string.format('timed out in %s at x=$%03X',phase,x)) end
end,emu.eventType.endFrame)
