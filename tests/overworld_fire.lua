-- Verify Overworld Dragon Chaos / Tree Burning:
-- 1) Barba breathes fire on B without needing the Hammer, drawing an animated flame sprite.
-- 2) Facing Forest ($06) scorches ONLY that single tile into Desert/Plains ($04), preserving neighboring trees.
-- 3) Facing Palace ($02) triggers flame sprite + reaction SFX.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/overworld-fire.txt','w'))
local errors=0
local frame=0
local worldAt=nil
local phase='find_palace'
local actionFrame=nil
local sawFlameOam,sawFlameTile,sawPalaceSfx=false,false,false
local sawPalaceFlameCentered,badPalaceFlameX=false,false
local sawRightFlameCentered,badRightFlameX=false,false
local leftActionFrame=nil

local function check(ok,msg)
    report:write((ok and 'PASS ' or 'FAIL ')..msg..'\n')
    if not ok then errors=errors+1 end
end

local function input()
    local b=newGameInput(frame)
    if frame>=1000 then
        if worldAt==nil then
            b.right=(frame>=1250 and frame<2050)
        elseif phase=='find_palace' then
            -- Step right once from North Palace, then face left at North Palace ($02)
            local rel=frame-worldAt
            if rel>=10 and rel<30 then b.right=true
            elseif rel>=35 and rel<40 then b.left=true
            elseif rel==45 then actionFrame=frame; b.b=true end
        elseif phase=='find_forest' then
            w(0x86,0); w(0x87,0); w(0x88,0); w(0x89,0)
            -- Walk right/up from North Palace until aligned ($7D==0) and facing Forest ($06)
            if r(0x0563)==6 and r(0x7D)==0 then
                actionFrame=frame
                b.b=true
                phase='burning_forest'
            else
                b.right=true
            end
        elseif phase=='burning_forest' then
            if actionFrame and frame==actionFrame+1 then b.b=true end
        elseif phase=='step_onto_burnt' then
            -- Step onto the burnt tile (still facing same direction) to check the next tile in the strip
            if actionFrame and frame>=actionFrame and frame<actionFrame+20 then b.right=true end
        elseif phase=='check_left_flame' then
            if leftActionFrame and frame==leftActionFrame then b.b=true end
        end
    end
    emu.setInput(b,0)
end

local function tick()
    frame=frame+1
    if frame>1250 and worldAt==nil and r(0x0736)==5 then worldAt=frame end
    if worldAt then
        if phase=='find_palace' and actionFrame then
            if r(0x6471)>0 then
                local y=r(0x02FC)
                local t=r(0x02FD)
                if y<0xF0 then
                    sawFlameOam=true
                    if r(0x02FF)==0x94 then sawPalaceFlameCentered=true else badPalaceFlameX=true end
                end
                if t==0x60 or t==0x62 then sawFlameTile=true end
            end
            if r(0xEC)==4 or (r(0xED)&0x40)~=0 then sawPalaceSfx=true end
            if frame==actionFrame+20 then
                check(sawFlameOam,'overworld B draws flame sprite in OAM $02FC')
                check(sawFlameTile,'overworld flame uses custom CHR tiles $60/$62')
                check(sawPalaceFlameCentered and not badPalaceFlameX,'right-facing overworld flame X is centered at $94')
                check(sawPalaceSfx,'breathing fire on Palace triggers reaction SFX')
                phase='find_forest'
                actionFrame=nil
            end
        elseif phase=='burning_forest' and actionFrame then
            if r(0x6471)>0 and r(0x02FC)<0xF0 then
                if r(0x02FF)==0x94 then sawRightFlameCentered=true else badRightFlameX=true end
            end
            if frame==actionFrame+6 then screenshot('ow-tree-burn') end
            if frame==actionFrame+20 then
                check(sawRightFlameCentered and not badRightFlameX,'overworld forest burn flame X is centered on tile ($94)')
                check(r(0x078B)==0,'Barba has no Hammer ($078B==0)')
                check(r(0x7CEB)==0x04 and r(0x7CEC)==0x56,
                    string.format('RLE split into single burnt facing tile (7CEB=%02X %02X %02X)',
                        r(0x7CEB),r(0x7CEC),r(0x7CED)))
                phase='step_onto_burnt'
                actionFrame=frame+1
            end
        elseif phase=='step_onto_burnt' and actionFrame then
            if frame==actionFrame+25 then
                local nextTerrain=r(0x0563)
                check(nextTerrain==6,'neighboring tree in horizontal strip remains Forest ($06), got '..nextTerrain)
                phase='check_left_flame'
                leftActionFrame=nil
            end
        elseif phase=='check_left_flame' then
            if leftActionFrame==nil and r(0x0736)==5 and r(0x7D)==0 then
                w(0x0562,2)
                leftActionFrame=frame
            elseif leftActionFrame and frame==leftActionFrame+3 then
                local ok=r(0x6471)>0 and r(0x02FC)<0xF0 and r(0x02FF)==0x74
                check(ok,string.format('left-facing overworld flame X is centered at $74 (timer=%d y=%02X x=%02X)',
                    r(0x6471),r(0x02FC),r(0x02FF)))
                report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
                report:close()
                stopScenario(errors==0 and 0 or 1)
            end
        end
    end
    if frame==3000 then
        check(false,'completed overworld fire scenario (phase='..phase..', terrain='..r(0x0563)..')')
        report:write('RESULT FAIL\n'); report:close(); stopScenario(1)
    end
end

emu.addEventCallback(input,emu.eventType.inputPolled)
emu.addEventCallback(tick,emu.eventType.endFrame)
