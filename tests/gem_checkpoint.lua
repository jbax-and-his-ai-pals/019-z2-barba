-- Reload the generated gem checkpoint and complete the native celebration.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local frame,age,errors=0,0,0
local loaded=false
local sawPlacement,sawFanfare,sawRoar,sawRelease=false,false,false,false
local sawTorso=false
local torsoFrames=0
local starts=0
local report=assert(io.open(OUTPUT_DIR..'/gem-checkpoint.txt','w'))
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n')
    if not ok then errors=errors+1 end
end
emu.addEventCallback(function()
    emu.setInput({right=loaded and age<100},0)
end,emu.eventType.inputPolled)
emu.addMemoryCallback(function()
    if frame>=120 and not loaded then
        local f=assert(io.open(OUTPUT_DIR..'/build-report.json','r'))
        local hash=assert(f:read('*a'):match('"output_sha256"%s*:%s*"([a-f0-9]+)"'));f:close()
        f=assert(io.open(OUTPUT_DIR..'/test-pack/'..hash:sub(1,12)..'/gem/palace-gem.mss','rb'))
        assert(emu.loadSavestate(f:read('*a')));f:close();loaded=true;age=0
        check(r(0x736)==11 and r(0x3B)==3,'checkpoint reloads beyond the boss beside the statue')
        check(r(0x5EE)==0 and r(0x794)==1,'checkpoint starts before final gem placement and roar')
    end
end,emu.callbackType.exec,0xC07B)
emu.addMemoryCallback(function(_,value)
    if loaded and value==0x40 then sawFanfare=true end
end,emu.callbackType.write,0xEB)
emu.addMemoryCallback(function(_,value)
    if loaded and value==0x88 then starts=starts+1 end
end,emu.callbackType.write,0x5EE)
emu.addEventCallback(function()
    frame=frame+1
    if not loaded then return end
    age=age+1
    if r(0x794)==0 then sawPlacement=true end
    if r(0x5EE)==0x88 and r(0x5FA)==72 then
        if r(0x220)==r(0x5F4)+32 and r(0x224)==r(0x220)
            and r(0x204)==r(0x5F4)-8 then
            sawTorso=true
            torsoFrames=torsoFrames+1
            if torsoFrames==10 then screenshot('gem-checkpoint-roar') end
        end
        sawRoar=true
    elseif sawRoar and r(0x5EE)==0 and r(0x5FA)~=72 then sawRelease=true end
    if age==600 then
        check(sawPlacement,'walking right places the final gem without fighting')
        check(sawFanfare,'native gem victory fanfare plays')
        check(sawRoar and sawRelease,'native celebration roars with head raised then releases pose')
        check(sawTorso,'gem roar completes two torso chunks with feet anchored')
        check(starts==1,'celebration plays exactly one roar')
        report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');report:close()
        stopScenario(errors==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
