-- Saria's three street rooms animate the palette-1 quicksand metatile.
-- The sand bank must preserve the native town graphics, including shout art.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local ppu=emu.memType.nesPpuDebug
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/saria-quicksand.txt','w'))
local fails=0
local function check(ok,msg)
    report:write((ok and 'PASS ' or 'FAIL ')..msg..'\n')
    if not ok then fails=fails+1 end
end

local function readTile(idx)
    local t={}
    local base=idx*16
    for i=0,15 do t[#t+1]=string.char(emu.read(base+i,ppu)) end
    return table.concat(t)
end

local function checkSandPalette()
    local complete, matched = true, true
    for col=0,15 do
        local attr=emu.read(0x27F8+col//4,ppu)
        local palette=(attr >> (2*(col%4//2))) & 3
        complete=complete and emu.read(0x2780+col,ppu)==0x98
                          and emu.read(0x27A0+col,ppu)==0x99
        matched=matched and palette==1
    end
    check(complete,'Saria room 6 has scrolled in all sixteen foul water tile columns')
    check(matched and emu.read(0x3F05,ppu)==0x37 and emu.read(0x3F06,ppu)==0x2A and emu.read(0x3F07,ppu)==0x0F,
        'Both halves of the foul water use green/scum/shadow palette 1 with no palette seam')
end

local function checkStreamedSand(room)
    local count, allSand = 0, true
    for nt=0x2000,0x2400,0x400 do
        for row=24,29 do
            for col=0,31 do
                local tile=emu.read(nt+row*32+col,ppu)
                if tile==0x98 or tile==0x99 then
                    local attr=emu.read(nt+0x3C0+row//4*8+col//4,ppu)
                    local shift=4*(row%4//2)+2*(col%4//2)
                    allSand=allSand and (attr>>shift)&3==1
                    count=count+1
                end
            end
        end
    end
    check(count>0 and allSand,string.format('Room %d has quicksand in every drawn liquid cell (%d tiles)',room,count))
end

local function shoutArtMatches()
    -- The S, O, and ! pairs span the R1 region that was taken from CHR 3.
    for _,pair in ipairs({0x80,0x9E,0xA0}) do
        for i=0,31 do
            if emu.read(pair*16+i,ppu)~=emu.read(7*4096+pair*16+i,emu.memType.nesChrRom) then
                return false
            end
        end
    end
    return true
end

local frame=0
local phase='enter6'
local settled=nil
local readyAt=nil
local seenBanks={}
local seenSand={}
local staticTile=nil
local staticChanged=false
local tipAtF8=false
local tipAt58=false
local villagerDropped=false

local function enterTown(town,room,page)
    w(0xB5,1);w(0x707,1);w(0x706,0);w(0x769,3);w(0x56B,town);w(0x561,room)
    w(0x568,math.max(0,town-1));w(0x56C,town//2);w(0x701,0);w(0x75C,page);w(0x704,0)
    w(0x736,0);w(0x73D,0);w(0x726,1);w(0x748,0x2C+town*2)
    settled=frame
    readyAt=nil
    seenSand={}
end

emu.addEventCallback(function()
    if frame<1000 then
        emu.setInput(newGameInput(frame),0)
    else
        emu.setInput({right=phase=='death6',left=phase=='inspect' and readyAt~=nil},0)
    end
end,emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        enterTown(2,6,1)
        w(0x79A,8)
        w(0x774,255);w(0x784,8)
    end
    if phase=='enter6' and frame>=1020 and r(0x736)==11 and r(0x726)==0 then
        settled=frame
        phase='shimmer6'
    elseif phase=='shimmer6' then
        local bank=r(0x64EF)
        seenBanks[bank]=true
        local sand=readTile(0x98)..readTile(0x99)
        seenSand[sand]=true
        local house=readTile(0x84)
        if not staticTile then staticTile=house
        elseif house~=staticTile then staticChanged=true end
        if frame>=settled+36 then
            local bankCount,sandCount=0,0
            for b in pairs(seenBanks) do
                if b==146 or b==148 or b==150 or b==152 then bankCount=bankCount+1 end
            end
            for _ in pairs(seenSand) do sandCount=sandCount+1 end
            check(bankCount==4,'Saria room 6 R1 cycles all 4 quicksand banks (146,148,150,152)')
            check(sandCount==4,'Saria room 6 quicksand tiles $98/$99 animate across 4 phases (got '..sandCount..')')
            check(not staticChanged,'Saria stationary BG tile $84 stays identical during shimmer')
            phase='death6'
            settled=frame
        end
    elseif phase=='death6' then
        if r(0x3B)==2 and r(0x4D)>=192 and not readyAt then
            readyAt=true
            checkSandPalette()
            screenshot('saria-room6-quicksand')
        end
        if r(0xB5)>1 or frame>=settled+600 then
            if not readyAt then check(false,'Barba never reached the full quicksand pit') end
            check(r(0xB5)>1,'Barba dies on Saria room 6 quicksand ($B5='..r(0xB5)..')')
            enterTown(2,7,2)
            phase='inspect'
        end
    elseif phase=='inspect' and frame>=settled+60 and r(0x736)==11 and r(0x726)==0 then
        local room=r(0x561)
        if not readyAt then
            readyAt=frame
            staticChanged=false
            tipAtF8=false
            tipAt58=false
            villagerDropped=false
        end
        seenSand[readTile(0x98)..readTile(0x99)]=true
        staticChanged=staticChanged or not shoutArtMatches()
        tipAtF8=tipAtF8 or (r(0x65F9)==0x45)
        tipAt58=tipAt58 or (r(0x6559)==0x45)
        local lineCounts={}
        for slot=0,63 do
            local y=emu.read(slot*4,emu.memType.nesSpriteRam)
            local tile=emu.read(slot*4+1,emu.memType.nesSpriteRam)
            if y<0xEF then
                local dropped=false
                for dy=0,15 do
                    local sy=y+1+dy
                    if sy>=0 and sy<240 then
                        lineCounts[sy]=(lineCounts[sy] or 0)+1
                        if lineCounts[sy]>8 then dropped=true end
                    end
                end
                if dropped and tile<=0x27 then villagerDropped=true end
            end
        end
        if frame==readyAt+36 then
            local count=0
            for _ in pairs(seenSand) do count=count+1 end
            check(count==4,string.format('Room %d animates all four quicksand patterns',room))
            check(not staticChanged,string.format('Room %d keeps town shout glyphs intact across all phases',room))
            if room==7 then
                check(tipAtF8 and not tipAt58,'Room 7 moves Barba tail tips to end of OAM ($65F8-$65FF)')
                check(not villagerDropped,'Room 7 drops zero villager sprites across the graveyard bridge')
            end
            checkStreamedSand(room)
            screenshot('saria-room'..room..'-quicksand')
            if room==7 then
                enterTown(2,8,3)
            else
                enterTown(0,0,0)
                phase='rauru'
            end
        end
    elseif phase=='rauru' and frame>=settled+40 and r(0x736)==11 and r(0x726)==0 then
        if not readyAt then readyAt=frame
        elseif frame>=readyAt+2 then
            check(r(0x64EF)==30,string.format('Rauru room 0 restores base R1 bank 30 (got %d)',r(0x64EF)))
            report:write('RESULT '..(fails==0 and 'PASS' or 'FAIL')..'\n')
            report:close()
            phase='done'
            stopScenario(fails==0 and 0 or 1)
        end
    end
    if frame==2100 then
        check(false,'timed out in phase '..phase)
        report:write('RESULT FAIL\n')
        report:close()
        stopScenario(1)
    end
end,emu.eventType.endFrame)
