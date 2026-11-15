-- Overworld side-facing dragon: walk right then left after the castle exit and
-- capture both walk frames per direction. Right uses tiles 0/4, left 8/12.
dofile(TEST_DIR..'/newgame.lua')
local frame=0
local mem=emu.memType.nesMemory
local function read(address) return emu.read(address,mem) end
local report=assert(io.open(OUTPUT_DIR..'/overworld-side.txt','w'))
local errors=0
local worldAt=nil
local seen={}
local function check(condition,message)
    report:write((condition and 'PASS ' or 'FAIL ')..message..'\n')
    if not condition then errors=errors+1 end
end
local function input()
    local buttons=newGameInput(frame)
    if frame>=1000 then
        buttons.right=(worldAt==nil and frame>=1250 and frame<2050) or (worldAt~=nil and frame>=worldAt+20 and frame<worldAt+60)
        buttons.left=(worldAt~=nil and frame>=worldAt+80 and frame<worldAt+120)
    end
    emu.setInput(buttons,0)
end
local function tick()
    frame=frame+1
    if frame>1250 and worldAt==nil and read(0x736)==5 then worldAt=frame end
    if worldAt then
        local t=read(0x201)
        local rel=frame-worldAt
        if rel>=30 and rel<60 then seen['r'..t]=true; if not seen.rshot and t==0 then seen.rshot=true; screenshot('ow-right-0') end; if not seen.rshot4 and t==4 then seen.rshot4=true; screenshot('ow-right-1') end end
        if rel>=90 and rel<120 then seen['l'..t]=true; if not seen.lshot and t==8 then seen.lshot=true; screenshot('ow-left-0') end; if not seen.lshot12 and t==12 then seen.lshot12=true; screenshot('ow-left-1') end end
        if rel==130 then
            check(seen.r0 and seen.r4,'right-facing walk uses side tiles 0 and 4')
            check(seen.l8 and seen.l12,'left-facing walk uses mirrored side tiles 8 and 12')
            report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
            report:close(); stopScenario(errors==0 and 0 or 1)
        end
    end
    if frame==2400 then check(false,'reached overworld'); report:write('RESULT FAIL\n'); report:close(); stopScenario(1) end
end
emu.addEventCallback(input,emu.eventType.inputPolled)
emu.addEventCallback(tick,emu.eventType.endFrame)
