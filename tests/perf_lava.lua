-- Lava performance probe: Palace 6 lava room (same fixture as palace.lua). Barba
-- walks into the lava and stands there; reports per-frame NMI work cycles, lag
-- frames and lava-hook calls ($E0A4) while on the lava versus on solid floor.
-- python tools/emulator_test.py tests/perf_lava.lua
dofile(TEST_DIR..'/newgame.lua')
local frame=0
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/perf-lava.txt','w'))
local function cycles()return emu.getState()['cpu.cycleCount']end
local nmiStart,nmiCycles,nmis,lavaCalls=nil,0,0,0
emu.addMemoryCallback(function()nmiStart=cycles();nmis=nmis+1 end,emu.callbackType.exec,0xC07B)
emu.addMemoryCallback(function()if nmiStart then nmiCycles=nmiCycles+cycles()-nmiStart;nmiStart=nil end end,emu.callbackType.exec,0xC1B5)
emu.addMemoryCallback(function()lavaCalls=lavaCalls+1 end,emu.callbackType.exec,0xE0A4)
local st={floor={n=0,sum=0,max=0,lag=0,calls=0},lava={n=0,sum=0,max=0,lag=0,calls=0}}
emu.addEventCallback(function()
    local buttons=newGameInput(frame)
    buttons.right=(frame>=1300 and frame<1430)
    emu.setInput(buttons,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        w(0x707,4);w(0x706,2);w(0x769,4);w(0x561,0x33)
        w(0x568,5);w(0x56B,6);w(0x56C,1);w(0x701,0);w(0x75C,0);w(0x704,0)
        w(0x736,0);w(0x73D,0);w(0x726,1)
        w(0x774,255);w(0x784,8)
    end
    local p=nil
    if frame>=1200 and frame<1300 then p='floor' elseif frame>=1450 and frame<1750 then p='lava' end
    if p then
        local s=st[p]; s.n=s.n+1; s.sum=s.sum+nmiCycles; s.calls=s.calls+lavaCalls
        if nmiCycles>s.max then s.max=nmiCycles end
        if nmis==0 then s.lag=s.lag+1 end
    end
    nmiCycles,nmis,lavaCalls=0,0,0
    if frame==1750 then
        for _,k in ipairs({'floor','lava'})do
            local s=st[k]
            report:write(string.format('%s frames=%d avgNmi=%d peakNmi=%d lag=%d lavaCallsPerFrame=%.2f\n',
                k,s.n,s.n>0 and s.sum//s.n or 0,s.max,s.lag,s.n>0 and s.calls/s.n or 0))
        end
        local ok=st.lava.n>0 and st.lava.lag==0 and st.lava.max<29700
        report:write((ok and 'PASS' or 'FAIL')..' no lag and peak under 29.7k cycles while standing in lava\n')
        report:write('RESULT '..(ok and 'PASS' or 'FAIL')..'\n')
        report:close();stopScenario(ok and 0 or 1)
    end
end,emu.eventType.endFrame)
