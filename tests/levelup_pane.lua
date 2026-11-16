-- Level-up pane: the attack row reads BREATH and draws the fireball icon.
-- New game, then grant enough experience for a level-up and capture the pane.
dofile(TEST_DIR..'/newgame.lua')
local frame=0
local mem=emu.memType.nesMemory
local ppu=emu.memType.nesPpuMemory
local function r(a) return emu.read(a,mem) end
local function w(a,v) emu.write(a,v,mem) end
local report=assert(io.open(OUTPUT_DIR..'/levelup_pane.txt','w'))
local errors=0
local opened
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n')
    if not ok then errors=errors+1 end
end
local function finish()
    report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
    report:close(); stopScenario(errors==0 and 0 or 1)
end
local function contains(seq)
    for nt=0x2000,0x27FF-#seq do
        local hit=true
        for i,v in ipairs(seq) do if emu.read(nt+i-1,ppu)~=v then hit=false;break end end
        if hit then return nt end
    end
end
emu.addEventCallback(function() emu.setInput(newGameInput(frame),0) end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        check(r(0x736)==0x0B,'new game reaches side-view play')
        -- Attack level 2, one level-up's worth of experience banked.
        w(0x777,2); w(0x775,0x27); w(0x776,0x0F)
    end
    if frame>1000 and not opened and r(0x74C)==1 then opened=frame end
    if opened and frame==opened+90 then
        check(true,'level-up pane opened')
        local breath=contains({0xDB,0xEB,0xDE,0xDA,0xED,0xE1})
        check(breath~=nil,'pane shows BREATH')
        check(contains({0xDA,0xED,0xED,0xDA,0xDC,0xE4})==nil,'pane no longer shows ATTACK')
        check(contains({0xC9,0xC9})~=nil,'attack row draws the level-2 icon pair')
        screenshot('levelup-pane')
        finish()
    end
    if frame==2400 then check(false,'level-up pane opened'); finish() end
end,emu.eventType.endFrame)
