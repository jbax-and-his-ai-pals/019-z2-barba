-- Pick up the native Candle with controller input from the human checkpoint.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local report=assert(io.open(OUTPUT_DIR..'/item-roar.txt','w'))
local frame,age,failures,starts=0,0,0,0
local loaded,released,moved=false,false,false
local overlap,completionLatch=false,false
local heldX
local holdFrames,poseFrames,sampleStarts=0,0,0
local stationary,itemHigh,standingTorso,roaringTorso,actionsLocked=true,true,true,true,true
local drained=false
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n')
    if not ok then failures=failures+1 end
end

emu.addMemoryCallback(function()
    if loaded or frame<120 then return end
    local build=assert(io.open(OUTPUT_DIR..'/build-report.json','r'))
    local hash=assert(build:read('*a'):match('"output_sha256"%s*:%s*"([a-f0-9]+)"'))
    build:close()
    local state=assert(io.open(OUTPUT_DIR..'/test-pack/'..hash:sub(1,12)..'/items/candle-pickup.mss','rb'))
    assert(emu.loadSavestate(state:read('*a')))
    state:close()
    loaded=true
    check(r(0x561)==8 and r(0x785)==0,'checkpoint starts beside the uncollected Candle')
end,emu.callbackType.exec,0xC07B)
emu.addEventCallback(function()
    local pickedUp=loaded and r(0x785)==1
    local challenge=r(0x64D4)~=0 and age%20<5
    emu.setInput({left=loaded and not pickedUp,right=pickedUp,
        a=challenge,b=challenge,start=challenge,select=challenge},0)
end,emu.eventType.inputPolled)
emu.addMemoryCallback(function(_,value)
    if loaded and value==0x8A then
        starts=starts+1
        overlap=overlap or r(0x7FB)&0x10~=0
    end
end,emu.callbackType.write,0x5EE)
emu.addMemoryCallback(function(_,value)
    if loaded and r(0x5EE)==0x8A and value==136 then sampleStarts=sampleStarts+1 end
end,emu.callbackType.write,0x4013)
emu.addEventCallback(function()
    frame=frame+1
    if not loaded then return end
    age=age+1
    local roar=r(0x5EE)
    local hold=r(0x64D4)
    local x=r(0x3B)*256+r(0x4D)
    completionLatch=completionLatch or roar==0x10
    if hold~=0 then
        heldX=heldX or x
        stationary=stationary and x==heldX
        actionsLocked=actionsLocked and r(0x524)==0 and r(0x773)==127 and r(0x70)==0
        itemHigh=itemHigh and r(0x235)==0x8C and r(0x234)+16==r(0x204)
        local top=r(0x5F4)
        if hold==1 and r(0x7FB)==0x10 and r(0x5FA)==27 then
            standingTorso=standingTorso and r(0x204)==top and r(0x20C)==top+16
                and r(0x218)==top+32 and r(0x220)==0xF8 and r(0x224)==0xF8
            holdFrames=holdFrames+1
            if holdFrames==10 then screenshot('item-roar-holding') end
        elseif (roar==0x8A or roar==0x9A) and r(0x5FA)==72 then
            roaringTorso=roaringTorso and r(0x204)==top-8 and r(0x20C)==top+8
                and r(0x218)==top+24 and r(0x220)==top+32 and r(0x224)==top+32
            poseFrames=poseFrames+1
            if poseFrames==10 then screenshot('item-roar-candle') end
        end
        drained=drained or roar==0x9A
    elseif drained and roar==0 and r(0x5FA)~=72 and r(0x240)==0xF8 then
        released=true
        moved=moved or x~=heldX
    end
    if age==330 then
        check(r(0x785)==1 and holdFrames>112,'Candle enters inventory and stays raised through the native pickup fanfare')
        check(starts==1 and sampleStarts==1 and not overlap,'one full sampled roar starts after the fanfare')
        check(poseFrames>90 and drained and released,'Barba holds the tilt through the buffered tail and then lowers the item')
        check(itemHigh,'Candle stays above the head in both poses')
        check(standingTorso,'standing uses its two torso chunks without a partial third chunk')
        check(roaringTorso,'raised head uses the gem overlap to complete the second torso chunk')
        check(stationary and actionsLocked and moved,'movement and actions stay locked until the ceremony ends')
        check(not completionLatch,'pickup leaves no completed palace ceremony state')
        report:write('RESULT '..(failures==0 and 'PASS' or 'FAIL')..'\n')
        report:close()
        stopScenario(failures==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
