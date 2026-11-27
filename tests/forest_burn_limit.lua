-- Overworld forest burns grow the WRAM RLE map ($7C00..) by up to 2 bytes each.
-- BurnMapEndGuard refuses a split once the map end reaches $7FF0, so the shift can
-- never write past $7FFF into MMC1 registers. The map end is forced by relocating
-- row $4A (pointer $6094/$6095) to a 4-byte stand-in row near the top of WRAM.
-- 1) end $7FEB: burn allowed, tile split, row $4A pointer moves +2.
-- 2) end $7FF3: burn refused, map bytes and row pointers unchanged, game keeps running.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/forest-burn-limit.txt','w'))
local errors=0
local frame=0
local worldAt=nil
local phase='find_forest'
local actionFrame=nil
local snap=nil
local guardCalls=0
local splitCalls=0

local function check(ok,msg)
    report:write((ok and 'PASS ' or 'FAIL ')..msg..'\n')
    if not ok then errors=errors+1 end
end

local function fakeRow(addr)
    for i=0,3 do w(addr+i,0xF5) end
    w(0x6094,addr&255); w(0x6095,addr>>8)
end

local function snapshot()
    local t={}
    for a=0x6000,0x6095 do t[#t+1]=r(a) end
    for a=0x7C00,0x7FFF do t[#t+1]=r(a) end
    return t
end

local function input()
    local b=newGameInput(frame)
    if frame>=1000 then
        if worldAt==nil then
            b.right=(frame>=1250 and frame<2050)
        elseif frame-worldAt<70 then
            -- Same opening steps as overworld_fire.lua (right, then face North Palace).
            local rel=frame-worldAt
            if rel>=10 and rel<30 then b.right=true
            elseif rel>=35 and rel<40 then b.left=true end
        elseif phase=='find_forest' then
            w(0x86,0); w(0x87,0); w(0x88,0); w(0x89,0)
            if r(0x0563)==6 and r(0x7D)==0 then
                fakeRow(0x7FE8)
                actionFrame=frame
                b.b=true
                phase='burn_allowed'
            else
                b.right=true
            end
        elseif phase=='step' then
            if frame>=actionFrame and frame<actionFrame+20 then b.right=true end
        elseif phase=='refuse_ready' then
            if r(0x0563)~=6 or r(0x7D)~=0 then emu.setInput(b,0) return end
            fakeRow(0x7FF0)
            guardCalls=0
            snap=snapshot()
            actionFrame=frame
            b.b=true
            phase='burn_refused'
        end
    end
    emu.setInput(b,0)
end

local function tick()
    frame=frame+1
    if frame>1250 and worldAt==nil and r(0x0736)==5 then worldAt=frame end
    if phase=='burn_allowed' and frame==actionFrame+20 then
        check(r(0x7CEB)==0x06 and r(0x7CEC)==0x04 and r(0x7CED)==0x46,
            string.format('below limit: forest split into burnt tile (7CEB=%02X %02X %02X)',
                r(0x7CEB),r(0x7CEC),r(0x7CED)))
        local p=r(0x6094)+256*r(0x6095)
        check(p==0x7FEA,string.format('below limit: row $4A pointer shifted +2 to $%04X',p))
        phase='step'
        actionFrame=frame+1
    elseif phase=='step' and frame==actionFrame+25 then
        check(r(0x0563)==6,'next tile ahead is forest for the refusal check, got '..r(0x0563))
        phase='refuse_ready'
    elseif phase=='burn_refused' and frame==actionFrame+30 then
        local now=snapshot()
        local same=true
        for i=1,#snap do if snap[i]~=now[i] then same=false break end end
        check(guardCalls==1,'at limit: guard ran for the second burn (calls='..guardCalls..')')
        check(same,'at limit: overworld map bytes and row pointers unchanged')
        check(r(0x0301)==0 and r(0x0302)==0xFF,'at limit: refused burn cancelled PPU redraw queue ($0301=0, $0302=$FF)')
        check(r(0x0736)==5,'at limit: still on the overworld (mode $0736 = '..r(0x0736)..')')
        phase='alive'
        actionFrame=frame
    elseif phase=='alive' and frame==actionFrame+60 then
        check(r(0x0736)==5,'game keeps running 60 frames after the refused burn')
        report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
        report:close()
        stopScenario(errors==0 and 0 or 1)
    end
    if frame==3500 then
        check(false,'completed forest burn limit scenario (phase='..phase..')')
        report:write('RESULT FAIL\n'); report:close(); stopScenario(1)
    end
end

emu.addMemoryCallback(function()
    local prg=emu.convertAddress(LABELS.OwSplitEntry2,mem)
    if prg and prg.address//0x4000==2 then guardCalls=guardCalls+1 end
end,emu.callbackType.exec,LABELS.OwSplitEntry2)
emu.addEventCallback(input,emu.eventType.inputPolled)
emu.addEventCallback(tick,emu.eventType.endFrame)
