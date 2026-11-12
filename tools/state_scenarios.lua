-- Generate human-playable snapshots using normal room loading and game logic.
-- Only progression/stats/entry location are edited; no persistent cheats run.
dofile(TEST_DIR..'/newgame.lua')
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
local function upgraded()
    w(0x700,9)
    w(0x777,4);w(0x778,8);w(0x779,8)
    w(0x783,8);w(0x784,8);w(0x773,255);w(0x774,255)
    for a=0x77B,0x782 do w(a,1)end
    for a=0x785,0x78C do w(a,1)end
    w(0x793,9);w(0x796,0x14)
    w(0x76F,0);w(0x749,7);w(0x74A,0)
end
local function palace(world,region,number,room,page)
    w(0x707,world);w(0x706,region);w(0x769,world==3 and 3 or 4)
    w(0x561,room);w(0x568,number-1);w(0x56B,number);w(0x56C,number==6 and 1 or 0)
    w(0x701,0);w(0x75C,page or 0);w(0x704,0)
    w(0x736,0);w(0x73D,0);w(0x726,1)
end
local scenes={
    {id='castle',name='Starting castle',frames=0},
    {id='combat',name='Palace 1 combat corridor',frames=230,setup=function()
        upgraded();w(0x774,192);palace(3,0,1,5,0)
    end},
    {id='spells',name='All spells and techniques',frames=90,setup=upgraded},
    {id='lava-ledge',name='Palace 6 lava ledge',frames=200,setup=function()
        upgraded();palace(4,2,6,0x33,0)
    end},
    {id='lava-surface',name='Standing on palace lava',frames=290,setup=function()
        upgraded();palace(4,2,6,0x33,0)
    end},
    {id='barba',name='Palace 6 boss encounter',frames=120,setup=function()
        upgraded();palace(4,2,6,0x3A,1)
    end,capture=function()return r(0x499)==2 end},
    {id='raft',name='Sea crossing',frames=150,setup=function()
        upgraded();w(0x707,0);w(0x706,0);w(0x769,1)
        w(0x73,0x4D);w(0x74,0x3C);w(0x562,1);w(0x736,2)
        w(0x7A9,0);w(0x7AA,0);w(0x7AC,0);w(0x7AD,0);w(0x726,1)
    end}
}
local function finish()
    local f=assert(io.open(PACK_DIR..'/capture-log.txt','w'))
    f:write(table.concat(records,'\n')..'\n');f:close()
    stopScenario(0)
end
local function saveScene()
    local scene=scenes[index]
    local state=emu.createSavestate()
    local file=assert(io.open(PACK_DIR..'/'..scene.id..'.mss','wb'))
    file:write(state);file:close()
    file=assert(io.open(PACK_DIR..'/'..scene.id..'.png','wb'))
    file:write(emu.takeScreenshot());file:close()
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
            if id=='raft' then buttons.right=age>=90 and age<110 end
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
    if capture then
        capture=false
        if not base then base=emu.createSavestate() end
        saveScene()
    end
end,emu.callbackType.exec,0xC07B)
