-- Shared fresh-save controller sequence. No game RAM is changed here.
function newGameInput(frame)
    local start = (frame>=180 and frame<183) or (frame>=420 and frame<423)
        or (frame>=620 and frame<623) or (frame>=700 and frame<703)
    local select = (frame>=540 and frame<543) or (frame>=560 and frame<563)
        or (frame>=580 and frame<583)
    return {start=start,a=(frame>=500 and frame<503),b=false,
        select=select,up=false,down=false,left=false,right=false}
end

function screenshot(name)
    local file=assert(io.open(OUTPUT_DIR..'/'..name..'.png','wb'))
    file:write(emu.takeScreenshot()); file:close()
end

function stopScenario(code)
    local stop=emu.exit or emu.stop
    stop(code)
end

-- The side-view trail sits in the highest free DMA-shadow entries, with the
-- near torso in the lowest of them (DrawEncounterTrailSprites1). Returns the
-- shadow addresses of the visible pieces {near=,outer=,tip=,far=}, searching
-- $65FC down to $6550 so the trail wins over any earlier sprite with a matching tile.
TRAIL_TILES={near=0x15,outer=0x3F,tip=0x45,far=0x31}
function trailSlots()
    local m=emu.memType.nesMemory
    local found={}
    for slot=0x65FC,0x6550,-4 do
        if emu.read(slot,m)<0xF0 then
            local tile=emu.read(slot+1,m)
            for name,t in pairs(TRAIL_TILES) do
                if tile==t and not found[name] then found[name]=slot end
            end
        end
    end
    return found
end
