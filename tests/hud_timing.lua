-- Compare identical controller/room fixtures against any build, sequentially:
-- python tools/emulator_test.py tests/hud_timing.lua --rom build/barba.nes
-- Copy hud-timing.{txt,csv} before the next run (the harness reuses OUTPUT_DIR).
-- Records real PPU writes, not wall time. Lua callbacks do not consume NES cycles.
dofile(TEST_DIR..'/newgame.lua')
local mem=emu.memType.nesMemory
local function r(a)return emu.read(a,mem)end
local function w(a,v)emu.write(a,v,mem)end
local frame,failures,magicBarDropped=0,0,0
local report=assert(io.open(OUTPUT_DIR..'/hud-timing.txt','w'))
local trace=assert(io.open(OUTPUT_DIR..'/hud-timing.csv','w'))
trace:write('testFrame,phase,event,ppuFrame,scanline,dot,cpuCycle,pc,address,value\n')
local phases={'plain-idle','fire-idle','fire-attacks','fire-xp'}
local stats={}
for _,name in ipairs(phases)do
    stats[name]={samples=0,splits=0,lateSplits=0,topWrites=0,visibleAddressWrites=0,
        geometry=0,mapperWrites=0,maxNmi=0,minSplit=999,maxSplit=-1,maxDot=0}
end
local nmiStart=nil
local function active()
    return frame>=1300 and frame<2200 and r(0x736)==11 and r(0x74C)==0 and r(0x726)==0
end
local function phase()return phases[math.min(4,math.floor((frame-1300)/225)+1)]end
local function stamp(event,address,value)
    local s=emu.getState()
    trace:write(string.format('%d,%s,%s,%d,%d,%d,%d,%04X,%04X,%d\n',
        frame,phase(),event,s['ppu.frameCount'],s['ppu.scanline'],s['ppu.cycle'],
        s['cpu.cycleCount'],s['cpu.pc'],address or 0,value or 0))
    return s
end
local function check(ok,message)
    report:write((ok and 'PASS ' or 'FAIL ')..message..'\n')
    if not ok then failures=failures+1 end
end
emu.addMemoryCallback(function()
    if not active()then nmiStart=nil;return end
    local s=stamp('nmi-entry',0xC07B)
    nmiStart={cycle=s['cpu.cycleCount'],phase=phase()}
end,emu.callbackType.exec,0xC07B)
emu.addMemoryCallback(function()
    if not nmiStart then return end
    local s=stamp('nmi-return',0xC1B5)
    local p=stats[nmiStart.phase]
    p.maxNmi=math.max(p.maxNmi,s['cpu.cycleCount']-nmiStart.cycle)
    nmiStart=nil
end,emu.callbackType.exec,0xC1B5)
-- Native split: sprite-0 polling D4B2, delay D4C0-D4C4, writes D4C5/8/CB.
emu.addMemoryCallback(function()
    if not active()then return end
    local s=stamp('split',0xD4C5)
    local p=stats[phase()];local line=s['ppu.scanline']
    p.splits=p.splits+1;p.minSplit=math.min(p.minSplit,line)
    p.maxSplit=math.max(p.maxSplit,line);p.maxDot=math.max(p.maxDot,s['ppu.cycle'])
    -- NTSC sprite-zero split must stay on line 31, including attack frames.
    if line~=31 then p.lateSplits=p.lateSplits+1 end
end,emu.callbackType.exec,0xD4C5)
emu.addMemoryCallback(function(address,value)
    if not active()then return end
    local s=stamp('ppu-write',address,value)
    local line=s['ppu.scanline'];local p=stats[phase()]
    if line>=0 and line<24 then p.topWrites=p.topWrites+1 end
    if address==0x2006 and line>=0 and line<240 then
        p.visibleAddressWrites=p.visibleAddressWrites+1
    end
end,emu.callbackType.write,0x2005,0x2006)
-- NMI is disabled in C08E and re-enabled at C1B2. Preserve PPUCTRL/PPUMASK
-- alongside address/scroll writes to identify delayed VBlank or forced blanking.
emu.addMemoryCallback(function(address,value)
    if active()then stamp('ppu-control',address,value)end
end,emu.callbackType.write,0x2000,0x2001)
emu.addMemoryCallback(function()
    if active()then local p=stats[phase()];p.mapperWrites=p.mapperWrites+1 end
end,emu.callbackType.write,0xE000)
if LABELS and LABELS.BarbaGeometry then
    emu.addMemoryCallback(function()
        if active()then local p=stats[phase()];p.geometry=p.geometry+1 end
    end,emu.callbackType.exec,LABELS.BarbaGeometry)
end
emu.addEventCallback(function()
    local b=newGameInput(frame)
    if frame>=1000 then
        b={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
        if frame>=1750 then
            local t=(frame-1750)%90
            b.b=t>=10 and t<13;b.down=t>=45 and t<65
            b.a=t>=70 and t<80
        end
    end
    emu.setInput(b,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    if frame==1000 then
        -- Same Palace 1 corridor as the F2 combat checkpoint; native room loader.
        w(0x707,3);w(0x706,0);w(0x769,3);w(0x561,5)
        w(0x568,0);w(0x56B,1);w(0x56C,0);w(0x701,0);w(0x75C,0);w(0x704,0)
        w(0x736,0);w(0x73D,0);w(0x726,1)
        w(0x777,4);w(0x778,8);w(0x779,8);w(0x783,8);w(0x784,8)
        w(0x775,0);w(0x776,0);w(0x770,7);w(0x771,0xD0)
    end
    if frame==1080 then
        w(0x4D,96);w(0x3B,0);w(0x29,144);w(0x57D,0);w(0x479,0)
    end
    if frame>=1300 and frame<2200 then
        if active()then
            local p=stats[phase()];p.samples=p.samples+1
            local expectedX=(r(0x564)>>2)+0x20
            if frame>=1305 and (r(0x2F8)~=0x0F or r(0x2F9)~=0x70 or r(0x2FA)~=0x21 or r(0x2FB)~=expectedX) then
                magicBarDropped=magicBarDropped+1
            end
        end
        w(0x774,frame>=1750 and frame<1975 and 223 or 255);w(0x773,255)
        w(0x76F,frame>=1525 and 0x10 or 0)
        -- Exercise HUD number rewriting, without opening a level menu.
        if frame>=1975 and frame%30==0 then w(0x755,0);w(0x756,5)end
    end
    if frame==2200 then
        for _,name in ipairs(phases)do
            local p=stats[name]
            report:write(string.format('%s samples=%d splits=%d splitLine=%d..%d maxDot=%d lateSplits=%d topScrollAddressWrites=%d visibleAddressWrites=%d geometry=%d mapperWrites=%d maxNmiCycles=%d\n',
                name,p.samples,p.splits,p.minSplit,p.maxSplit,p.maxDot,p.lateSplits,
                p.topWrites,p.visibleAddressWrites,p.geometry,p.mapperWrites,p.maxNmi))
            check(p.samples>=180 and p.splits>=180,name..' exercised stable side-view frames')
            check(p.lateSplits==0,name..' split stays near HUD boundary')
            check(p.topWrites==0,name..' no scroll/address writes inside upper HUD')
            check(p.maxNmi<29781,name..' NMI game work finishes inside one NTSC frame')
        end
        check(magicBarDropped==0,'HUD magic partial-bar OAM $02F8 intact at full magic')
        report:write('RESULT '..(failures==0 and 'PASS' or 'FAIL')..'\n')
        report:close();trace:close();stopScenario(failures==0 and 0 or 1)
    end
end,emu.eventType.endFrame)
