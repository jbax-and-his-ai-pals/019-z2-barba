-- Reload every generated state and let the real game run after loading.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local frame=0
local age=0
local index=0
local pending=false
local failures=0
local file=assert(io.open(PACK_DIR..'/validation.txt','w'))
local ids={'castle','combat','spells','lava-ledge','lava-surface','barba','raft'}
local function check(ok,text)
    file:write((ok and 'PASS ' or 'FAIL ')..text..'\n');file:flush()
    if not ok then failures=failures+1 end
end
local function nextState()
    index=index+1
    if not ids[index] then
        file:write('RESULT '..(failures==0 and 'PASS' or 'FAIL')..'\n');file:close()
        stopScenario(failures==0 and 0 or 1);return
    end
    local stateFile=assert(io.open(PACK_DIR..'/'..ids[index]..'.mss','rb'))
    local state=stateFile:read('*a');stateFile:close()
    check(emu.loadSavestate(state),ids[index]..' native .mss loads')
    age=0
end
emu.addEventCallback(function()
    emu.setInput({start=index==2 and age>=90 and age<93,select=false,a=false,b=false,up=false,down=false,left=false,right=false},0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if index==0 then
        if frame==120 then pending=true end
        return
    end
    age=age+1
    if index==2 then
        if age==10 then
            check(r(0x770)*256+r(0x771)==2000,'upgraded combat checkpoint has correct next-level XP target')
            emu.write(0x775,0,mem);emu.write(0x776,50,mem)
        end
        if age==30 then check(r(0x74C)==0,'small XP gain does not open an unaffordable upgrade menu') end
        if age==40 then emu.write(0x775,7,mem);emu.write(0x776,0xD0,mem) end
        if age==80 then check(r(0x74C)==1,'affordable XP gain opens level-up menu') end
        if age==400 then
            check(r(0x777)==5 and r(0x775)==0 and r(0x776)==0,'accepting upgrade raises attack and spends XP once')
            check(r(0x74C)==0,'upgrade returns to normal gameplay without looping (dialog='..r(0x74C)..', menu='..r(0x524)..')')
        end
    end
    if age==3 then
        check(r(0xB5)==1,ids[index]..' player is alive after load')
        local pixels=emu.getScreenBuffer()
        local distinct={}
        for i=1,#pixels,97 do distinct[pixels[i]]=true end
        local colors=0;for _ in pairs(distinct)do colors=colors+1 end
        check(colors>3,ids[index]..' visible game frame')
        if index<7 then check(r(0x736)==11,ids[index]..' side-view gameplay ready') end
        if index==2 then check(r(0x774)<255 and r(0x707)==3,'combat has damaged health and Palace 1 geometry') end
        if index==3 then
            local spells=true
            for a=0x77B,0x782 do if r(a)==0 then spells=false end end
            check(spells and (r(0x796)&0x14)==0x14,'all spells and both thrust techniques unlocked')
            check(r(0x773)==255 and r(0x774)==255,'spell sandbox begins with full meters')
        end
        if index==5 then check(r(0xA7)&4~=0 and r(0x479)==0,'lava surface supports the player') end
        if index==6 then
            local boss=false
            for slot=0,5 do if r(0xA1+slot)==0x21 and r(0xB6+slot)>0 then boss=true end end
            check(boss and r(0x561)==0x3A and r(0x76E)==24,'native Palace 6 boss and graphics present')
        end
        if index==7 then check(r(0x736)==24 and r(0x7A9)>0,'native raft crossing is active') end
    end
    if index==6 and age==90 then screenshot('test-pack-boss-active') end
    if age==(index==2 and 410 or 120) then
        check(r(0x774)>0 and r(0x76C)~=2,ids[index]..' remains playable for 120 frames')
        if index==7 then check(r(0x706)==2 and r(0x736)==5,'sea crossing ends on East Hyrule overworld') end
        pending=true
    end
end,emu.eventType.endFrame)
emu.addMemoryCallback(function()
    if pending then pending=false;nextState()end
end,emu.callbackType.exec,0xC07B)
