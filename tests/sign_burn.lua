-- Town signs: reading one before burning gives the native text; after a
-- fireball scorches the board ($E3) the sign reader ($22, or $21 in five West
-- rooms) shows the burned-sign
-- lines (src/sign.inc) in rotation, the mark survives the dialogue, and it is
-- gone when the room reloads.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local SIGN_LO,SIGN_HI=0x9D0A,0x9FFF
local frame,age,phase,errors=0,0,0,0
local done,reloaded,settled,shotText=false,false,false,false
local lastPtr,stable=0,0
local pending,base,wantLoad=false,nil,false
local startPtr,captured=nil,false
local slot=nil
local talkFrame,splitMatches,scrolledReads,missingSplits=false,false,0,0
local cases={{room=0x00,kind=0x22,talk=0x98,name='Rauru entrance ($22)'},
    {room=0x09,kind=0x21,talk=0x80,name='room $09 ($21)'}}
local ci=1
local talks={}            -- text pointer captured per talk
local talkAt=nil
local f=assert(io.open(OUTPUT_DIR..'/sign-burn.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
local function ptr()return r(0x569)+r(0x56A)*256 end
local function signText(p)return p>=SIGN_LO and p<=SIGN_HI end
local function idle()return {start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}end
local function findSign()
    for x=0,5 do if r(0xB6+x)==1 and r(0xA1+x)==cases[ci].kind then return x end end
end
local function talking()return r(0x74C)~=0 end
-- Sample dialogue state at VBlank, before the engine can open/close the box.
-- Check the actual scanline scroll write, with a nonzero camera X so disabling
-- the split cannot accidentally pass on a room aligned to the nametable edge.
emu.addMemoryCallback(function()
    talkFrame=phase==3 and talking() and r(0x726)==0 and r(0xFD)~=0
    splitMatches=false
end,emu.callbackType.exec,0xC07B)
emu.addMemoryCallback(function(_,value)
    if not talkFrame then return end
    local state=emu.getState()
    if state['ppu.scanline']==31 and value==r(0xFD) then
        splitMatches=(r(0x64E0)==(r(0x746)&1))
    end
end,emu.callbackType.write,0x2005)
-- phase 1: walk to the sign, read it (intact)
-- phase 2: back off, breathe at the board until the mark is set
-- phase 3: read it twice more (rotation)
-- phase 4: reload the room, read it again (intact)
local want=nil
emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then
        b=idle()
        if want then for k,v in pairs(want) do b[k]=v end end
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addMemoryCallback(function()
    if wantLoad then wantLoad=false;emu.loadSavestate(base);return end
    if not pending then return end
    pending=false
    base=emu.createSavestate()
    check(r(0x707)==1,'native Rauru entrance loaded')
    phase=1;age=0
end,emu.callbackType.exec,0xC07B)
local px=function()return r(0x4D)end
local talkStep=0
local function talkTo(target)
    -- returns true once one conversation has been opened and closed
    if talkStep==0 then
        -- stop early: Barba slides a few pixels after releasing the d-pad
        if px()<target-12 then want={right=true} elseif px()>target+4 then want={left=true}
        else want=nil;talkStep=1;age=0 end
    elseif talkStep==1 then
        want=(age%20<3) and {up=true} or nil
        if not talking() then startPtr=ptr() end
        if talking() then talkStep=2;captured=false;want=nil end
        if age>400 then
            f:write(string.format('talk timeout px=%02X py=%02X air=%02X 74C=%02X DE=%02X C8=%02X mode=%02X\n',px(),r(0x29),r(0x479),r(0x74C),r(0xDE),r(0xC8),r(0x736)))
            talks[#talks+1]=-1;talkStep=3
        end
    elseif talkStep==2 then
        -- advance/close the box with B presses until the dialogue ends
        -- the letter pointer moves off its stale value once the new text starts
        if not captured and ptr()~=startPtr then talks[#talks+1]=ptr();captured=true end
        -- wait for the text to finish printing (pointer stops moving), then close it
        if ptr()~=lastPtr then lastPtr=ptr();stable=0 else stable=stable+1 end
        if captured and stable==60 and #talks==2 and not shotText then shotText=true;screenshot('sign-burn-text') end
        want=(captured and stable>=60 and age%6<2) and {b=true} or nil
        if not talking() then
            if not captured then
                f:write(string.format('talk closed without new text start=%04X now=%04X\n',startPtr,ptr()))
                talks[#talks+1]=-1
            end
            talkStep=3;want=nil
        end
    elseif talkStep==3 then
        want=nil;talkStep=0;return true
    end
    return false
end
emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        w(0x707,1);w(0x706,0);w(0x769,3);w(0x561,0)
        w(0x701,0);w(0x75C,0);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1)
    end
    if phase==0 then
        if frame>1150 and r(0x736)==11 then pending=true end
        if frame==1800 then check(false,'Rauru loaded');f:close();stopScenario(1)end
        return
    end
    if done then return end
    if talkFrame then
        scrolledReads=scrolledReads+1
        if not splitMatches then missingSplits=missingSplits+1 end
    end
    age=age+1
    for x=0,5 do if r(0xA1+x)<0x21 then w(0xB6+x,0) end end -- no villagers
    if phase==1 then
        slot=slot or findSign()
        if not slot then check(false,cases[ci].name..' sign reader present');f:close();stopScenario(1)return end
        if talkTo(cases[ci].talk) then
            check(talks[1]~=-1,cases[ci].name..': '..'reading the intact sign opens a dialogue')
            check(not signText(talks[1]),cases[ci].name..string.format(': intact sign shows native text (ptr %04X)',talks[1]&0xFFFF))
            check(r(0x4A0+slot)==0,cases[ci].name..': '..'intact sign has no burn mark')
            f:write("frame "..frame.." -> phase 2\n");phase=2;age=0
        end
    elseif phase==2 then
        -- step left, face right, breathe (standing, then jump-breathing) at the board
        if age<40 then want={left=true}
        elseif age<46 then want={right=true}
        else
            local t=(age-46)%60
            if age<46+180 then want={b=(t%8)<3}
            else want={a=t<18,b=(t>=10 and t<13)} end
        end
        if r(0x4A0+slot)~=0 then
            startMark=r(0x4A0+slot)
            check(startMark>=1 and startMark<=6,cases[ci].name..': burned sign starts on line 1-6 ('..startMark..')')
            f:write(string.format('mark set at age %d (pending=%02X, mark=%02X, px=%02X)\n',age,r(0x64D1),r(0x4A0+slot),px()))
            screenshot('sign-burn-scorched')
            check(true,cases[ci].name..': '..'a fireball on the sign board marks the sign actor')
            f:write("frame "..frame.." -> phase 3\n");want=nil;phase=3;age=0
        elseif age>600 then
            check(false,'a fireball on the sign board marks the sign actor (pending='..r(0x64D1)..')')
            f:close();stopScenario(1)
        end
    elseif phase==3 then
        if age<20 then want=nil return end
        if talkTo(cases[ci].talk) then
            local ok={}
            for i=2,#talks do if talks[i]~=-1 then ok[#ok+1]=talks[i] end end
            if #ok>=3 or #talks>=8 then
                for i=2,#talks do f:write(string.format('talk %d ptr=%04X mark-after=%d\n',i,talks[i]&0xFFFF,r(0x4A0+slot))) end
                check(#ok>=3,'three burned reads open ('..#ok..')')
                check(ok[1] and signText(ok[1]),cases[ci].name..': '..'burned sign shows burned-sign text')
                check(ok[2] and signText(ok[2]) and ok[2]~=ok[1],cases[ci].name..': '..'second read shows the next line')
                check(ok[3] and signText(ok[3]) and ok[3]~=ok[2],cases[ci].name..': '..'third read shows another line (mark survives dialogue)')
                local expect=(startMark-1+3)%6+1
                check(r(0x4A0+slot)==expect,'rotation advanced three lines from '..startMark..' to '..expect..' ('..r(0x4A0+slot)..')')
                check(scrolledReads>0 and missingSplits==0,string.format(
                    '%s: dialogue keeps the camera scroll at the HUD split (%d/%d frames)',
                    cases[ci].name,scrolledReads-missingSplits,scrolledReads))
                scrolledReads,missingSplits=0,0
                f:write("frame "..frame.." -> phase 4\n");phase=4;age=0
            end
        end
    elseif phase==4 then
        if not reloaded then
            reloaded=true;talkStep=0;want=nil;age=0
            -- leave and re-enter: the native area loader rebuilds the room and its actors
            w(0x707,1);w(0x706,0);w(0x769,3);w(0x561,cases[ci].room)
            w(0x701,0);w(0x75C,0);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1)
            return
        end
        if not settled then
            if age<150 or r(0x736)~=11 then want=nil return end
            settled=true
        end
        slot=findSign()
        if talkTo(cases[ci].talk) then
            check(slot and r(0x4A0+slot)==0,cases[ci].name..': '..'reloaded room: sign mark is gone')
            check(talks[#talks]~=-1 and not signText(talks[#talks]),cases[ci].name..': '..'reloaded room: sign shows native text again')
            if ci<#cases then
                -- next case: load its room, then start over at phase 1
                ci=ci+1;talks={};slot=nil;talkStep=0;want=nil
                reloaded=false;settled=false;phase=5;age=0
                return
            end
            done=true
            f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close()
            stopScenario(errors==0 and 0 or 1)
        end
    elseif phase==5 then
        if not reloaded then
            reloaded=true
            w(0x707,1);w(0x706,0);w(0x769,3);w(0x561,cases[ci].room)
            w(0x701,0);w(0x75C,0);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1)
            return
        end
        if age<150 or r(0x736)~=11 then return end
        check(r(0x561)==cases[ci].room,cases[ci].name..' loaded')
        reloaded=false;settled=false;phase=1;age=0
    end
    if frame>20000 and not done then
        done=true
        check(false,string.format('timed out in phase %d (px=%02X mode=%02X step=%d age=%d 74C=%02X)',phase,px(),r(0x736),talkStep,age,r(0x74C)))
        f:close();stopScenario(1)
    end
end,emu.eventType.endFrame)
