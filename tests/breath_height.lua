-- Controller-driven breath/height regression with controlled enemy fixtures.
-- Run sequentially with other Mesen scenarios; no user play profile is touched.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local frame=0
local current=0
local errors=0
local cases={}
local report=assert(io.open(OUTPUT_DIR..'/breath-height.txt','w'))
local muzzleX,muzzleY=0x05F2,0x05F3
local hit,projectile,fireClass,aligned=false,false,false,false
local previousSlots={0,0}
local startY=nil
local jumped,landed,ducked,walked,world=false,false,false,false,false
local peak=nil
local wholeAscent,wholeDescent=false,false
local function fullBodyVisible()
    local head,body=false,false
    for _,a in ipairs({0x228,0x22C,0x230})do
        if r(a)<0xF0 then head=true end
    end
    for _,a in ipairs({0x214,0x218,0x21C})do
        if r(a)<0xF0 then body=true end
    end
    return head and body
end
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n');report:flush()
    if not ok then errors=errors+1 end
end
for _,fire in ipairs({false,true})do
    for _,full in ipairs({false,true})do
        for _,dir in ipairs({1,2})do
            for _,duck in ipairs({false,true})do
                cases[#cases+1]={fire=fire,full=full,dir=dir,duck=duck}
            end
        end
    end
end
local function caseStart(i)
    current=i
    local test=cases[i]
    hit,projectile,fireClass,aligned=false,false,false,false
    previousSlots={0,0}
    w(0x5F,test.dir);w(0x9F,test.dir);w(0x70,0);w(0x400,0)
    w(0x76F,test.fire and 0x10 or 0);w(0x774,test.full and 127 or 100);w(0x784,4)
    w(0x777,1);w(0x8D,0);w(0x8E,0);w(0x5CA,0);w(0x5CB,0)
    for address=0xB6,0xBB do w(address,0)end
    if not test.fire then
        w(0xB6,1);w(0xA1,4);w(0xC2,8);w(0xA8,0);w(0x1A,1)
        w(0x444,0);w(0x40E,0);w(0x518,0)
    end
end
local function input()
    local buttons=newGameInput(frame)
    if frame>=1000 and current>0 and current<=#cases then
        local elapsed=frame-(1000+(current-1)*80)
        buttons.down=cases[current].duck
        buttons.b=elapsed>=12 and elapsed<15
    end
    local movement=1000+#cases*80
    if frame>=movement then
        buttons={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
        buttons.a=frame>=movement+30 and frame<movement+52
        buttons.down=frame>=movement+130 and frame<movement+160
        buttons.right=frame>=movement+180 and frame<movement+1050 and not world
    end
    emu.setInput(buttons,0)
end
local function tick()
    frame=frame+1
    local movement=1000+#cases*80
    if frame==1000 then check(r(0x736)==11,'fresh game reaches playable castle')end
    if frame>=1000 and frame<movement then
        local i=math.floor((frame-1000)/80)+1
        if current~=i then caseStart(i)end
        local test=cases[current]
        local elapsed=frame-(1000+(current-1)*80)
        -- Place the test Bot relative to the current mouth, not the old sword
        -- lane. Only its position/velocity is held; normal damage code runs.
        -- The mouth mirror updates during the game frame, so for one tick after
        -- caseStart it can still describe the previous case's facing. Park the
        -- enemy away until it matches; a stale mouth would knock the dragon back.
        if not test.fire and (elapsed<2 or r(0x9F)~=test.dir) then
            w(0x4E,(r(0x4D)+0x60)%256);w(0x3C,r(0x3B));w(0x2A,0x40)
        elseif not test.fire then
            -- Overlap the visible 8x16 breath sprite that starts at the mouth:
            -- damage must agree with what the player sees.
            local dx=test.dir==1 and 4 or -4
            local screenX=math.max(0,math.min(240,r(muzzleX)+dx))
            local worldX=r(0x4D)+r(0x3B)*256+screenX-r(0xCC)
            w(0x4E,worldX%256);w(0x3C,math.floor(worldX/256)%256)
            w(0x2A,math.min(220,r(muzzleY)+4));w(0x71,0);w(0x57E,0)
            if r(0xC2)<8 or r(0x40E)>0 then hit=true end
        end
        for slot=0,1 do
            local active=r(0x8D+slot)>0 and r(0x8D+slot)<0x80
            if active then projectile=true end
            if active and previousSlots[slot+1]==0 then
                if r(0x5CA+slot)==0 then fireClass=true end
                local x=r(0x5A+slot)+r(0x48+slot)*256-r(0x72C)-r(0x72A)*256
                if math.abs(r(0x36+slot)-r(muzzleY))<=8 and math.abs(x-r(muzzleX))<=12 then aligned=true end
            end
            previousSlots[slot+1]=active and 1 or 0
        end
        if elapsed==24 then screenshot('breath-case-'..current)end
        if elapsed==65 then
            local name=string.format('Fire=%s health=%s dir=%d crouch=%s',tostring(test.fire),test.full and 'full' or 'damaged',test.dir,tostring(test.duck))
            if test.fire then
                check(projectile and fireClass,name..': emits native Fire projectile')
                check(aligned,name..': projectile begins at mouth')
            else
                check(not projectile,name..': no automatic sword beam')
                check(hit,name..': attached breath damages enemy')
            end
        end
    end
    if frame==movement then
        for a=0xB6,0xBB do w(a,0)end
        w(0x76F,0);w(0x70,0);w(0x400,0);w(0x8D,0);w(0x8E,0)
        startY=r(0x29);peak=startY
    end
    if frame>=movement+30 and frame<movement+130 then
        if r(0x479)>0 then jumped=true end
        if r(0x479)==2 and r(0x80)==6 and fullBodyVisible() then
            wholeAscent=true
        end
        if r(0x479)>0 and r(0x57D)<0x80 and fullBodyVisible() then wholeDescent=true end
        peak=math.min(peak,r(0x29))
        if jumped and r(0x479)==0 and math.abs(r(0x29)-startY)<=1 then landed=true end
        if frame==movement+48 then screenshot('breath-height-jump')end
    end
    if frame>=movement+130 and frame<movement+160 and r(0x80)==6 then ducked=true end
    if frame==movement+170 then
        check(jumped and landed and peak<startY-8,'jump rises and returns to original floor')
        check(wholeAscent and wholeDescent,'head and lower body remain visible through jump ascent and descent')
        check(ducked,'crouch state still available after attack tests')
        screenshot('breath-height-idle')
    end
    if frame>=movement+180 and r(0x70)~=0 then walked=true end
    if frame>=movement+180 and r(0x736)==5 then world=true end
    if frame==movement+1100 then
        check(walked and world,'current player clears castle side exit and reaches overworld')
        check(r(0xB5)==1,'player remains alive after movement/exit sequence')
        report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');report:close()
        stopScenario(errors==0 and 0 or 1)
    end
end
emu.addEventCallback(input,emu.eventType.inputPolled)
emu.addEventCallback(tick,emu.eventType.endFrame)
