-- Palace 5 Gooma: fireball-only kill (no thrust techniques), key drop, scroll unlock and exit.
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local weapon=nil
local weaponSprites=0
local lostSprites=0
local crowdedLines=0
local fireOverlapLines=0
local missingFireLines=0
local fireSlots={[0x38]=true,[0x3C]=true,[0x40]=true,[0x44]=true,[0x48]=true}

local function sprite(base,offset)
    return r(base+offset),r(base+offset+1),r(base+offset+2),r(base+offset+3)
end

-- Sample the four sprites immediately after the native extended swing draws
-- them. Read the store operands so this can also measure the old ROM.
emu.addMemoryCallback(function()
    if r(0x56B)~=5 or r(0x561)~=0x29 or r(0x728)==0 then return end
    weapon={}
    for _,address in ipairs({0xB6FE,0xB701,0xB704,0xB707}) do
        local y,tile,attr,x=sprite(0x200,r(address))
        if y<0xEF and (tile==0xBA or tile==0xBC or tile==0xBE) then
            weapon[#weapon+1]={y=y,tile=tile~1,attr=attr,x=x}
        end
    end
end,emu.callbackType.exec,0xB728)

emu.addMemoryCallback(function()
    if not weapon or #weapon==0 then return end
    local lines={}
    for offset=0,0xFC,4 do
        local y,tile,attr,x=sprite(0x6500,offset)
        local fire=fireSlots[offset] and tile~=0xBB and tile~=0xBD
        for line=y+1,math.min(y+16,239) do
            local row=lines[line] or {count=0,preFireCount=0,visible={}}
            lines[line]=row
            row.count=row.count+1
            if offset<0x38 then row.preFireCount=row.preFireCount+1 end
            row.firePresent=row.firePresent or fire
            if row.count<=8 then
                row.visible[#row.visible+1]={y=y,tile=tile,attr=attr,x=x}
                row.fireDrawn=row.fireDrawn or fire
            end
        end
    end
    local weaponLines={}
    for _,part in ipairs(weapon) do
        weaponSprites=weaponSprites+1
        local visible=true
        for line=part.y+1,math.min(part.y+16,239) do
            weaponLines[line]=true
            local partVisible=false
            if lines[line] then
                for _,entry in ipairs(lines[line].visible) do
                    if entry.y==part.y and entry.tile==part.tile and entry.attr==part.attr and entry.x==part.x then
                        partVisible=true
                        break
                    end
                end
            end
            visible=visible and partVisible
        end
        if not visible then lostSprites=lostSprites+1 end
    end
    for line in pairs(weaponLines) do
        local row=lines[line]
        if row and row.count>8 then crowdedLines=crowdedLines+1 end
        if row and row.firePresent then
            fireOverlapLines=fireOverlapLines+1
            if not row.fireDrawn and row.preFireCount<8 then missingFireLines=missingFireLines+1 end
        end
    end
    weapon=nil
end,emu.callbackType.exec,0xC0BF)

dofile(TEST_DIR..'/boss_fight.lua')
runBossFight{name='gooma',world=3,region=2,number=5,room=0x29,page=0,kind=3,
    bosses={[0x21]=true},final=0x21,attack=6,frames=12000,exitPage=3,
    checks=function(check,fight)
        check(weaponSprites>0 and crowdedLines>0,
            string.format('swing exercised %d weapon sprites and %d crowded lines',weaponSprites,crowdedLines))
        check(lostSprites==0,string.format('no ball or link sprites lost to OAM (%d lost)',lostSprites))
        check(fireOverlapLines>0 and missingFireLines==0,
            string.format('fire stays visible on %d overlapping lines (%d missing)',fireOverlapLines,missingFireLines))
        check((fight.damage[0x21] or 0)>0,'fireballs damaged Gooma ($21)')
    end}
