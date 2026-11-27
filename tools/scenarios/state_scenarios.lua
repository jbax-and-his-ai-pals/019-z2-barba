-- Generate human-playable snapshots using normal room loading and game logic.
-- Only progression/stats/entry location are edited; no persistent cheats run.
dofile(TEST_DIR..'/newgame.lua')
dofile(TEST_DIR..'/checkpoint_features.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local frame=0
local age=0
local index=1
local base=nil
local capture=false
local records={}
local crossingFrame=nil
local positioned=false
local function upgraded()
    w(0x700,9)
    w(0x777,4);w(0x778,8);w(0x779,8)
    w(0x783,8);w(0x784,8);w(0x773,255);w(0x774,255)
    for a=0x77B,0x782 do w(a,1)end
    for a=0x785,0x78C do w(a,1)end
    w(0x793,9);w(0x796,0x14)
    w(0x76F,0);w(0x749,7);w(0x74A,0)
    -- Level edits must refresh the cached XP threshold. Otherwise 50 XP opens
    -- a menu where no upgrade is affordable, trapping its selection loop.
    local target=65535
    for stat=0,2 do
        local offset=stat*8+r(0x777+stat)
        local cost=emu.read(0x1658+offset,emu.memType.nesPrgRom)*256
                  +emu.read(0x1670+offset,emu.memType.nesPrgRom)
        target=math.min(target,cost)
    end
    w(0x775,0);w(0x776,0)
    w(0x770,math.floor(target/256));w(0x771,target%256)
end
local function palace(world,region,number,room,page)
    local code=({[1]=0,[2]=1,[3]=2,[4]=0,[5]=0,[6]=1,[7]=2})[number] or 0
    w(0x707,world);w(0x706,region);w(0x70A,region==2 and 2 or 0);w(0x769,world==3 and 3 or 4)
    w(0x561,room);w(0x568,number-1);w(0x56B,number);w(0x56C,number==6 and 1 or 0)
    w(0x748,0x34+code)
    w(0x701,0);w(0x75C,page or 0);w(0x704,0)
    w(0x736,0);w(0x73D,0);w(0x726,1)
    if number==1 then w(0x73,32);w(0x74,62)
    elseif number==6 then w(0x73,102);w(0x74,45) end
end
local scenes={
    {id='castle',name='Starting castle',frames=0},
    {id='combat',name='Palace 1 combat corridor',frames=230,setup=function()
        upgraded();w(0x774,192);palace(3,0,1,5,0)
    end},
    {id='spells',name='All spells and techniques',frames=90,setup=function()
        upgraded()
        w(0x648B,0x57)
        for _,a in ipairs({0x63B1,0x63B2,0x63B3,0x63B4,0x63B5,0x63B7,0x63B8,0x63B9,0x63BA}) do w(a,1) end
    end},
    {id='lava-ledge',name='Palace 6 lava ledge',frames=200,setup=function()
        upgraded();palace(4,2,6,0x33,0)
    end},
    {id='lava-surface',name='Standing on palace lava',frames=290,setup=function()
        upgraded();palace(4,2,6,0x33,0)
    end},
    {id='barba',name='Palace 6 boss encounter',frames=120,setup=function()
        upgraded();palace(4,2,6,0x3A,0)
    end,capture=function()return r(0x499)==2 end},
    {id='raft',name='Sea crossing',frames=150,setup=function()
        upgraded();w(0x707,0);w(0x706,0);w(0x769,1)
        w(0x73,0x4D);w(0x74,0x3C);w(0x562,1);w(0x736,2)
        w(0x7A9,0);w(0x7AA,0);w(0x7AC,0);w(0x7AD,0);w(0x726,1)
    end},
    {id='town',name='Rauru town street',frames=150,setup=function()
        upgraded();w(0x707,1);w(0x706,0);w(0x70A,0);w(0x769,3);w(0x561,0)
        w(0x73,54);w(0x74,46);w(0x748,0x2C)
        w(0x701,0);w(0x75C,1);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1)
    end,capture=function()
        return r(0xCC)>=88 and r(0xCC)<=168
    end},
    -- Left edge of the Palace 6 boss room before the boss rises; max stats.
    {id='boss-door',name='Before Palace 6 boss',frames=60,setup=function()
        upgraded();palace(4,2,6,0x3A,0)
        -- Max attack too. Every stat is at level 8, so park the next-level
        -- XP target out of reach rather than reading past the cost tables.
        w(0x777,8);w(0x770,0xFF);w(0x771,0xFF)
    end,capture=function()return r(0x736)==11 and r(0x499)~=2 end},
    -- Great Palace Thunderbird / Dark Link encounter with max stats, all spells, and full meters.
    {id='great-palace',name='Great Palace final boss',frames=60,setup=function()
        upgraded()
        w(0x707,5);w(0x706,2);w(0x70A,2);w(0x769,5)
        w(0x73,73);w(0x74,4);w(0x748,0x36)
        w(0x561,0x35);w(0x568,6);w(0x56B,7);w(0x56C,2)
        w(0x701,0);w(0x75C,0);w(0x704,0)
        w(0x736,0);w(0x73D,0);w(0x726,1)
        w(0x777,8);w(0x770,0xFF);w(0x771,0xFF)
    end,capture=function()return r(0x736)==11 end}
}
-- Python supplies the same recipe list to generation, manifest and reload checks.
if PACK_SCENES then
    scenes={}
    for _,recipe in ipairs(PACK_SCENES) do
        local spec=recipe
        scenes[#scenes+1]={id=spec.id,name=spec.name,frames=spec.frames or 150,setup=function()
            for address,value in pairs(spec.writes) do w(address,value) end
        end,capture=function()return r(0x736)==(spec.mode or 11) and (spec.mode==5 and r(0x726)==0 or (spec.mode~=5 and r(0xB5)==1)) end}
    end
