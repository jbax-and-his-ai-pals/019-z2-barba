-- One-shot DMC prototype: real sample reads, music channel ownership, jaw art,
-- and return to silence. Run against build/roar-prototype/barba.nes.
local frame, starts, reads, active, stopped, lastTimer = 0, 0, 0, 0, 0, 0
local pulseWrites, noiseWrites, badSample = 0, 0, false
local badJaw = false
local titleMode = nil
local ducked, fullVolume, badDuck = 0, 0, false
local lastDac, suddenStart, rampWrites = 0, false, 0
local function rd(a) return emu.read(a, emu.memType.nesDebug) end
emu.addMemoryCallback(function()
    if rd(0x8506)==0x2F and rd(0x05F0)>0 then
        if rd(0x21D)~=0x1E or rd(0x221)~=0x20 or rd(0x23D)~=0x04 then badJaw=true end
    end
end,emu.callbackType.exec,0xA58E)
emu.addMemoryCallback(function() reads=reads+1 end, emu.callbackType.read, 0xF400, 0xFD70)
emu.addMemoryCallback(function(addr, value)
    local pc=emu.getState()['cpu.pc']
    if addr==0x4011 and rd(0x8506)==0x00 and pc>=0x8F40 and pc<0x8F80 then
        if math.abs(value-lastDac)>2 then suddenStart=true end
        rampWrites=rampWrites+1;lastDac=value
    elseif addr==0x4011 and rd(0x8506)==0x2F and pc>=0xA59E and pc<0xA5E8 then
        if value~=lastDac then suddenStart=true end
        lastDac=value
    end
    if pc>=0x8F00 and pc<0x8F28 and rd(0x8506)==0x00 and (addr==0x4000 or addr==0x4004) then
        local original=emu.getState()['cpu.x']
        local expected=original
        if rd(0x05F0)>0 then
            expected=(original&0xF0)|((original&15)//2);ducked=ducked+1
        else fullVolume=fullVolume+1 end
        if value~=expected then badDuck=true end
    end
    if pc < 0xA59E or pc >= 0xA5E8 or rd(0x8506)~=0x2F then return end
    if addr>=0x4000 and addr<=0x400B then pulseWrites=pulseWrites+1 end
    if addr>=0x400C and addr<=0x400F then noiseWrites=noiseWrites+1 end
    if addr==0x4012 and value~=0xD0 then badSample=true end
end, emu.callbackType.write, 0x4000, 0x4015)
emu.addEventCallback(function()
    emu.setInput({start=frame>=860 and frame<864},0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
    frame=frame+1
    local timer=rd(0x05F0)
    if timer>lastTimer then starts=starts+1 end
    if timer>4 and rd(0x4015)&0x10~=0 then active=active+1 end
    if starts>0 and timer==0 and rd(0x4015)&0x10==0 then stopped=stopped+1 end
    lastTimer=timer
    if frame==850 then titleMode=rd(0x0736) end
    if frame==100 then
        local image=assert(io.open(OUTPUT_DIR..'/title-sample.png','wb'))
        image:write(emu.takeScreenshot());image:close()
    end
    if frame==1050 then
        local exitOk=titleMode~=nil and rd(0x0736)~=titleMode and rd(0x4015)&0x10==0
        local ok=starts>=2 and reads>100 and active>10 and stopped>10
            and pulseWrites==0 and noiseWrites==0 and not badSample and not badJaw and exitOk
            and ducked>10 and fullVolume>10 and not badDuck
            and rampWrites==32 and not suddenStart
        local f=assert(io.open(OUTPUT_DIR..'/title-sample.txt','w'))
        f:write(string.format('starts=%d sampleReads=%d activeFrames=%d silentFrames=%d pulseWrites=%d noiseWrites=%d\n',
            starts,reads,active,stopped,pulseWrites,noiseWrites))
        f:write(string.format('titleMode=%d finalMode=%d timer=%d dmcStatus=%02X\n',titleMode or -1,rd(0x736),rd(0x5F0),rd(0x4015)))
        f:write((starts>=2 and 'PASS' or 'FAIL')..' repeated title sample starts\n')
        f:write((reads>100 and active>10 and 'PASS' or 'FAIL')..' hardware DMC reads and plays sample\n')
        f:write((stopped>10 and 'PASS' or 'FAIL')..' one-shot sample returns to silence\n')
        f:write((not badJaw and 'PASS' or 'FAIL')..' complete open jaw held throughout roar\n')
        f:write((exitOk and 'PASS' or 'FAIL')..' Start during roar exits title and stops DMC\n')
        f:write((rampWrites==32 and not suddenStart and 'PASS' or 'FAIL')..' first roar starts at pre-ramped DAC midpoint without a level jump\n')
        f:write((ducked>10 and fullVolume>10 and not badDuck and 'PASS' or 'FAIL')..' title pulse volume halves during roar and restores afterward\n')
        f:write((pulseWrites==0 and noiseWrites==0 and not badSample and 'PASS' or 'FAIL')..' roar preserves music channel registers\n')
        f:write('RESULT '..(ok and 'PASS' or 'FAIL')..'\n');f:close()
        local stop=emu.exit or emu.stop;stop(ok and 0 or 1)
    end
end,emu.eventType.endFrame)
