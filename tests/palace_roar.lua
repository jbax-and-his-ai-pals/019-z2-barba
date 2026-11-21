-- Each statue places a crystal through gameplay. Check the three local tile
-- swaps, restoration, and Palace 6's extra lighting in actual PPU memory.
dofile(TEST_DIR..'/newgame.lua')
local mem,ppu=emu.memType.nesMemory,emu.memType.nesPpuMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local function tile(a)return emu.read(a,ppu)end
local report=assert(io.open(OUTPUT_DIR..'/palace_roar.txt','w'))
local rooms={
    {3,0,0x0D,0}, {3,0,0x22,1}, {4,0,0x0E,2},
    {4,1,0x1C,0}, {3,2,0x29,0}, {4,2,0x3A,1}
}
local frame,age,palace,errors=0,0,1,0
local base,baseline,phase,firstLight,secondLight
local align,unrelated,restored
local trailFrames,roundedTrail
local sampled=LABELS.RoarAudio~=nil
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..'Palace '..palace..' '..message..'\n')
    if not ok then errors=errors+1 end
end

emu.addEventCallback(function()
    local buttons=newGameInput(frame)
    if base then buttons={right=age>=120 and age<200} end
    emu.setInput(buttons,0)
end,emu.eventType.inputPolled)

emu.addMemoryCallback(function()
    frame=frame+1
    if frame<1000 then return end
    age=age+1
    if age==1 then
        if base then emu.loadSavestate(base) else base=emu.createSavestate() end
        local world,region,room,code=table.unpack(rooms[palace])
        w(0x707,world);w(0x706,region);w(0x769,world)
        w(0x561,room);w(0x568,palace-1);w(0x56B,palace);w(0x56C,code);w(0x748,0x34+code)
        w(0x701,0);w(0x75C,3);w(0x704,0)
        w(0x736,0);w(0x73D,0);w(0x726,1)
        w(0x794,7-palace)
        for flag=0x78D,0x792 do w(flag,0) end
        phase,firstLight,secondLight=0,false,false
        align,unrelated,restored=true,true,false
        trailFrames,roundedTrail=0,true
    elseif age==80 then
        w(0x3B,3);w(0x4D,80);w(0x29,144);w(0x57D,0);w(0x479,0)
    elseif age==119 then
        baseline={}
        for address=0x2740,0x275F do baseline[address]=tile(address) end
        for address=0x27F2,0x27F5 do baseline[address]=tile(address) end
    elseif age>=120 then
        if sampled and r(0x5EE)&0x88==0x88 and r(0x5FA)==72 and r(0x220)<0xF0 then
            local y=r(0x218)
            trailFrames=trailFrames+1
            roundedTrail=roundedTrail and r(0x6518)==y and r(0x6519)==0x35
                and r(0x6514)==y and r(0x6515)==0x37
                and r(0x6550)==y and r(0x6554)==y
                and r(0x6558)==y and r(0x655C)==y
        end
        local near=tile(0x274E)==0x9A and tile(0x2751)==0x9B
        local middle=tile(0x274C)==0x9A and tile(0x2753)==0x9B
        local outer=tile(0x274A)==0x9A and tile(0x2755)==0x9B
        if near and phase==0 then
            phase=1
            align=not sampled or r(0x5EE)&0x88==0x88
        elseif middle and phase==1 and not near then
            phase=2
            firstLight=tile(0x27F3)==0x6B
        elseif outer and phase==2 and not middle then
            phase=3
            secondLight=tile(0x27F5)==0x6E
            if palace==6 then screenshot('palace-6-crystal-pulse') end
        elseif phase==3 and not outer and r(0xDE)~=0 then
            -- Native cleanup can change the statue's attributes after unlock.
            phase=4
            restored=true
            for address,value in pairs(baseline) do
                if tile(address)~=value then
                    restored=false
                    report:write(string.format('tile %04X started %02X ended %02X\n',address,value,tile(address)))
                end
            end
        end
        unrelated=unrelated and tile(0x2749)==baseline[0x2749] and tile(0x2756)==baseline[0x2756]
        if age==700 then
            check(r(0x794)==6-palace,'places the gem')
            check(phase>=3 and align,'floor pulses near, middle, then outer on the roar')
            check(restored and unrelated,'restores the floor and preserves surrounding tiles')
            if sampled then
                check(trailFrames>0 and roundedTrail,'right-facing bend and tail stay at foot height during the roar')
            end
            check(palace==6 and firstLight and secondLight or palace~=6 and not firstLight and not secondLight,
                palace==6 and 'lights both pedestal sections' or 'uses the standard floor pulse')
            palace=palace+1;age=0
            if not rooms[palace] then
                report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
                report:close()
                stopScenario(errors==0 and 0 or 1)
            end
        end
    end
end,emu.callbackType.exec,0xC07B)
