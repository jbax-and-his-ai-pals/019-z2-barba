-- Die mid-Inferno / mid-METEOR-dive / mid-volley via the native kill flag
-- ($0494), continue, and assert the Inferno/METEOR state is idle and the
-- volley still fires (including game over -> continue). Logs every writer PC to Barba WRAM $6400-$64FF and
-- RAM $05EA-$05FF and fails if a non-Barba PC writes Barba WRAM.
-- Known limit (INFO, not FAIL): extra-projectile records and pending Inferno
-- waves frozen at death resume for <1 s in the respawn room.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local report=assert(io.open(OUTPUT_DIR..'/death_continue.txt','w'))
local errors=0
local function check(ok,msg)
    report:write((ok and 'PASS ' or 'FAIL ')..msg..'\n'); report:flush()
    if not ok then errors=errors+1 end
end

local barbaRanges={{0x81C1,0x81E4},{0x97F1,0x9814},{0x9847,0x9877},{0x9D0A,0x9DFF},{0x9EB9,0x9FFF},
    {0xA765,0xA7CF},{0xA89E,0xA97D},{0xAA40,0xBFF9},{0xD39A,0xD3C9},{0xFEAA,0xFECF},{0xFF4C,0xFF6E}}
local function isBarba(pc)
    for _,rg in ipairs(barbaRanges) do if pc>=rg[1] and pc<=rg[2] then return true end end
    return false
end
local writers={}
local function onWrite(addr,value)
    local pc=emu.getState()['cpu.pc']
    local region=(addr>=0x6400) and 'W' or 'R'
    local key=string.format('%s %04X',region,pc)
    writers[key]=(writers[key] or 0)+1
end
emu.addMemoryCallback(onWrite,emu.callbackType.write,0x6400,0x64FF)
emu.addMemoryCallback(onWrite,emu.callbackType.write,0x05EA,0x05FF)

local frame=0
pendingSave=false
pendingNext=false
local base=nil
local caseIndex=0
local age=0
local phase='boot'
local leftSide=false
local held={}
local shotSeen=false
local cases={
    {name='Inferno firestorm',setup=function()
        w(0x0782,1);w(0x0749,7);w(0x074A,0);w(0x0773,0xFF)
        held.select=true end},
    {name='METEOR dive',setup=function()
        w(0x076F,r(0x076F)|0x10)
        held.a=true end},
    {name='live volley',setup=function()
        held.b=true end},
    {name='game over mid-Inferno',setup=function()
        w(0x0782,1);w(0x0749,7);w(0x074A,0);w(0x0773,0xFF)
        held.select=true; held.gameover=true end},
}

local function killNow()
    -- Bot on top of Barba with 1 HP left: native contact damage kills.
    w(0x0774,0);w(0x0494,1);w(0x050C,0)
    if held.gameover then w(0x0700,1) end -- DEC to 0 = game over ($CA44)
end

local function wramIdle()
    return r(0x6470)==0 and r(0x6473)==0 and r(0x6474)==0
end

emu.addEventCallback(function()
    local b=newGameInput(frame)
    if base then
        b={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
        if phase=='act' then
            if held.select and age<3 then b.select=true end
            if held.a then
                if age>=1 and age<10 then b.a=true end
                if age>=12 and age<16 then b.down=true end
                if age==13 then b.b=true end
            end
            if held.b and age>=2 and age<5 then b.b=true end
        elseif phase=='dead' then
            -- mash Start every 40 frames to get through game over / continue.
            if age%40<3 then b.start=true end
        elseif phase=='probe' then
            if age>=20 and age<23 then b.b=true end
        end
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)

local function nextCase()
    caseIndex=caseIndex+1
    local c=cases[caseIndex]
    if not c then
        local keys={}
        for k,_ in pairs(writers) do keys[#keys+1]=k end
        table.sort(keys)
        local foreignW=0
        for _,k in ipairs(keys) do
            local region,pc=k:match('(%a) (%x+)')
            local barba=isBarba(tonumber(pc,16))
            report:write(string.format('WRITER %s count=%d %s\n',k,writers[k],barba and 'barba' or 'NON-BARBA'))
            if region=='W' and not barba then foreignW=foreignW+1 end
        end
        check(foreignW==0,'no non-Barba PC writes Barba WRAM $6400-$64FF (foreign='..foreignW..')')
        report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n'); report:close()
        stopScenario(errors==0 and 0 or 1)
        return
    end
    emu.loadSavestate(base)
    held={}; age=0; phase='act'; leftSide=false; shotSeen=false
    c.setup()
end

emu.addEventCallback(function()
    frame=frame+1
    if not base then
        if not pendingSave and frame>=1000 and r(0x0736)==0x0B and r(0x074C)==0 then
            w(0x0774,0xFF);w(0x0784,4);w(0x0777,4)
            pendingSave=true
        end
        return
    end
    if pendingNext then return end
    age=age+1
    local c=cases[caseIndex]
    if phase=='act' then
        if age==20 then
            report:write(string.format('%s at death: inferno=%d aim=%02X meteor=%d extraLive=%d shots=%02X/%02X\n',
                c.name,r(0x6470),r(0x6473),r(0x6474),r(0x645C),r(0x8D),r(0x8E)))
            killNow()
            phase='dead'; age=0
        end
    elseif phase=='dead' then
        if r(0x0736)~=0x0B then leftSide=true end
        if leftSide and r(0x0736)==0x0B and r(0x074C)==0 and age>60 then
            phase='settle'; age=0
        end
        if age>4000 then check(false,c.name..': never returned to side view after death'); pendingNext=true; phase='wait' end
    elseif phase=='settle' then
        if age==30 then
            check(wramIdle(),string.format('%s: Inferno/METEOR WRAM idle after continue (%d/%02X/%d)',
                c.name,r(0x6470),r(0x6473),r(0x6474)))
            report:write(string.format('INFO %s: extra records 30 frames after continue live=%d %02X %02X %02X'..string.char(10),
                c.name,r(0x645C),r(0x6400),r(0x6410),r(0x6420)))
            report:write(string.format('%s respawn: world=%d room=%02X hp=%d lives=%d mode=%02X\n',
                c.name,r(0x0707),r(0x0561),r(0x0774),r(0x0700),r(0x0736)))
            phase='probe'; age=0
        end
    elseif phase=='probe' then
        if r(0x8D)>0 or r(0x8E)>0 then shotSeen=true end
        if age==90 then
            check(shotSeen,c.name..': B volley fires after continue')
            pendingNext=true; phase='wait'
        end
    end
end,emu.eventType.endFrame)

emu.addMemoryCallback(function()
    if pendingSave then pendingSave=false; base=emu.createSavestate(); nextCase()
    elseif pendingNext then pendingNext=false; nextCase() end
end,emu.callbackType.exec,0xC07B)
