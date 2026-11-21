-- Requires a current Tricky Movement pack. Walk into the shaft from F7.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(addr)return emu.read(addr,mem)end
local function readFile(path)
    local file=assert(io.open(path,'rb'))
    local data=file:read('*a');file:close()
    return data
end
local buildReport=readFile(OUTPUT_DIR..'/build-report.json')
local digest=assert(buildReport:match('"output_sha256"%s*:%s*"(%x+)"'))
local sample=readFile(OUTPUT_DIR..'/roar.dmc')
local sampleRate=tonumber(assert(buildReport:match('"rate_index"%s*:%s*(%d+)')))
local checkpoint=OUTPUT_DIR..'/test-pack/'..digest:sub(1,12)..'/movement/p6-drop-shaft.mss'
local frame,loadFrame,lives=0,nil,nil
local request,started,rate,address,length
local enables,fetches=0,0
local waveformMatches=true
local heldFallPose=true
local themeBeforeFall=0
local themeDuringFall=false
local fallingFrames=0

emu.addMemoryCallback(function()
    if frame>=120 and not loadFrame then
        assert(emu.loadSavestate(readFile(checkpoint)),'Cannot load F7')
        loadFrame=frame;lives=r(0x700)
    end
end,emu.callbackType.exec,0xC07B)
emu.addMemoryCallback(function()
    if loadFrame then request=frame end
end,emu.callbackType.exec,0xC705)
emu.addMemoryCallback(function(addr,value)
    if not loadFrame then return end
    if addr==0x4010 then rate=value end
    if addr==0x4012 then address=value end
    if addr==0x4013 then length=value end
end,emu.callbackType.write,0x4010,0x4013)
emu.addMemoryCallback(function(_,value)
    if not loadFrame or value~=0x1F then return end
    enables=enables+1
    if enables==1 then started=frame end
end,emu.callbackType.write,0x4015)
emu.addMemoryCallback(function(addr,value)
    if not started then return end
    fetches=fetches+1
    waveformMatches=waveformMatches and addr==0xF400+fetches-1 and value==sample:byte(fetches)
end,emu.callbackType.read,0xF400,0xFD70)
emu.addEventCallback(function()
    local age=loadFrame and frame-loadFrame or 0
    emu.setInput({right=age>=10 and age<26},0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if not loadFrame then return end
    local mode,track=r(0x736),r(0x7FB)
    if not request and mode==0x0B and track~=0 then themeBeforeFall=track end
    if started and mode==0x0F then
        fallingFrames=fallingFrames+1
        if r(0x5EE)&0x08~=0 then heldFallPose=false end
        if track~=0 then themeDuringFall=true end
    end
    if frame-loadFrame~=230 then return end
    local report=assert(io.open(OUTPUT_DIR..'/fall_roar.txt','w'))
    local passed=true
    local function check(ok,message)
        passed=passed and ok
        report:write((ok and 'PASS ' or 'FAIL ')..message..'\n')
    end
    check(request and started and started-request>=0 and started-request<=1 and enables==1,
        'one DMC start at the native shaft cue (enables '..enables..')')
    check(rate==sampleRate and address==0xD0 and length==(#sample-1)//16,
        'full-rate roar at the production sample address and length')
    check(fetches==#sample and waveformMatches,'continuous full waveform ('..fetches..' bytes fetched)')
    check(heldFallPose,'shaft roar does not request a raised head')
    check(themeBeforeFall~=0 and fallingFrames>0 and not themeDuringFall and track==0x02,
        string.format('music stops throughout the fall and the palace theme starts in the lower room (before $%02X, after $%02X, track active while falling: %s)',
            themeBeforeFall,track,tostring(themeDuringFall)))
    check(mode==0x0B and r(0x561)==0x2D and r(0x700)==lives and r(0x5EE)==0,
        'destination room resumes gameplay and releases the roar')
    report:write('RESULT '..(passed and 'PASS' or 'FAIL')..'\n');report:close()
    stopScenario(passed and 0 or 1)
end,emu.eventType.endFrame)
