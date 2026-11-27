-- Error of Ruto: killing Error ($0E in world 1, town 1) with firebreath
-- leaves a persistent ash pile that you can interact with: "I AM ASH PILE."
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end

local frame,age,phase,errors=0,0,0,0
local done=false
local slot=nil
local want=nil
local ashStartFrame=nil
local sawAshOamDuringTalk=false

local f=assert(io.open(OUTPUT_DIR..'/error-ash.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
local function finish()
    if done then return end
    done=true
    f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close()
    stopScenario(errors==0 and 0 or 1)
end

local function idle()
    return {start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
end
local function ptr()return r(0x0569)+r(0x056A)*256 end
local function talking()return r(0x074C)~=0 end
local function findError()
    for x=0,5 do
        if r(0xB6+x)==1 and r(0xA1+x)==0x0E then return x end
    end
end

local function decodeTownLine(addr)
    local out={}
    for i=0,31 do
        local b=(addr<0x8000) and r(addr+i) or emu.read(0xC000+(addr-0x8000)+i,emu.memType.nesPrgRom)
        if b==0xFF then break
        elseif b==0xFD then out[#out+1]='/'
        elseif b==0xF4 then out[#out+1]=' '
        elseif b==0xCF then out[#out+1]='.'
        elseif b==0x35 then out[#out+1]="'"
        elseif b>=0xDA and b<=0xF3 then out[#out+1]=string.char(b-0xDA+65)
        else out[#out+1]='?' end
    end
    return table.concat(out)
end

local function hasAshOam()
    for i=0,63 do
        local y=r(0x0200+i*4)
        local t=r(0x0201+i*4)
        if y<0xF0 and (t==0x7E or t==0x80) then return true end
    end
    return false
end

local function loadErrorRoom()
    w(0x0707,1);w(0x0706,0);w(0x0769,3)
    w(0x0561,0x1D);w(0x0568,0);w(0x056B,1);w(0x056C,0)
    w(0x0701,0);w(0x075C,2);w(0x0704,0)
    w(0x0736,0);w(0x073D,0);w(0x0726,1)
    age=0
end
local function p16()return r(0x3B)*256+r(0x4D) end
local function e16()return r(0x3C+slot)*256+r(0x4E+slot) end

emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then
        b=idle()
        if want then for k,v in pairs(want) do b[k]=v end end
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)

local talkStep=0
local alivePtr=0
local ashPtr=0

emu.addEventCallback(function()
    if done then return end
    frame=frame+1;age=age+1
    if frame==1000 then
        loadErrorRoom()
        phase=1
    elseif phase==1 then
        if r(0x0736)==11 and age>=45 then
            slot=findError()
            check(slot~=nil,'Ruto Error room ($1D, $056B=1) spawned actor $0E')
            if not slot then finish();return end
            phase=2;age=0;talkStep=0
        elseif age>180 then
            check(false,'Ruto Error room failed to load');finish()
        end
    elseif phase==2 then
        -- Talk to alive Error first
        local ex=e16()
        local px=p16()
        if talkStep==0 then
            if px<ex-8 then want={right=true}
            elseif px>ex+8 then want={left=true}
            else want=nil;talkStep=1;age=0 end
        elseif talkStep==1 then
            want=(age%20<3) and {up=true} or nil
            if talking() then
                talkStep=2;age=0;want=nil
            elseif age>120 then
                check(false,string.format('alive Error did not open dialogue (px=%02X ex=%02X A8=%02X 3B=%02X 3C=%02X)',
                    px,ex,r(0xA8+slot),r(0x3B),r(0x3C+slot)));finish()
            end
        elseif talkStep==2 then
            if age==20 then alivePtr=ptr() end
            want=(age>=40 and age%20<3) and {b=true} or nil
            if not talking() then
                check(alivePtr~=0 and (alivePtr<0x9D0A or alivePtr>0x9FFF),
                    string.format('alive Error uses native dialogue (ptr=%04X)',alivePtr))
                want=nil;phase=3;age=0
            elseif age>240 then
                check(false,'alive Error dialogue did not close');finish()
            end
        end
    elseif phase==3 then
        -- Back off left, then breathe fire right until Error ignites
        local px=p16()
        local ex=e16()
        local af=r(0xAF+slot)
        if af>=0xC0 then
            want=nil
            check(true,'Error ignited on firebreath')
            phase=4;age=0
        elseif px>ex-0x40 and age<90 then
            want={left=true}
        else
            want=(age%18<4) and {b=true,right=true} or {right=true}
            if age>300 then
                check(false,'firebreath did not ignite Error');finish()
            end
        end
    elseif phase==4 then
        -- Wait for burning to finish and become ash ($BF), then wait 200 frames
        local af=r(0xAF+slot)
        if af==0xBF then
            if not ashStartFrame then ashStartFrame=frame end
            if frame-ashStartFrame>=200 then
                check(r(0xB6+slot)==1 and r(0xAF+slot)==0xBF,
                    'Error ash pile persists past normal ~124-frame expiry')
                phase=5;age=0;talkStep=0
            end
        elseif age>120 and not ashStartFrame then
            check(false,string.format('Error did not reach ash state (AF=%02X)',af));finish()
        end
    elseif phase==5 then
        -- Walk to ash pile and talk with Up
        local ex=e16()
        local px=p16()
        if talkStep==0 then
            if px<ex-8 then want={right=true}
            elseif px>ex+8 then want={left=true}
            else want=nil;talkStep=1;age=0 end
        elseif talkStep==1 then
            want=(age%20<3) and {up=true} or nil
            if talking() then
                talkStep=2;age=0;want=nil
            elseif age>120 then
                check(false,'Error ash pile did not open dialogue on Up');finish()
            end
        elseif talkStep==2 then
            if age==20 then ashPtr=ptr() end
            if hasAshOam() then sawAshOamDuringTalk=true end
            want=(age>=50 and age%20<3) and {b=true} or nil
            if not talking() then
                local txt=decodeTownLine(0x63C0)
                check(ashPtr>=0x63C0 and ashPtr<0x6400,
                    string.format('ash pile uses custom text pointer (%04X: %s)',ashPtr,txt))
                check(txt=="I AM/ERROR'S/ASH PILE.",
                    string.format('ash pile text is "I AM/ERROR\'S/ASH PILE." (got "%s")',txt))
                check(sawAshOamDuringTalk,'ash pile OAM remains visible during dialogue')
                check(r(0xAF+slot)==0xBF and r(0x05C3+slot)==0,
                    'ash pile stays in ash state after closing dialogue')
                want=nil;phase=6;age=0;talkStep=0
            elseif age>240 then
                check(false,'ash pile dialogue did not close');finish()
            end
        end
    elseif phase==6 then
        -- Verify B button also talks to the ash pile
        if talkStep==0 then
            want=(age>=10 and age%20<3) and {b=true} or nil
            if talking() then
                talkStep=1;age=0;want=nil
            elseif age>120 then
                check(false,'Error ash pile did not open dialogue on B');finish()
            end
        elseif talkStep==1 then
            if age==20 then
                check(ptr()==ashPtr,string.format('B button also opens "I AM ASH PILE." dialogue (got %04X)',ptr()))
            end
            want=(age>=50 and age%20<3) and {b=true} or nil
            if not talking() then
                check(r(0xAF+slot)==0xBF,'ash pile still intact after second talk')
                finish()
            elseif age>240 then
                check(false,'second ash pile dialogue did not close');finish()
            end
        end
    end
    if frame>4000 then
        check(false,'timeout in phase '..tostring(phase))
        finish()
    end
end,emu.eventType.endFrame)
