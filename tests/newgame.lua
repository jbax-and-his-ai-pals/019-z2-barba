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
