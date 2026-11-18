-- Encounter scenery: actual MMC3 splits and animated liquid and sprig patterns.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local ppu=emu.memType.nesPpuMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/ow-clouds.txt','w'))
local frame,index,age,fails=0,0,0,0
local base,done
local lines,banks,patterns,hudPatterns
local tips,roots,grassMismatch,splitMismatch,splitSamples
local grassWind={0,1,2,1,0,-1,-2,-1}
local stillTip={0,0,0x08,0x08,0x10,0x10,0x10,0x10,0,0,0x18,0x18,0x30,0x30,0x30,0x30}
local cases={
    {name='west-water-left',room=1,sky=true,water=true},
    {name='west-water-right',room=1,entry=0x13,sky=true,water=true},
    {name='medicine-cave',room=0x0E,water=true},
    {name='west-forest',room=3},
    {name='west-grass',terrain=5,sky=true,grass=true},
    {name='west-road',terrain=9,sky=true,grass=true},
    {name='west-swamp',terrain=7,sky=true,water=true},
    {name='east-water-room-zero',region=2,room=0,entry=6,sky=true,water=true},
    {name='east-valley',region=2,room=2,entry=2,sky=true},
    {name='east-road',region=2,room=0x39,entry=0x18,sky=true},
}
local function check(ok,msg)
    report:write((ok and 'PASS ' or 'FAIL ')..msg..'\n')
    if not ok then fails=fails+1 end
end
local function count(set)
    local n=0
    for _ in pairs(set) do n=n+1 end
    return n
end

local function enter(scene)
    w(0x707,0);w(0x706,scene.region or 0);w(0x769,scene.region and 2 or 1)
    w(0x561,scene.room or 0)
    w(0x568,0);w(0x56B,0);w(0x56C,0);w(0x701,0);w(0x75C,0);w(0x704,0)
    w(0x73D,0);w(0x726,1);w(0x774,255);w(0x784,8)
    if scene.entry or scene.terrain then
        w(0x748,scene.entry or 0xFF);w(0x563,scene.terrain or 5);w(0x736,0)
    else
        w(0x736,7)
    end
end

local function checkMap(scene)
    local sky=r(0x64EE)
    local skyRows=sky>0 and (sky-31)//16 or 0
    local clouds,invalid=0,0
    for page=0,r(0xD1) do
        for offset=0,0xCF do
            local tile=r(0x6000+page*0xD0+offset)
            local cloud=tile>=0xC2 and tile<=0xC4
            if cloud then clouds=clouds+1 end
            if offset//16<skyRows then
                if tile~=0x40 and not cloud then invalid=invalid+1 end
            elseif cloud then
                invalid=invalid+1
            end
        end
    end
    check(invalid==0 and (sky>0)==(scene.sky==true) and (clouds>0)==(scene.sky==true),
        string.format('%s sky split %d, %d clouds confined to clear rows',scene.name,sky,clouds))
    if scene.entry==0x13 then check(r(0x701)==1,scene.name..' used the native right-hand entry') end
end

local function pattern(tile)
    local bytes={}
    for i=0,15 do bytes[#bytes+1]=string.char(emu.read(tile*16+i,ppu)) end
    return table.concat(bytes)
end

local function grassTip(shift)
    local bytes={}
    for i,pixels in ipairs(stillTip) do
        local row=(i-1)%8
        local bend=(row==2 or row==3) and shift
            or ((row==4 or row==5) and (shift>0 and 1 or (shift<0 and -1 or 0)) or 0)
        bytes[i]=string.char(bend>=0 and pixels>>bend or pixels<<-bend)
    end
    return table.concat(bytes)
end

emu.addEventCallback(function() emu.setInput(newGameInput(frame),0) end,emu.eventType.inputPolled)
emu.addMemoryCallback(function()
    if done or frame<1050 or age~=0 then return end
    if not base then base=emu.createSavestate() end
    index=index+1
    local scene=cases[index]
    if not scene then
        done=true
        report:write('RESULT '..(fails==0 and 'PASS' or 'FAIL')..'\n')
        report:close()
        stopScenario(fails==0 and 0 or 1)
        return
    end
    assert(emu.loadSavestate(base))
    enter(scene)
    lines={};banks={};patterns={};hudPatterns={}
    tips={};roots={};grassMismatch=0;splitMismatch=0;splitSamples=0
    age=1
end,emu.callbackType.exec,0xC07B)

emu.addMemoryCallback(function()
    if not lines or age<60 then return end
    local stage,line=r(0x64D6),emu.getState()['ppu.scanline']
    lines[stage]=line
    if cases[index].name=='west-grass' and age>=81 and age<=100 and stage==1 then
        splitSamples=splitSamples+1
        if line~=r(0x64EE) then splitMismatch=splitMismatch+1 end
    end
end,emu.callbackType.exec,0xD4BE)

emu.addMemoryCallback(function()
    if age<80 or age>=100 or cases[index].name~='west-grass' then return end
    -- A native blank cell ($F5) can sit between sprite fetches above the
    -- sky split. It must not allow A12 to fall long enough for an extra clock.
    for offset=0,8,4 do
        w(0x200+offset,112)
        w(0x201+offset,offset==4 and 0xF5 or 0x20)
    end
end,emu.callbackType.exec,0xC1A0) -- NMI tail's JSR to CopyOamShadow6

emu.addEventCallback(function()
    frame=frame+1
    if done or age==0 then return end
    age=age+1
    if age<60 then return end
    local scene=cases[index]
    local active=r(0x736)==11 and r(0x726)==0
    local sky,grass=r(0x64EE),r(0x64F0)
    local countIrq=r(0x64D7)
    if active then
        if scene.grass then
            -- NMI chooses the CHR phase before the game increments $12.
            local shift=grassWind[((r(0x12)-1)>>3&7)+1]
            local tip=pattern(0x4E)
            tips[tip]=true
            roots[pattern(0x4F)]=true
            if tip~=grassTip(shift) or countIrq~=2 then grassMismatch=grassMismatch+1 end
        end
        banks[r(0x64EF)]=true
        patterns[pattern(0x98)..pattern(0x99)]=true
        hudPatterns[pattern(0xE7)]=true
    end
    if age==135 then
        check(active and r(0x706)==(scene.region or 0) and (not scene.room or r(0x561)==scene.room),
            scene.name..' loaded into live gameplay')
        checkMap(scene)
        check(lines[0]==31 and (sky==0 or lines[1]==sky),scene.name..' HUD and sky IRQs fire on their programmed lines')
        if scene.grass then
            check(grass==1 and count(tips)==5 and count(roots)==1 and grassMismatch==0
                and count(lines)==2,scene.name..' sprig tips sway through five CHR phases with fixed roots and HUD/sky-only IRQs')
            if scene.name=='west-grass' then
                check(splitSamples==20 and splitMismatch==0,
                    string.format('blank sprite leaves sky split stable (%d/%d wrong scanlines)',splitMismatch,splitSamples))
            end
            screenshot(scene.name..'-scenery')
        else
            check(grass==0,scene.name..' excludes mixed or plant-free rows from grass sway')
        end
        check((r(0x64F1)~=0)==(scene.water==true) and count(banks)==(scene.water and 4 or 1)
            and count(patterns)>=(scene.water and 2 or 1) and count(hudPatterns)==1,
            string.format('%s liquid uses %d R1 banks and %d surface patterns, with HUD art stable',
                scene.name,count(banks),count(patterns)))
        report:flush()
        age=0
    end
end,emu.eventType.endFrame)
