-- Requires a current Edge Scenarios pack. Observe actual GAME OVER DMC writes.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local frame, loaded, loadFrame, sawScreen = 0, false, 0, false
local starts, lengths, addresses, rates = {}, {}, {}, {}
local requestFrame=nil
local file=assert(io.open(OUTPUT_DIR..'/build-report.json','r'))
local buildReport=file:read('*a');file:close()
local digest=buildReport:match('"output_sha256"%s*:%s*"(%x+)"')
local compact=buildReport:find('"game_over_shared_laugh"',1,true)~=nil
local statePath=OUTPUT_DIR..'/test-pack/'..digest:sub(1,12)..'/edges/game-over-danger.mss'
emu.addMemoryCallback(function(addr,value)
    if loaded and value==2 and requestFrame==nil then requestFrame=frame end
end,emu.callbackType.write,0xE9)
emu.addMemoryCallback(function()
    if loaded then sawScreen=true end
end,emu.callbackType.exec,0xCA72)
emu.addMemoryCallback(function(addr,value)
    if not loaded or r(0x07FA)~=2 then return end
    if addr==0x4012 then addresses[#addresses+1]=value end
    if addr==0x4010 then rates[#rates+1]=value end
    if addr==0x4013 then
        starts[#starts+1]=frame;lengths[#lengths+1]=value
    end
end,emu.callbackType.write,0x4010,0x4013)
emu.addMemoryCallback(function()
    if frame>=120 and not loaded then
        local f=assert(io.open(statePath,'rb'));local state=f:read('*a');f:close()
        assert(emu.loadSavestate(state),'Cannot load danger state')
        loaded=true;loadFrame=frame
    end
end,emu.callbackType.exec,0xC07B)
emu.addEventCallback(function()emu.setInput({},0)end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if loaded and frame-loadFrame==600 then
        local report=assert(io.open(OUTPUT_DIR..'/game_over_audio.txt','w'))
        local errors=0
        local function check(ok,msg)
            report:write((ok and 'PASS ' or 'FAIL ')..msg..'\n')
            if not ok then errors=errors+1 end
        end
        check(sawScreen,'natural death reaches native GAME OVER')
        check(#starts==5,'exactly five laughs ('..#starts..')')
        if compact then
            report:write('INFO initial request frame='..tostring(requestFrame)..'\n')
            -- Native requests reach the audio driver one frame later; add 36.
            check(requestFrame~=nil and starts[1]~=nil and starts[1]-requestFrame==37,
                'initial laugh adds 36 frames after the native one-frame handoff')
        end
        for i=1,#starts do report:write(string.format('INFO %d frame=%d address=%02X length=%02X\n',i,starts[i],addresses[i],lengths[i])) end
        local expectedAddress={0xD0,0xDC,0xE1,0xE7,0xEA}
        local expectedLength={14,10,12,8,8}
        if compact then
            expectedAddress={0xF2,0xF2,0xF3,0xF4,0xF5}
            expectedLength={4,3,3,3,3}
        end
        local expectedRate=compact and {6,6,6,10,10} or {15,15,15,15,15}
        for i=1,5 do
            check(addresses[i]==expectedAddress[i] and lengths[i]==expectedLength[i],
                'laugh '..i..' uses its octave-up sample and shortened length')
            check(rates[i]==expectedRate[i],'laugh '..i..' follows the original descending contour one octave up')
            if i>1 then
                check(starts[i]~=nil and starts[i-1]~=nil and starts[i]-starts[i-1]==23,
                    'laugh '..i..' preserves native 23-frame spacing')
            end
        end
        report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');report:close()
        stopScenario(errors==0 and 0 or 1)
    end
    if frame>2000 then error('game-over audio scenario timed out') end
end,emu.eventType.endFrame)
