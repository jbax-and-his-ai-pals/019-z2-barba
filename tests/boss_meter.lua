-- Generate the current Bosses pack before running this scenario.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local oam=emu.memType.nesSpriteRam
local function r(address)return emu.read(address,mem) end
local function w(address,value)emu.write(address,value,mem) end
local function readFile(path)
    local file=assert(io.open(path,'rb'))
    local data=file:read('*a')
    file:close()
    return data
end

local buildReport=readFile(OUTPUT_DIR..'/build-report.json')
local digest=assert(buildReport:match('"output_sha256"%s*:%s*"(%x+)"'))
local bossMeter=buildReport:match('"boss_meter"%s*:%s*"([^"]+)"') or 'souls'
local pack=OUTPUT_DIR..'/test-pack/'..digest:sub(1,12)..'/bosses/'
local cases={
    {name='horsehead',id=0x20,hp=32,target=390},
    {name='helmethead',id=0x21,hp=48,target=390},
    {name='rebonack',id=0x20,hp=72,target=405},
    {name='carock',id=0x22,hp=48,target=390},
    {name='gooma',id=0x21,hp=144,target=430},
    {name='lava-link',id=0x21,hp=192,target=392},
    {name='thunderbird',id=0x22,hp=192,target=375},
    {name='dark-link',id=0x23,hp=8,target=405},
}
local report=assert(io.open(OUTPUT_DIR..'/boss_meter.txt','w'))
local frame,age,index,errors=0,0,0,0
local pending=false
local stats,expected,castFrame

local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n')
    if not ok then errors=errors+1 end
end

local function bossSlot(case)
    for slot=0,5 do
        local id=r(0xA1+slot)
        if r(0xB6+slot)==1 then
            if case.name=='rebonack' then
                if id==0x0A or id==0x20 and r(0x81+slot)==0 then return slot,id end
            elseif id==case.id then
                return slot,id
            end
        end
    end
end

emu.addMemoryCallback(function()
    if not pending then return end
    pending=false
    if bossMeter=='souls' then
        report:write('PASS vanilla 8-pip meter skipped on --boss-meter souls (covered by souls_boss_bar.lua)\n')
        report:write('RESULT PASS\n')
        report:close()
        stopScenario(0)
        return
    end
    index=index+1
    local case=cases[index]
    if not case then
        report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n')
        report:close()
        stopScenario(errors==0 and 0 or 1)
        return
    end
    assert(emu.loadSavestate(readFile(pack..'boss-'..case.name..'.mss')),case.name)
    age,expected,castFrame=0,nil,nil
    stats={active=0,hidden=0,missing=0,wrongColor=0,stray=0,full=false,partial=false,
        dead=false,teleport=0,dismounted=0}
end,emu.callbackType.exec,0xC07B)

emu.addEventCallback(function()
    local case=cases[index]
    if not case then return end
    local x=r(0x3B)*256+r(0x4D)
    local buttons={right=x<case.target,left=x>case.target+16,
        a=case.name=='lava-link' and age%36<27 or age>200 and age%90<25,
        b=age>250 and age%10<3,select=castFrame==frame}
    if case.name=='rebonack' and r(0x728)~=0 then
        local slot=bossSlot(case)
        if slot then
            local dx=r(0x3C+slot)*256+r(0x4E+slot)-x
            buttons.left=dx<-28 and (age%6<4 or dx<-96) or dx<0 and r(0x9F)~=2 and age%40==0
            buttons.right=dx>28 and (age%6<4 or dx>96) or dx>0 and r(0x9F)~=1 and age%40==0
        end
    end
    emu.setInput(buttons,0)
end,emu.eventType.inputPolled)

-- The hardware receives the OAM and HP prepared by the previous game update.
emu.addMemoryCallback(function()
    local case=cases[index]
    if not case or age<2 or r(0x736)~=0x0B then return end
    expected=0
    local slot,id=bossSlot(case)
    if not slot or r(0x728)==0 then return end
    if case.name=='lava-link' and r(0xAF+slot)<0x80 then return end
    if case.name=='thunderbird' and r(0x504+slot)~=0 then return end
    if case.name=='dark-link' and (r(0x63)~=3 or r(0x505)~=0) then return end
    local hp=r(0xC2+slot)
    if hp==0 or hp>case.hp then return end
    expected=(hp*8+case.hp-1)//case.hp
    if id==0x0A then stats.dismounted=stats.dismounted+1 end
    if case.name=='carock' and r(0xAF+slot)>=0xF0 then stats.teleport=stats.teleport+1 end
end,emu.callbackType.exec,0xC0BF)

emu.addEventCallback(function()
    frame=frame+1
    if index==0 then
        if frame==120 then pending=true end
        return
    end
    local case=cases[index]
    if not case then return end
    age=age+1
    if expected~=nil then
        local cells={}
        for offset=0,0xFC,4 do
            local y=emu.read(offset,oam)
            if y>=0x38 and y<=0x70 and y%8==0 and emu.read(offset+3,oam)==0x10
                and emu.read(offset+2,oam)==1 then
                local tile=emu.read(offset+1,oam)
                if tile==0x6F or tile==0x71 then cells[(0x70-y)//8+1]=tile end
            end
        end
        if expected==0 then
            stats.hidden=stats.hidden+1
            if next(cells) then stats.stray=stats.stray+1 end
            if stats.partial then stats.dead=true end
        else
            stats.active=stats.active+1
            stats.full=stats.full or expected==8
            stats.partial=stats.partial or expected<8
            for pip=1,8 do
                local filled=pip<=expected
                if cells[pip]~=(filled and 0x6F or 0x71) then
                    stats.missing=stats.missing+1
                    if stats.missing<=3 then
                        local actors={}
                        for s=0,5 do
                            actors[#actors+1]=string.format('%02x/%d/%d',r(0xA1+s),r(0xB6+s),r(0xC2+s))
                        end
                        report:write(string.format('%s frame %d pip %d expected %d filled, tile %s, actors %s\n',
                            case.name,age,pip,expected,tostring(cells[pip]),table.concat(actors,' ')))
                    end
                end
                -- Opaque center of the pip. This also checks actual sprite evaluation.
                local color=emu.getPixel(20,0x70-(pip-1)*8+12)&0xFFFFFF
                if color~=(filled and 0xB53120 or 0xFFFEFF) then stats.wrongColor=stats.wrongColor+1 end
            end
        end
        expected=nil
    end
    if age%15==0 then w(0x774,255) end
    if case.name=='thunderbird' and stats.full and not stats.partial
        and (not castFrame or frame-castFrame>=60) then
        w(0x749,7)           -- Choose Inferno and cast it with Select.
        w(0x74A,0)
        w(0x773,255)
        castFrame=frame+1
    end
    if age>=1300 then
        check(stats.active>=120 and stats.full and stats.partial,
            string.format('%s full and damaged meter sampled over %d frames',case.name,stats.active))
        check(stats.missing==0 and stats.wrongColor==0,
            string.format('%s all eight pips render (%d wrong OAM, %d wrong pixels)',
                case.name,stats.missing,stats.wrongColor))
        check(stats.hidden>=30 and stats.stray==0,
            string.format('%s meter hidden outside combat (%d stray frames)',case.name,stats.stray))
        if case.name=='carock' then check(stats.teleport>=30,'Carock meter stays through teleports') end
        if case.name=='rebonack' then check(stats.dismounted>=30,'Rebonack meter stays after dismount') end
        if case.name=='dark-link' then check(stats.dead,'Dark Barba meter clears on defeat') end
        pending=true
    end
end,emu.eventType.endFrame)