end
local function finish()
    local f=assert(io.open(PACK_DIR..'/capture-log.txt','w'))
    f:write(table.concat(records,'\n')..'\n');f:close()
    stopScenario(0)
end
local function saveScene()
    local scene=scenes[index]
    if PACK_SCENES and PACK_SCENES[index].feature then
        local ok,detail=checkpointFeature(PACK_SCENES[index])
        assert(ok,detail);records[#records+1]='FEATURE '..scene.id..' '..detail
    end
    local state=emu.createSavestate()
    local file=assert(io.open(PACK_DIR..'/'..scene.id..'.mss','wb'))
    file:write(state);file:close()
    file=assert(io.open(PACK_DIR..'/'..scene.id..'.png','wb'))
    file:write(emu.takeScreenshot());file:close()
    if PACK_SCENES and PACK_SCENES[index].town then
        local palette={}
        for a=0,15 do palette[#palette+1]=string.format('%02X',emu.read(a,emu.memType.nesPaletteRam)) end
        records[#records+1]='PALETTE '..scene.id..' '..table.concat(palette,' ')
    end
    local enemies={}
    for slot=0,5 do
        if r(0xB6+slot)>0 then enemies[#enemies+1]=string.format('%02X',r(0xA1+slot)) end
    end
    records[#records+1]=string.format('%d %s mode=%d world=%d room=%02X page=%d x=%d y=%d hp=%d enemies=%s',
        index,scene.id,r(0x736),r(0x707),r(0x561),r(0x3B),r(0x4D),r(0x29),r(0x774),table.concat(enemies,','))
    index=index+1
    if not scenes[index] then finish();return end
    assert(emu.loadSavestate(base),'Failed to restore fresh-game baseline')
    age=0
    crossingFrame=nil
    positioned=false
    scenes[index].setup()
end
emu.addEventCallback(function()
    local buttons=newGameInput(frame)
    if base then
        buttons={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
        if scenes[index] then
            local id=scenes[index].id
            if id=='combat' then buttons.right=age>=100 and age<125 end
            if id=='lava-surface' then buttons.right=age>=100 and age<230 end
            if id=='barba' then
                -- Reach the center platform under normal player movement before
                -- capturing the active fight. Core F9 captures the approach.
                buttons.right=r(0x0728)~=2
                buttons.a=r(0x3B)*256+r(0x4D)>=0xDA and (age+28)%36<27
            end
            if id=='raft' then buttons.right=age>=90 and age<110 end
            if id=='town' then buttons.right=(r(0x736)==11 and r(0xCC)<116) end
        end
    end
    emu.setInput(buttons,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if not base then
        if frame==1000 then capture=true end
    else
        age=age+1
        if scenes[index] then
            if PACK_SCENES and PACK_SCENES[index].position and age==80 then
                local p=PACK_SCENES[index].position
                w(0x3B,math.floor(p.x/256));w(0x4D,p.x%256);w(0x29,p.y)
                w(0x57D,0);w(0x479,0)
            elseif PACK_SCENES and PACK_SCENES[index].town and age==80 then
                w(0x4D,112);w(0x57D,0);w(0x479,0)
            end
            if scenes[index].id=='combat' and age==80 then
                w(0x4D,96);w(0x3B,0);w(0x29,144);w(0x57D,0);w(0x479,0)
            end
            if scenes[index].id=='raft' and r(0x736)==24 and not crossingFrame then crossingFrame=age end
            if age>=scenes[index].frames and (not scenes[index].capture or scenes[index].capture()) then
                if scenes[index].id~='raft' or (crossingFrame and age>=crossingFrame+16 and r(0x736)==24) then capture=true end
            end
            assert(age<650,'Scene did not reach its capture point: '..scenes[index].id)
        end
    end
end,emu.eventType.endFrame)
emu.addMemoryCallback(function()
    if PACK_SCENES and base and not positioned and PACK_SCENES[index].mode==5 and r(0x736)==2 then
        -- The native outside-area transition restores the last area coordinates.
        -- Supply the new entry location before normal overworld drawing begins.
        w(0x73,PACK_SCENES[index].entry['115']);w(0x74,PACK_SCENES[index].entry['116'])
        positioned=true
    end
    if capture then
        capture=false
        if not base then
            base=emu.createSavestate()
            if PACK_SCENES then scenes[1].setup();age=0;return end
        end
        saveScene()
    end
end,emu.callbackType.exec,0xC07B)
