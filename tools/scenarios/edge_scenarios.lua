-- Generate and reload-check last-life danger and the actual GAME OVER screen.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local phase='boot'
local age=0
local frame=0
local sawGameOver=false
local errors=0
local report=assert(io.open(PACK_DIR..'/validation.txt','w'))
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n');report:flush()
    if not ok then errors=errors+1 end
end
local function load(path)
    local f=assert(io.open(path,'rb'));local state=f:read('*a');f:close()
    assert(emu.loadSavestate(state),'Cannot load '..path)
end
local function save(id)
    local f=assert(io.open(PACK_DIR..'/'..id..'.mss','wb'))
    f:write(emu.createSavestate());f:close()
end
local function picture(id)
    local f=assert(io.open(PACK_DIR..'/'..id..'.png','wb'))
    f:write(emu.takeScreenshot());f:close()
end
emu.addEventCallback(function()
    emu.setInput({start=phase=='continue' and age%40<3},0)
end,emu.eventType.inputPolled)
emu.addMemoryCallback(function()
    if phase=='danger' or phase=='verify-over' then sawGameOver=true end
end,emu.callbackType.exec,0xCA72)
emu.addMemoryCallback(function()
    if phase=='load' then
        phase='settle';age=0;load(SOURCE_STATE)
        w(0x0700,1);w(0x0774,1);w(0x0494,0);w(0x050C,0);w(0x048D,0)
        w(0x074F,r(0x074F)|0x40)
    elseif phase=='save-danger' then
        save('game-over-danger');load(PACK_DIR..'/game-over-danger.mss')
        check(r(0x0700)==1 and r(0x0774)==1,'F1 reload: one life and one health unit')
        check(r(0x0736)==11 and r(0x0561)==5,'F1 reload: Palace 1 combat corridor')
        phase='danger';age=0
    elseif phase=='save-over' then
        save('game-over');load(PACK_DIR..'/game-over.mss')
        sawGameOver=false;phase='verify-over';age=0
    end
end,emu.callbackType.exec,0xC07B)
emu.addEventCallback(function()
    frame=frame+1;age=age+1
    if phase=='boot' and frame==120 then phase='load'
    elseif phase=='settle' and age==8 then phase='save-danger'
    elseif phase=='danger' then
        if age==1 then picture('game-over-danger') end
        if sawGameOver then
            check(true,'F1 natural enemy contact reaches GAME OVER in '..age..' frames')
            phase='save-over'
        end
    elseif phase=='verify-over' and age>=2 then
        picture('game-over')
        check(sawGameOver,'F2 reload: native GAME OVER screen is active')
        phase='continue';age=0
    elseif phase=='continue' and r(0x0736)==11 and r(0x074C)==0 then
        check(r(0x0700)==3,'F2 Start continues to gameplay with three lives')
        phase='done'
        report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');report:close()
        stopScenario(errors==0 and 0 or 1)
    end
    if phase~='done' and frame>5000 then
        phase='done';check(false,'edge checkpoint generation timed out')
        report:write('RESULT FAIL\n');report:close();stopScenario(1)
    end
end,emu.eventType.endFrame)
