-- Controlled CPU harness for raised-head clearance and extra OAM ownership.
-- Execute the real bank-4 solid predicate through TerrainBatch. Tile $42
-- is empty and $4C is solid in this area's native false-wall table.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local frame=0
local ready=false
local current=0
local failures=0
local running=false
local tests={}
local report=assert(io.open(OUTPUT_DIR..'/tall-geometry.txt','w'))
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n');report:flush()
    if not ok then failures=failures+1 end
end
local function add(name,entry,setup,verify)
    tests[#tests+1]={name=name,entry=entry,setup=setup,verify=verify}
end
local function baseline()
    w(0x2000,0) -- controlled CPU calls must not be interrupted by gameplay NMI
    for address=0x6000,0x633F do w(address,0x42)end
    for address=0x200,0x23F,4 do w(address,0xF8)end
    w(0x769,4);w(0x707,4);w(0x13,0);w(0x80,3);w(0x17,1)
    w(0xCC,0x50);w(0x4D,0x48);w(0x3B,0);w(0x29,0x90);w(0x9F,1)
    w(0x72A,0);w(0x72C,0);w(0xC8,0);w(0x48D,0);w(0x50C,0)
    w(0x70E,0);w(0x752,0);w(0x479,0);w(0x5F6,0)
    w(0x754,0);w(0x400,0);w(0x12,0)
    w(0x5EE,0)
    for address=0xB6,0xBB do w(address,0)end
end
local function geometry(name,setup,x,y,flags)
    add(name,'BarbaGeometry',setup,function()
        check(r(0x5F6)==flags,'geometry flags '..r(0x5F6)..' expected '..flags)
        if x then check(r(0x5F2)==x and r(0x5F3)==y,
            string.format('mouth %02X,%02X expected %02X,%02X',r(0x5F2),r(0x5F3),x,y))end
        local state=emu.getState()
        check(state['cpu.x']==7 and state['cpu.y']==9,'geometry preserves caller X and Y')
        local prg=emu.convertAddress(0x8506,mem)
        check(prg and prg.address//0x4000==0,'terrain probe restores player PRG bank')
    end)
end
geometry('standing right in open space',function()end,0x6C,0x84,1)
geometry('standing left in open space',function()w(0x9F,2)end,0x4C,0x84,1)
geometry('crouch keeps native low lane',function()w(0x17,0);w(0x80,6)end,0x6C,0x9A,1)
geometry('elevator folds mouth even with standing shield',function()w(0x754,0x10)end,0x6C,0x9A,1)
geometry('airborne low shield retains full-body mouth',function()
    w(0x17,0);w(0x80,6);w(0x479,2)
end,0x6C,0x84,1)
geometry('left head edge under actual solid tile',function()w(0x6064,0x4C)end,0x6C,0x94,3)
geometry('right head edge under actual solid tile',function()w(0x6066,0x4C)end,0x6C,0x94,3)
geometry('head bottom edge catches stone below its top row',function()
    w(0x29,0x88);w(0x6064,0x4C)
end,0x6C,0x8C,3)
geometry('head bottom-right edge catches stone below its top row',function()
    w(0x29,0x88);w(0x6066,0x4C)
end,0x6C,0x8C,3)
geometry('stale ZP $07 solid value does not tuck head in open space',function()
    w(0x07,0x4C)
end,0x6C,0x84,1)
geometry('right probe crosses a world-page boundary',function()
    w(0x4D,0xF0);w(0x6130,0x4C)
end,0x6C,0x94,3)
geometry('near top of screen tucks head safely',function()w(0x29,0x20)end,0x6C,0x24,3)
geometry('right screen edge invalidates wrapped muzzle',function()w(0xCC,0xF0)end,nil,nil,0)
geometry('left screen edge invalidates wrapped muzzle',function()w(0xCC,2);w(0x9F,2)end,nil,nil,0)
geometry('Fairy excludes tall geometry',function()w(0x13,8)end,nil,nil,0)
geometry('item pose excludes tall geometry',function()w(0x80,0x0C)end,nil,nil,0)
geometry('swamp water submerges grounded Barba',function()w(0x752,0x20)end,0x6C,0x94,5)
geometry('airborne over swamp water stays full height',function()w(0x752,0x20);w(0x479,2)end,0x6C,0x84,1)

local extraHead={0x204,0x24C,0x2C4}
if LABELS.RoarAudio then
    add('gem victory looking up','BarbaDisplay',function()w(0x5EE,0x88)end,function()
        check(r(0x5FA)==72,'active gem roar draws looking-up frame 8 while grounded')
    end)
    add('pending gem keeps normal pose','BarbaDisplay',function()w(0x5EE,0x48)end,function()
        check(r(0x5FA)==27,'pending gem request keeps native idle pose')
    end)
    add('spell roar keeps normal pose','BarbaDisplay',function()w(0x5EE,0x80)end,function()
        check(r(0x5FA)==27,'spell roar does not force gem victory pose')
    end)
end
local function allHidden(addresses)
    for _,address in ipairs(addresses)do if r(address)~=0xF8 then return false end end
    return true
end
add('open-space idle displays raised head row','BarbaDisplay',function()end,function()
    local visible=0
    for _,address in ipairs(extraHead)do if r(address)==0x80 then visible=visible+1 end end
    check(visible>=2,'raised head uses extra OAM row at actor Y minus 16')
end)
add('ceiling tuck moves head down and hides middle row','BarbaDisplay',function()
    w(0x6064,0x4C)
end,function()
    local moved=0
    for _,address in ipairs(extraHead)do if r(address)==0x90 then moved=moved+1 end end
    check(moved>=2,'tucked head remains within native actor height')
    check(allHidden({0x208,0x20C,0x210}),'middle neck row is hidden while tucked')
end)
add('crouching does not leave a raised head ghost','BarbaDisplay',function()
    w(0x17,0);w(0x80,6)
end,function()check(allHidden(extraHead),'crouch hides all extra head sprites')end)
for _,case in ipairs({
    {name='open crouch facing right',pose=6,facing=1},
    {name='open crouch attack facing left',pose=7,facing=2},
    {name='corridor crouch facing right',pose=6,facing=1,ceiling=0x6064},
    {name='corridor crouch attack facing left',pose=7,facing=2,ceiling=0x6066},
})do
    add(case.name,'BarbaDisplay',function()
        w(0x17,0);w(0x80,case.pose);w(0x9F,case.facing)
        if case.ceiling then w(case.ceiling,0x4C)end
    end,function()
        local back=case.facing==1 and 0x214 or 0x21C
        local front=case.facing==1 and 0x21C or 0x214
        local head=case.pose==6 and {0x00,0x02,0x04} or {0x1E,0x20,0x04}
        for col=0,2 do
            local oam=0x208+4*col
            local tile=case.facing==1 and head[3-col] or head[1+col]
            check(r(oam)==0x98 and r(oam+1)==tile,
                'full head column '..col..' draws at crouch height')
        end
        check(r(0x219)==0x32 and r(back+1)==0x54 and r(front)==0xF8,
            'only the two cropped elbow columns draw below the head')
        check(r(0x218)==0xA8 and r(back)==0xA8 and
            (r(back+2)&0x40)==(case.facing==1 and 0x40 or 0),
            'cropped elbow starts 16px below the head and keeps facing')
        check(r(0x5F3)==0x9A and r(0x5F6)==1,'crouch keeps its fire origin')
    end)
end
for _,attack in ipairs({0,2})do
    add('elevator duck attack='..attack,'BarbaDisplay',function()
        w(0x754,0x10);w(0x400,attack)
    end,function()
        check(allHidden(extraHead),'elevator hides raised head')
        check(r(0x5FA)==(attack==0 and 54 or 63),'elevator selects compact idle/attack art')
        check(r(0x5F3)==0x9A,'elevator fire origin follows compact head')
        check(r(0x80)==3 and r(0x17)==1 and r(0x754)==0x10,'elevator pose leaves native control state intact')
    end)
end
for _,case in ipairs({
    {name='standing',pose=3,air=0,hurt=0},
    {name='upstab',pose=8,air=2,hurt=0},
    {name='downstab',pose=9,air=1,hurt=0},
    {name='hit during upstab',pose=8,air=2,hurt=0x32},
    {name='hit during downstab',pose=9,air=1,hurt=0x32},
})do
    add('busy odd frame: '..case.name,'BarbaDisplay',function()
        w(0x12,1);w(0x80,case.pose);w(0x479,case.air)
        w(0x796,0x14);w(0x57D,case.air==2 and 0xFC or 2);w(0x50C,case.hurt)
        for address=0xB6,0xBB do w(address,1)end
        -- A complete native enemy record, including a different palette.
        for offset=0,23 do w(0x2C8+offset,0x80+offset)end
    end,function()
        local intact=true
        for offset=0,23 do if r(0x2C8+offset)~=0x80+offset then intact=false end end
        check(intact,'player rendering preserves all six enemy sprites on busy odd frames')
        check(r(0x218)==0xA0,'lower body stays in player OAM')
        local palette=(case.hurt>>1)&3
        local matches=true
        for _,sprite in ipairs({0x204,0x208,0x20C,0x210,0x214,0x218,0x21C,0x220,0x224,0x24C,0x2C4})do
            if r(sprite)<0xEF and (r(sprite+2)&3)~=palette then matches=false end
        end
        check(matches,'all visible player pieces use the same expected palette')
    end)
end
for _,facing in ipairs({1,2})do
    add('ascent displays full body facing '..facing,'BarbaDisplay',function()
        w(0x80,6);w(0x479,2);w(0x9F,facing)
    end,function()
        check(not allHidden(extraHead),'ascent retains the raised head')
        check(not allHidden({0x208,0x20C,0x210}),'ascent retains the middle body')
        check(not allHidden({0x214,0x218,0x21C}),'ascent retains the lower body')
        check(r(0x80)==6 and r(0x479)==2,'visual jump does not change native physics state')
    end)
end
add('airborne low attack retains full body','BarbaDisplay',function()
    w(0x80,7);w(0x17,0);w(0x479,2)
end,function()
    check(not allHidden(extraHead),'airborne low attack retains raised jaws')
    check(not allHidden({0x214,0x218,0x21C}),'airborne attack retains the lower body')
end)
add('Fairy does not leave extra head sprites','BarbaDisplay',function()
    w(0x13,8)
end,function()check(allHidden(extraHead),'Fairy owns no extra tall-head OAM')end)
add('item hold does not leave extra head sprites','BarbaDisplay',function()
    w(0x80,0x0C);w(0x49D,0)
end,function()check(allHidden(extraHead),'item hold owns no extra tall-head OAM')end)
add('downstab right draws second torso chunk above row 0','BarbaDisplay',function()
    w(0x80,9);w(0x479,2);w(0x9F,1)
end,function()
    check(r(0x220)==0x70 and r(0x224)==0x70,'downstab right places extra torso at DRAW_TOP-16')
    check(r(0x221)==0x06 and r(0x225)==0x08 and r(0x205)==0x06 and r(0x24D)==0x08,
        'downstab right reverses tile columns in both torso chunks')
    check(r(0x223)==0x4C and r(0x227)==0x54,'downstab right aligns X to columns 0 and 8')
    check(r(0x204)==0x80 and r(0x24C)==0x80,'downstab right keeps row 0 torso below it')
    check(r(0x206)==0x80 and r(0x24E)==0x80 and r(0x222)==0x80 and r(0x226)==0x80,
        'downstab right flips both torso chunks horizontally and vertically')
    check(r(0x20A)==0x40 and r(0x216)==0x40,'downstab right keeps turned head attributes')
end)
add('downstab left draws second torso chunk above row 0','BarbaDisplay',function()
    w(0x80,9);w(0x479,2);w(0x9F,2)
end,function()
    check(r(0x220)==0x70 and r(0x224)==0x70,'downstab left places extra torso at DRAW_TOP-16')
    check(r(0x221)==0x08 and r(0x225)==0x06 and r(0x24D)==0x08 and r(0x2C5)==0x06,
        'downstab left reverses tile columns in both torso chunks')
    check(r(0x223)==0x54 and r(0x227)==0x5C,'downstab left aligns X to columns 8 and 16')
    check(r(0x24E)==0xC0 and r(0x2C6)==0xC0 and r(0x222)==0xC0 and r(0x226)==0xC0,
        'downstab left flips both torso chunks horizontally and vertically')
end)
add('downstab near HUD hides second torso chunk','BarbaDisplay',function()
    w(0x80,9);w(0x479,2);w(0x29,0x30)
end,function()
    check(allHidden({0x220,0x224}),'downstab does not draw extra torso into the HUD')
end)
add('downstab under ceiling tuck hides second torso chunk and draws full downward head','BarbaDisplay',function()
    w(0x80,9);w(0x479,2);w(0x6064,0x4C)
end,function()
    check(allHidden({0x220,0x224}),'tucked downstab hides extra torso chunk')
    check(r(0x204)==0x90 and r(0x24C)==0x90 and r(0x2C4)==0x90,'tucked downstab places upper head row at DRAW_TOP+16')
    check(r(0x205)==0x56 and r(0x24D)==0x4C and r(0x2C5)==0x4A,'tucked downstab draws full 24x32 downward head')
end)
add('downstab near right edge hides wrapped torso sprite','BarbaDisplay',function()
    w(0x80,9);w(0x479,2);w(0x9F,1);w(0x4D,0xF4)
end,function()
    check(r(0x220)==0x70 and r(0x224)==0xF8,'downstab clips offscreen right half of extra torso')
end)
add('downstab collapses all extra chunks when ceiling blocks Y1','BarbaDisplay',function()
    w(0x80,9);w(0x479,2);w(0x6054,0x4C)
end,function()
    check(r(0x64FE)==0 and allHidden({0x220,0x224}),'ceiling at Y1 keeps only Row 0..2 below roof')
end)
add('downstab collapses torso chunks into wagging tip when ceiling blocks Y2','BarbaDisplay',function()
    w(0x80,9);w(0x479,2);w(0x6044,0x4C)
end,function()
    check(r(0x64FE)==1,'ceiling at Y2 sets DOWNSTAB_ROWS=1')
    check(r(0x220)==0x70 and r(0x221)==0x0A and r(0x224)==0xF8,'ceiling at Y2 places wagging tip at Y1')
end)
add('downstab collapses third torso chunk when ceiling blocks Y3','BarbaDisplay',function()
    w(0x80,9);w(0x479,2);w(0x6034,0x4C)
end,function()
    check(r(0x64FE)==2,'ceiling at Y3 sets DOWNSTAB_ROWS=2')
    check(r(0x220)==0x70 and r(0x224)==0x70,'ceiling at Y3 keeps second torso chunk at Y1')
end)
add('swamp water shifts head down and hides bottom row','BarbaDisplay',function()
    w(0x752,0x20)
end,function()
    check(r(0x204)==0x90 and r(0x24C)==0x90,'swamp shifts head row down to actor Y')
    check(r(0x208)==0xA0 and r(0x20C)==0xA0,'swamp shifts torso row down 16px')
    check(allHidden({0x214,0x218,0x21C}),'swamp hides bottom row')
end)

-- The trail takes the highest free shadow entries, one per visible piece, near
-- torso lowest (first priority). trailSlots() (newgame.lua) finds the pieces.
local function encounterTorso(keepHistory)
    w(0x6518,0xA0);w(0x6519,0x0D);w(0x651A,0x40);w(0x651B,0x54)
    w(0x5FA,3*9)
    for slot=0x6550,0x65FC,4 do w(slot,0xF8)end
    if not keepHistory then w(0x6487,0)end
end
local function enemy(slot,y)
    w(slot,y);w(slot+1,0xB5);w(slot+2,0x01);w(slot+3,0x40)
end
local function isEnemy(slot,y)
    return r(slot)==y and r(slot+1)==0xB5 and r(slot+2)==0x01 and r(slot+3)==0x40
end
local function checkTrail(y,x,attr)
    local s=trailSlots()
    local near,outer=s.near,s.outer
    local facesRight=attr&0x40~=0
    check(near and outer and r(near)==y and r(outer)==y,'both trail sprites have the expected Y')
    check(near and outer and near<outer and r(near+3)==x+(facesRight and 8 or 0)
        and r(outer+3)==x+(facesRight and 0 or 8),'the column nearest Barba has first priority in either facing')
    check(near and outer and r(near+1)==0x15 and r(outer+1)==0x3F,'the rotated torso uses its near column before its outer column')
    check(near and outer and r(near+2)==attr and r(outer+2)==attr,'trail inherits Barba palette and draws in front of the background')
end
local function checkTip(y,x,attr)
    local s=trailSlots()
    local farX=x+((attr&0x40~=0) and -8 or 8)
    check(s.tip and r(s.tip)==y and r(s.tip+2)==attr and r(s.tip+3)==x,
        'the near tip column follows the torso')
    check(s.far and r(s.far)==y and r(s.far+2)==attr and r(s.far+3)==farX,
        'the far tip column follows, 8px further out')
    check(s.near and s.tip and s.far and s.near<s.tip and s.tip<s.far,'the tips sit behind the torso')
end
local function noTrail(names)
    local s=trailSlots()
    for _,name in ipairs(names) do if s[name] then return false end end
    return true
end
add('right-facing encounter trail at rest','DrawEncounterTorso',encounterTorso,function()
    checkTrail(0xA0,0x3C,0x40)
    checkTip(0xA0,0x34,0x40)
    check(r(0x6519)==0x35 and r(0x6515)==0x37,'the bend uses the center and rear body slots facing right')
    check(r(0x651C)==0xF8,'the old front seam does not use a third lower-row sprite')
    local prg=emu.convertAddress(0x8506,mem)
    check(prg and prg.address//0x4000==6,'the bank-6 encounter trail swap leaves player return in PRG bank 6')
end)
add('the bend mirrors onto the rear slot during a jump','DrawEncounterTorso',function()
    encounterTorso();w(0x651A,1);w(0x5FA,12*9);w(0x6515,0x0B)
end,function()
    check(r(0x6519)==0x35 and r(0x651D)==0x37 and r(0x6514)==0xF8,
        'the bend mirrors into two body slots facing left and hides the old seam')
end)
add('the bend applies during the hurt pose','DrawEncounterTorso',function()
    encounterTorso();w(0x651A,1);w(0x5FA,10*9);w(0x6515,0x0B)
end,function()
    check(r(0x6519)==0x35 and r(0x651D)==0x37 and r(0x6514)==0xF8,
        'hurt pose replaces the straight torso with the curved junction tiles')
end)
add('downstab suppresses the horizontal encounter trail','DrawEncounterTorso',function()
    encounterTorso();w(0x5FA,9*9);w(0x6519,0x5B);w(0x6515,0x5D)
end,function()
    check(r(0x6519)==0x5B and r(0x6515)==0x5D,'the downstab body tiles are intact')
    check(noTrail({'near','outer','tip','far'}),'downstab does not sprout a horizontal tail from the downward head')
    check(r(0x6487)==0,'downstab resets the encounter trail history index')
end)
add('encounter trail stays visible over grass','DrawEncounterTorso',function()
    encounterTorso();w(0x651A,0x62)
end,function()
    checkTrail(0xA0,0x3C,0x42)
end)
add('corridor crouch lifts both horizontal pieces above the floor','DrawEncounterTorso',function()
    encounterTorso()
    w(0x6518,0xA8);w(0x6519,0x33);w(0x5FA,6*9)
    for address=0x6481,0x6486 do w(address,0xB0)end
    w(0x6487,1)
end,function()
    checkTrail(0x9F,0x3C,0x40)
    checkTip(0x9F,0x34,0x40)
    check(r(0x6518)==0xA8 and r(0x6519)==0x33,'the crouch bend stays below the full head')
end)
local jumpY={0xA0,0x9C,0x98,0x94,0x98,0x9C,0xA0,0xA4,0xA0,0xA0,0xA0,0xA0,0xA0,0xA0}
for frame,y in ipairs(jumpY)do
    add('encounter trail bounce sample '..frame,'DrawEncounterTorso',function()
        encounterTorso(frame>1);w(0x6518,y);w(0x651A,1)
    end,function()
        checkTrail(jumpY[math.max(1,frame-3)],0x64,0x01)
        checkTip(jumpY[math.max(1,frame-6)],0x74,0x01)
    end)
end
local walkPose={0,1,1,2,2,0,0,1,1,2,2,0,0}
local walkY={[0]=0xA0,[1]=0x9E,[2]=0xA2}
for frame,pose in ipairs(walkPose)do
    add('encounter trail walk sway sample '..frame,'DrawEncounterTorso',function()
        encounterTorso(frame>1);w(0x80,pose)
    end,function()
        checkTrail(walkY[walkPose[math.max(1,frame-3)]],0x3C,0x40)
        checkTip(walkY[walkPose[math.max(1,frame-6)]],0x34,0x40)
    end)
end
add('encounter trail snaps to a teleported lower body','DrawEncounterTorso',function()
    encounterTorso(true);w(0x6518,0x55)
end,function()
    checkTrail(0x55,0x3C,0x40)
    checkTip(0x55,0x34,0x40)
end)
add('enemies keep their entries and outrank the trail','DrawEncounterTorso',function()
    encounterTorso();enemy(0x6550,0xA2);enemy(0x6554,0xA4)
end,function()
    checkTrail(0xA0,0x3C,0x40)
    checkTip(0xA0,0x34,0x40)
    check(isEnemy(0x6550,0xA2) and isEnemy(0x6554,0xA4),'the enemy sprites stay ahead of the trail')
end)
add('the trail skips occupied HUD entries','DrawEncounterTorso',function()
    encounterTorso();w(0x65F8,0x0F);w(0x65F9,0x71);w(0x65FC,0x0F);w(0x65FD,0x6F);enemy(0x65F4,0xA2)
end,function()
    local s=trailSlots()
    check(s.near==0x65E4 and s.outer==0x65E8 and s.tip==0x65EC and s.far==0x65F0,
        'the trail takes the four highest free entries below the HUD and enemy')
    check(isEnemy(0x65F4,0xA2),'the enemy entry is intact')
    check(r(0x65F8)==0x0F and r(0x65FC)==0x0F,'the HUD entries are intact')
end)
add('the tips give way first when entries run out','DrawEncounterTorso',function()
    encounterTorso()
    for slot=0x6550,0x65FC,4 do enemy(slot,0x30)end
    w(0x65F4,0xF8);w(0x65FC,0xF8)
end,function()
    local s=trailSlots()
    check(s.near==0x65F4 and s.outer==0x65FC,'the torso takes the only two free entries, near one first')
    check(s.tip==nil and s.far==nil,'no tip is drawn without a free entry')
    check(isEnemy(0x65F0,0x30) and isEnemy(0x65F8,0x30),'occupied entries are untouched')
end)
add('the trail never uses entries ahead of the enemy blocks','DrawEncounterTorso',function()
    encounterTorso()
    for slot=0x6550,0x65FC,4 do enemy(slot,0x30)end
    w(0x654C,0xF8)
end,function()
    check(r(0x654C)==0xF8,'entry $4C stays free')
    local s=trailSlots()
    check(s.near==nil and s.outer==nil and s.tip==nil and s.far==nil,'no piece is drawn when $50-$FC are full')
end)
add('the tip clips at the left edge','DrawEncounterTorso',function()
    encounterTorso();w(0x651B,0x1C)
end,function()
    checkTrail(0xA0,0x04,0x40)
    check(noTrail({'tip','far'}),'no tip column is drawn')
end)
add('the far tip hides at the right edge','DrawEncounterTorso',function()
    encounterTorso();w(0x651A,1);w(0x651B,0xD8)
end,function()
    checkTrail(0xA0,0xE8,0x01)
    local s=trailSlots()
    check(s.tip and r(s.tip)==0xA0 and r(s.tip+3)==0xF8,'the near tip still draws')
    check(s.far==nil,'the far tip column stays hidden instead of wrapping')
end)
for _,case in ipairs({
    {'hidden lower row',function()w(0x6518,0xF8)end},
    {'left edge',function()w(0x651B,0x17)end},
    {'right edge',function()w(0x651A,0);w(0x651B,0xE8)end},
    {'HUD edge',function()w(0x6518,0x1F)end},
    {'fairy',function()w(0x13,1)end},
})do
    add('no encounter trail at '..case[1],'DrawEncounterTorso',function()
        encounterTorso();case[2]()
    end,function()
        check(noTrail({'near','outer','tip','far'}),'all trail slots stay hidden')
    end)
end

local function fallSetup(isShadow,facing,y)
    for address=0x200,0x2FF,4 do w(address,0xF8)end
    w(0xB5,1);w(0x80,9);w(0x81,9)
    if isShadow then
        w(0x11,1);w(0x91,0x3C);w(0xCD,0x80);w(0x2A,y);w(0xA0,facing);w(0xC9,0);w(0x0753,1);w(0x050D,0)
    else
        w(0x11,0);w(0x90,0x08);w(0xCC,0x78);w(0x29,y);w(0x9F,facing);w(0xC8,0);w(0x0752,0);w(0x050C,0)
    end
end
for _,actor in ipairs({
    {name='Barba',shadow=false,base=0x208,x=0x78,pal=0},
    {name='Shadow',shadow=true,base=0x23C,x=0x80,pal=1},
})do
    for _,facing in ipairs({1,2})do
        local dir=facing==1 and 'right' or 'left'
        add('fall-in-hole '..actor.name..' '..dir..' draws 64px torpedo','BarbaFallDraw',function()
            fallSetup(actor.shadow,facing,0x60)
        end,function()
            local b=actor.base
            local h0=facing==1 and {0x56,0x4C,0x4A} or {0x4A,0x4C,0x56}
            local h1=facing==1 and {0x5C,0x5A,0x58} or {0x58,0x5A,0x5C}
            local tt=facing==1 and {0x06,0x08} or {0x08,0x06}
            local hattr=(facing==1 and 0x40 or 0)+actor.pal
            local tattr=(facing==1 and 0x80 or 0xC0)+actor.pal
            local headOk=true
            for i=0,2 do
                local hx=actor.x+(facing==1 and 8 or 0)+i*8
                headOk=headOk and r(b+i*4)==0x60 and r(b+i*4+1)==h0[i+1] and r(b+i*4+2)==hattr and r(b+i*4+3)==hx
                headOk=headOk and r(b+12+i*4)==0x70 and r(b+12+i*4+1)==h1[i+1] and r(b+12+i*4+2)==hattr and r(b+12+i*4+3)==hx
            end
            check(headOk,actor.name..' '..dir..' downward head rows at Y and Y+16')
            local torsoOk=true
            for row=0,1 do
                local ty=0x60-(row+1)*16
                local rb=b+24+row*8
                for c=0,1 do
                    torsoOk=torsoOk and r(rb+c*4)==ty and r(rb+c*4+1)==tt[c+1]
                        and r(rb+c*4+2)==tattr and r(rb+c*4+3)==actor.x+8+c*8
                end
            end
            check(torsoOk,actor.name..' '..dir..' draws two inverted torso chunks at Y-16 and Y-32')
        end)
    end
    add('fall-in-hole '..actor.name..' clips both chunks below Y=16','BarbaFallDraw',function()
        fallSetup(actor.shadow,1,0x08)
    end,function()
        local b=actor.base
        check(r(b)==0x08 and allHidden({b+24,b+28,b+32,b+36}),
            actor.name..' hides both torso chunks when Y < 16')
    end)
    add('fall-in-hole '..actor.name..' clips only upper chunk below Y=32','BarbaFallDraw',function()
        fallSetup(actor.shadow,2,0x14)
    end,function()
        local b=actor.base
        check(r(b+24)==0x04 and r(b+28)==0x04 and allHidden({b+32,b+36}),
            actor.name..' draws lower torso at Y-16 and hides upper chunk when 16 <= Y < 32')
    end)
end

local function nextTest()
    current=current+1
    local test=tests[current]
    if not test then
        running=false
        report:write('RESULT '..(failures==0 and 'PASS' or 'FAIL')..'\n');report:close()
        stopScenario(failures==0 and 0 or 1);return
    end
    baseline();test.setup()
    report:write('CASE '..test.name..'\n');report:flush()
    local entry=assert(LABELS[test.entry],'Missing assembled label '..test.entry)
    local program={0x20,0xC5,0xFF,0x20,entry%256,math.floor(entry/256),0x4C,0x06,0x06}
    for i,value in ipairs(program)do w(0x5FF+i,value)end
    running=true
    emu.setState({['cpu.pc']=0x0600,['cpu.sp']=0xFD,['cpu.x']=7,['cpu.y']=9,['cpu.ps']=0x24})
end
emu.addMemoryCallback(function()
    if running then tests[current].verify();nextTest()end
end,emu.callbackType.exec,0x0606)
emu.addEventCallback(function()
    frame=frame+1
    if frame==120 then ready=true end
end,emu.eventType.endFrame)
emu.addMemoryCallback(function()
    if ready then ready=false;nextTest()end
end,emu.callbackType.exec,0xC07B)
