-- Rauru sage basement post-Shield "WAIT" + 5-box dialogue sequence.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local frame,age,done,errors=0,0,false,0
local report=assert(io.open(OUTPUT_DIR..'/sage-basement.txt','w'))
local function check(ok,msg)
    report:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');report:flush()
    if not ok then errors=errors+1 end
end
local function finish()
    if done then return end
    done=true
    report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');report:close()
    stopScenario(errors==0 and 0 or 1)
end

local phase='approach_sage'
local bPulse=0
local startPulse=0
local seenPointers={}
local waitDismissed=false
local reentered=false
local postWalkDone=false
local shotCaptured=false

local function ptr()
    return r(0x0569)+256*r(0x056A)
end

local function loadBasement(page)
    w(0x0783,1);w(0x0784,1);w(0x0773,255);w(0x0774,255)
    w(0x0707,1);w(0x0706,0);w(0x0769,3)
    w(0x0561,0x24);w(0x0568,0);w(0x056B,0);w(0x056C,0)
    w(0x0701,0);w(0x075C,page or 1);w(0x0704,0)
    w(0x0736,0);w(0x073D,0);w(0x0726,1)
    age=0
end

emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then
        b={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
        if phase=='approach_sage' and age>=60 then
            b.right=true
        elseif phase=='wait_spell' then
            if startPulse>0 then b.start=true;startPulse=startPulse-1 end
        elseif phase=='walk_away' then
            b.left=true
        elseif phase=='wait_box' then
            if bPulse>0 then b.b=true;bPulse=bPulse-1 end
        elseif phase=='walk_back' and age>=20 then
            b.right=true
        elseif phase=='leave_room' then
            b.left=true
        elseif phase=='return_sage' and age>=60 then
            b.right=true
        elseif phase=='seq_boxes' then
            if bPulse>0 then b.b=true;bPulse=bPulse-1 end
        elseif phase=='recheck_away' then
            b.left=true
        elseif phase=='recheck_return' then
            b.right=true
        end
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)

emu.addEventCallback(function()
    if done then return end
    frame=frame+1
    if frame==1000 then
        w(0x077B,0)
        w(LABELS.SAGE_STATE,0);w(LABELS.SAGE_BOX,0)
        loadBasement(1)
        return
    end
    if frame<=1000 then return end
    age=age+1

    if phase=='approach_sage' then
        if r(0x074C)==2 and r(0x077B)==1 then
            check(r(LABELS.SAGE_STATE)==1,'sage basement armed before Shield completes')
            phase='wait_spell'
        end
    elseif phase=='wait_spell' then
        if r(0x074C)==0 and r(0x074B)==0 and r(0xDE)==0 then
            if r(0x0524)==5 and startPulse==0 then
                startPulse=3
            elseif r(0x0524)==0 and r(LABELS.SAGE_STATE)==2 then
                check(true,'Shield learned and spell menu closed (SAGE_STATE=2)')
                phase='walk_away'
            end
        end
    elseif phase=='walk_away' then
        if r(0x074C)==2 then
            check(r(0x3B)==1 and r(0x4D)<=0x40 and r(0x4D)>=0x30,'WAIT. triggers past halfway toward the left exit (X='..r(0x4D)..')')
            check(r(LABELS.SAGE_STATE)==3,'SAGE_STATE advances to 3 on WAIT')
            phase='wait_box'
        end
    elseif phase=='wait_box' then
        if r(0x074C)==2 and r(0x0524)==6 and not waitDismissed then
            check(ptr()==LABELS.SageWaitText,'WAIT message box pointer matches SageWaitText')
        end
        if r(0x074C)==2 and r(0x0524)==9 and r(0x0766)==1 and bPulse==0 then
            bPulse=3
        elseif waitDismissed==false and r(0x074C)==0 and r(0x0524)==0 and r(0xDE)==0 and r(LABELS.SAGE_STATE)==3 then
            waitDismissed=true
            check(true,'WAIT message box dismissed cleanly')
            -- Walk straight back to the sage in the same visit: the sequence must start on its own.
            phase='walk_back'
            age=0
        end
    elseif phase=='walk_back' then
        if r(0x074C)==2 then
            check(r(LABELS.SAGE_STATE)==4,'walking straight back to sage auto-starts sequence (SAGE_STATE=4, X='..r(0x4D)..')')
            phase='seq_boxes'
        end
    elseif phase=='leave_room' then
        if r(0x3B)==0 and r(0x4D)<=200 then
            check(r(LABELS.SAGE_STATE)==3,'SAGE_STATE stays 3 while leaving without talking to sage')
            loadBasement(1)
            reentered=true
            phase='return_sage'
        end
    elseif phase=='return_sage' then
        if age>=60 and r(0x074C)==2 then
            check(reentered and r(LABELS.SAGE_STATE)==4,'returning to sage later triggers sequence (SAGE_STATE=4)')
            phase='seq_boxes'
        end
    elseif phase=='seq_boxes' then
        if r(0x074C)==2 and r(0x0524)==6 then
            local p=ptr()
            if #seenPointers==0 or seenPointers[#seenPointers]~=p then
                seenPointers[#seenPointers+1]=p
            end
        end
        if r(0x074C)==2 and r(0x0524)==9 and r(0x0766)==1 and bPulse==0 then
            if #seenPointers==2 and not shotCaptured then
                shotCaptured=true
                screenshot('sage-think-box')
            end
            bPulse=3
        elseif #seenPointers>=5 and r(0x074C)==0 and r(0x0524)==0 and r(0xDE)==0 then
            check(seenPointers[1]==LABELS.SageUmText,'box 1 is "UM..."')
            check(seenPointers[2]==LABELS.SageThinkText,'box 2 is "DO YOU / THINK A / SAGE..."')
            check(seenPointers[3]==LABELS.SageDragonText,'box 3 is "AND A / DRAGON..."')
            check(seenPointers[4]==LABELS.SageUmText,'box 4 is "UM..."')
            check(seenPointers[5]==LABELS.SageNevermindText,'box 5 is "NEVER / MIND..."')
            check(r(LABELS.SAGE_STATE)==8,'SAGE_STATE is 8 after sequence completes')
            phase='recheck_away'
            age=0
        end
    elseif phase=='recheck_away' then
        if r(0x074C)~=0 then
            check(false,'dialogue retriggered while walking away after completion')
            finish()
        elseif r(0x3B)==1 and r(0x4D)<=0x48 then
            phase='recheck_return'
            age=0
        end
    elseif phase=='recheck_return' then
        if r(0x074C)~=0 then
            check(false,'dialogue retriggered when returning to sage after completion')
            finish()
        elseif r(0x3B)==1 and r(0x4D)>=176 then
            check(r(LABELS.SAGE_STATE)==8,'sequence never triggers again after completion')
            finish()
        end
    end

    if frame>4000 then
        check(false,'timeout in phase '..phase..' (74C='..r(0x074C)..' 524='..r(0x0524)..' state='..r(LABELS.SAGE_STATE)..')')
        finish()
    end
end,emu.eventType.endFrame)
