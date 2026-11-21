-- Reload every generated state and let the real game run after loading.
dofile(TEST_DIR..'/newgame.lua')
dofile(TEST_DIR..'/checkpoint_features.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local frame=0
local age=0
local index=0
local pending=false
local failures=0
local initialX=0
local initialY=0
local walkStartX=0
local downY=0
local elevatorDown=false
local elevatorUp=false
local pendingDrop=false
local dropProbe=false
local dropBelowScreen=false
local dropLives=0
local sawFallMode=false
local fallFullFrames=0
local fallPoseValid=true
local moved=false
local file=assert(io.open(PACK_DIR..'/validation.txt','w'))
local ids=PACK_IDS or {'castle','combat','spells','lava-ledge','lava-surface','barba','raft','town','boss-door','great-palace'}
local function check(ok,text)
    file:write((ok and 'PASS ' or 'FAIL ')..text..'\n');file:flush()
    if not ok then failures=failures+1 end
end
local function nextState()
    index=index+1
    if not ids[index] then
        file:write('RESULT '..(failures==0 and 'PASS' or 'FAIL')..'\n');file:close()
        stopScenario(failures==0 and 0 or 1);return
    end
    local stateFile=assert(io.open(PACK_DIR..'/'..ids[index]..'.mss','rb'))
    local state=stateFile:read('*a');stateFile:close()
    check(emu.loadSavestate(state),ids[index]..' native .mss loads')
    age=0
    initialY=r(0x29);elevatorDown=false;elevatorUp=false;dropProbe=false;dropBelowScreen=false
    sawFallMode=false;fallFullFrames=0;fallPoseValid=true
    initialX=PACK_SCENES and PACK_SCENES[index].mode==5 and r(0x73)*256+r(0x74) or r(0x3B)*256+r(0x4D);moved=false
end
emu.addEventCallback(function()
    local feature=PACK_SCENES and PACK_SCENES[index] and PACK_SCENES[index].feature
    local duckUnderCeiling=feature=='ceiling' and age>=4 and age<9
    emu.setInput({start=not PACK_SCENES and index==2 and age>=90 and age<93,select=false,a=false,b=false,up=feature=='elevator' and age>=25 and age<37,down=duckUnderCeiling or (feature=='elevator' and age>=10 and age<22) or PACK_SCENES~=nil and PACK_SCENES[index]~=nil and PACK_SCENES[index].mode==5 and age>=22 and age<38,left=feature=='pit' and age>=10 and age<16,right=(dropProbe and age>=130 and age<146) or (PACK_SCENES~=nil and feature~='elevator' and feature~='pit' and age>=10 and age<22)},0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if index==0 then
        if frame==120 then pending=true end
        return
    end
    if PACK_SCENES and not PACK_SCENES[index] then return end
    age=age+1
    if PACK_SCENES and age>10 and age<42 and (PACK_SCENES[index].mode==5 and r(0x73)*256+r(0x74) or r(0x3B)*256+r(0x4D))~=initialX then moved=true end
    if PACK_SCENES and PACK_SCENES[index].walk_in_view then
        if age==10 then walkStartX=r(0x3B)*256+r(0x4D) end
        if age==22 then
            local x=r(0x3B)*256+r(0x4D)
            local screenX=r(0xCC)
            check(x-walkStartX>=5 and screenX>=88 and screenX<=136,
                ids[index]..string.format(' walks right in view: world x %d -> %d, screen anchor x %d',walkStartX,x,screenX))
        end
    end
    if PACK_SCENES and PACK_SCENES[index].feature=='elevator' then
        if age==23 or age==38 then
            check(r(0x754)~=0 and r(0x5FA)==54 and r(0x204)==0xF8 and r(0x24C)==0xF8 and r(0x2C4)==0xF8,
                ids[index]..' ducks while riding elevator age='..age)
            if age==23 then screenshot('elevator-duck-'..index)end
        end
        if age==23 then downY=r(0x29);elevatorDown=downY>initialY end
        if age==38 then
            elevatorUp=r(0x29)<downY;moved=elevatorDown and elevatorUp
            check(moved,ids[index]..string.format(' elevator controller Y=%d -> %d -> %d',initialY,downY,r(0x29)))
        end
    end
    if PACK_SCENES and PACK_SCENES[index].feature=='ceiling' and age==6 then
        local right=r(0x9F)==1
        local headY=r(0x29)+8
        local back=right and 0x6514 or 0x651C
        check(r(0x5FA)==54 and r(0x6508)==headY and r(0x650C)==headY and r(0x6510)==headY
            and r(0x6509)==(right and 0x05 or 0x01) and r(0x650D)==0x03 and r(0x6511)==(right and 0x01 or 0x05),
            ids[index]..' Down draws all three full head columns')
        check(r(0x6518)==headY+16 and r(back)==headY+16 and r(0x6519)==0x33 and r(back+1)==0x55,
            ids[index]..' Down draws the cropped elbow entirely below the full head')
        local floorY=r(0x29)+32
        for i,tile in ipairs({0x15,0x3F,0x45,0x31})do
            local slot=0x6550+4*(i-1)
            check(r(slot)+16==floorY-1 and r(slot+1)==tile,
                ids[index]..' crouched trail column '..i..' stays above the brick surface')
        end
    end
    if PACK_SCENES and age==45 then
        check(moved,ids[index]..' responds to controller movement')
        if PACK_SCENES[index].mode~=5 then
            check(r(0x19)==1 and r(0x29)>=48 and r(0x29)<224,ids[index]..' player sprite in visible playfield')
        end
    end
    if not PACK_SCENES and index==2 then
        if age==10 then
            check(r(0x770)*256+r(0x771)==2000,'upgraded combat checkpoint has correct next-level XP target')
            emu.write(0x775,0,mem);emu.write(0x776,50,mem)
        end
        if age==30 then check(r(0x74C)==0,'small XP gain does not open an unaffordable upgrade menu') end
        if age==40 then emu.write(0x775,7,mem);emu.write(0x776,0xD0,mem) end
        if age==80 then check(r(0x74C)==1,'affordable XP gain opens level-up menu') end
        if age==400 then
            check(r(0x777)==5 and r(0x775)==0 and r(0x776)==0,'accepting upgrade raises attack and spends XP once')
            check(r(0x74C)==0,'upgrade returns to normal gameplay without looping (dialog='..r(0x74C)..', menu='..r(0x524)..')')
        end
    end
    if age==3 then
        if PACK_SCENES then
            local spec=PACK_SCENES[index]
            if spec.walk_in_view then
                local screenX=r(0xCC)
                check(screenX>=88 and screenX<=136 and r(0x29)==spec.position.y and r(0x479)==0,
                    ids[index]..string.format(' starts grounded near center: screen anchor x %d, y %d',screenX,r(0x29)))
            end
            if spec.feature then
                local ok,detail=checkpointFeature(spec)
                check(ok,ids[index]..' '..detail)
            end
            check(r(0x773)<=r(0x783)*32-1 and r(0x774)<=r(0x784)*32-1,ids[index]..' meters fit native container capacity')
            check(r(0x736)==(spec.mode or 11) and r(0x707)==spec.world and (spec.mode==5 or r(0x561)==spec.room),ids[index]..' expected room/world')
            if spec.mode==5 then check(r(0x706)==spec.region and r(0x73)==spec.entry['115'] and r(0x74)==spec.entry['116'],ids[index]..' expected overworld location') end
            for address,value in pairs(spec.expected) do
                check(r(address)==value,ids[index]..string.format(' progression $%04X = %d',address,value))
            end
            if ids[index]=='boss-dark-link' then
                check(r(0xB6)==1 and r(0xA1)==0x23 and r(0x753)==2 and (r(0x0252)&3)==2,'boss-dark-link has active shadow-palette Dark Barba')
            end
        end
        check(r(0xB5)==1,ids[index]..' player is alive after load')
        local pixels=emu.getScreenBuffer()
        local distinct={}
        for i=1,#pixels,97 do distinct[pixels[i]]=true end
        local colors=0;for _ in pairs(distinct)do colors=colors+1 end
        check(colors>3,ids[index]..' visible game frame')
        if not PACK_SCENES and index<7 then check(r(0x736)==11,ids[index]..' side-view gameplay ready') end
        if not PACK_SCENES and (index==1 or index==2 or index==8) then
            for i,tile in ipairs({0x15,0x3F,0x45,0x31})do
                local slot=0x6550+4*(i-1)
                check(r(slot)<0xF0 and r(slot+1)==tile,
                    ids[index]..' draws default horizontal body column '..i)
            end
        end
        if not PACK_SCENES and index==2 then check(r(0x774)<255 and r(0x707)==3,'combat has damaged health and Palace 1 geometry') end
        if not PACK_SCENES and index==3 then
            local spells=true
            for a=0x77B,0x782 do if r(a)==0 then spells=false end end
            check(spells and (r(0x796)&0x14)==0x14,'all spells and both thrust techniques unlocked')
            check(r(0x773)==255 and r(0x774)==255,'spell sandbox begins with full meters')
        end
        if not PACK_SCENES and index==5 then check(r(0xA7)&4~=0 and r(0x479)==0,'lava surface supports the player') end
        if not PACK_SCENES and index==6 then
            local boss=false
            for slot=0,5 do if r(0xA1+slot)==0x21 and r(0xB6+slot)>0 then boss=true end end
            check(boss and r(0x561)==0x3A and r(0x76E)==24,'native Palace 6 boss and graphics present')
        end
        if not PACK_SCENES and index==7 then check(r(0x736)==24 and r(0x7A9)>0,'native raft crossing is active') end
        if not PACK_SCENES and index==8 then
            local random=false
            for slot=0,5 do
                if r(0xB6+slot)==1 and r(0xBC+slot)==255 then random=true end
            end
            check(r(0x736)==11 and r(0x707)==1 and r(0x561)==0 and random,
                'town checkpoint contains a native generated outdoor wanderer')
        end
        if not PACK_SCENES and index==9 then
            check(r(0x736)==11 and r(0x561)==0x3A and r(0x707)==4,'boss-door is in the Palace 6 boss room')
            check(r(0x777)==8 and r(0x778)==8 and r(0x779)==8 and r(0x784)==8,'boss-door has maximum levels and containers')
            check(r(0x499)~=2,'boss-door begins before the boss rises')
        end
        if not PACK_SCENES and index==10 then
            check(r(0x736)==11 and r(0x561)==0x35 and r(0x707)==5,'great-palace is in Great Palace room $35')
        end
    end
    if not PACK_SCENES and index==6 and age==90 then screenshot('test-pack-boss-active') end
    if age==(not PACK_SCENES and index==2 and 410 or 120) then
        check(r(0x774)>0 and r(0x76C)~=2,ids[index]..' remains playable for 120 frames')
        if not PACK_SCENES and index==7 then check(r(0x706)==2 and r(0x736)==5,'sea crossing ends on East Hyrule overworld') end
        if PACK_SCENES and PACK_SCENES[index].feature=='pit' then
            -- A geometric gap is not automatically a lethal pit: prove native routing.
            pendingDrop=true
        else pending=true end
    end
    if dropProbe then
        if r(0x29)>=224 and r(0x561)==PACK_SCENES[index].room then dropBelowScreen=true end
        if r(0x0736)==0x0F and r(0x0208)<0xF0 then
            sawFallMode=true
            if r(0x80)~=9 or r(0x81)~=9 then fallPoseValid=false end
            local by,sy=r(0x0208),r(0x023C)
            if by>=0x40 and by<0xD8 and sy>=0x40 and sy<0xD8 then
                fallFullFrames=fallFullFrames+1
                if fallFullFrames==20 then screenshot('barba-drop-shaft') end
                local right=r(0x9F)==1
                -- Pose 9 uses the native six-tile draw table. The asset
                -- compiler may reassign its CHR indexes when it shares art.
                local headTiles=0xEB25+r(0xEB97+9)
                local function fallOk(base,py,px,pal)
                    -- Validate DMA order: all 13 player sprites precede the shadow.
                    for offset=0,36,4 do
                        local src,dst=base+offset,base+offset+0x6300
                        if r(dst)~=r(src) or r(dst+1)~=(r(src+1)~1)
                            or r(dst+2)~=r(src+2) or r(dst+3)~=r(src+3) then return false end
                    end
                    local outer=base+0x6300+40
                    local tt=right and {0x06,0x08} or {0x08,0x06}
                    local hattr=(right and 0x40 or 0)+pal
                    local tattr=(right and 0x80 or 0xC0)+pal
                    for row=0,1 do
                        for col=0,2 do
                            local sprite=base+row*12+col*4
                            local tile=r(headTiles+row*3+(right and 2-col or col))
                            if tile==0xF5 or r(sprite)~=py+row*16 or r(sprite+1)~=tile
                                or r(sprite+2)~=hattr then return false end
                        end
                    end
                    for row=0,1 do
                        local ty=py-(row+1)*16
                        local rowBase=base+24+row*8
                        for c=0,1 do
                            if r(rowBase+c*4)~=ty or r(rowBase+c*4+1)~=tt[c+1]
                                or r(rowBase+c*4+2)~=tattr or r(rowBase+c*4+3)~=px+8+c*8 then return false end
                        end
                    end
                    for c=0,1 do
                        local slot=outer+c*4
                        if r(slot)~=py-0x30 or r(slot+1)~=tt[c+1]+1
                            or r(slot+2)~=tattr or r(slot+3)~=px+8+c*8 then return false end
                    end
                    return r(outer+8)==py-0x40 and r(outer+9)==0x0B
                        and r(outer+10)==(tattr~0xC0) and r(outer+11)==px+12
                end
                if not fallOk(0x0208,by,0x78,0) or not fallOk(0x023C,sy,0x80,1) then fallPoseValid=false end
            end
        end
        if age==350 then
            check(sawFallMode and fallFullFrames>0 and fallPoseValid,
                ids[index]..string.format(' fall-in-hole mirrors the tips and draws all of Barba ahead of the shadow (%d full frames)',fallFullFrames))
            check(dropBelowScreen and r(0x561)==45 and r(0x700)==dropLives and r(0xB5)==1,
                ids[index]..string.format(' native drop reaches room $%02X, lives %d -> %d (NOT lethal)',r(0x561),dropLives,r(0x700)))
            pending=true
        end
    end
end,emu.eventType.endFrame)
emu.addMemoryCallback(function()
    if pendingDrop then
        pendingDrop=false
        local stateFile=assert(io.open(PACK_DIR..'/'..ids[index]..'.mss','rb'))
        assert(emu.loadSavestate(stateFile:read('*a')));stateFile:close()
        dropProbe=true;dropLives=r(0x700)
        sawFallMode=false;fallFullFrames=0;fallPoseValid=true
    end
    if pending then pending=false;nextState()end
end,emu.callbackType.exec,0xC07B)
