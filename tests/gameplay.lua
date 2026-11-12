-- Actual controller-driven new game, attack poses, jump, and castle exit.
dofile(TEST_DIR..'/newgame.lua')
local frame=0
local mem=emu.memType.nesMemory
local function read(address) return emu.read(address,mem) end
local report=assert(io.open(OUTPUT_DIR..'/gameplay.txt','w'))
local seenStand,seenCrouch,seenJump=false,false,false
local errors=0
local captures={}
local sawWorld=false
local function check(condition,message)
    report:write((condition and 'PASS ' or 'FAIL ')..message..'\n')
    if not condition then errors=errors+1 end
end
local function input()
    local buttons=newGameInput(frame)
    if frame>=1000 then
        buttons.b=(frame>=1030 and frame<1033) or (frame>=1100 and frame<1103)
        buttons.down=(frame>=1080 and frame<1140)
        buttons.a=(frame>=1170 and frame<1190)
        buttons.right=(frame>=1250 and frame<2050 and not sawWorld)
    end
    emu.setInput(buttons,0)
end
local function tick()
    frame=frame+1
    if frame==1000 then
        check(read(0x736)==0x0B,'new game reaches side-view play')
        screenshot('barba-idle')
    end
    if frame>1000 and frame<1250 then
        local pose=read(0x80)
        if pose==5 and not seenStand then
            seenStand=true; captures[frame+2]='barba-standing-flame'
            check(read(0x225)==0x50 and read(0x224)<0xF8,'standing plume tip is rendered')
        end
        if pose==7 and not seenCrouch then
            seenCrouch=true; captures[frame+2]='barba-crouched-flame'
            check(read(0x224)==read(0x220),'crouched plume halves share a Y position')
        end
        if frame>=1170 and read(0x479)>0 then seenJump=true end
    end
    if captures[frame] then
        screenshot(captures[frame])
        if captures[frame]=='barba-overworld' then
            check(read(0x201)%2==0 and read(0x205)==read(0x201)+2,'overworld uses two adjacent dragon sprite columns')
        end
    end
    if frame>1250 and read(0x736)==5 and not sawWorld then
        sawWorld=true; captures[frame+3]='barba-overworld'
    end
    if frame%100==0 then
        report:write(string.format('frame %d mode %d world %d room %d y %d bank %s\n',
            frame,read(0x736),read(0x707),read(0x561),read(0x29),
            tostring(emu.getState()['mapper.prgReg'])))
    end
    if frame==2100 then
        check(seenStand and seenCrouch and seenJump,'standing, crouched and jumping states exercised')
        check(sawWorld,'castle exit reaches overworld')
        local state=emu.getState()
        report:write('chr0 '..tostring(state['mapper.chrMemoryOffset0'])..'\n')
        report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
        report:close(); stopScenario(errors==0 and 0 or 1)
    end
end
emu.addEventCallback(input,emu.eventType.inputPolled)
emu.addEventCallback(tick,emu.eventType.endFrame)
