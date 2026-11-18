-- METEOR (spell slot 4, $076F bit 4): airborne Down + B dives at the native
-- fall cap; landing emits one flat floor shockwave each way (fire class),
-- which hits a floor Bot. Without the spell, Down + B is an ordinary volley.
dofile(TEST_DIR..'/newgame.lua')
local m=emu.memType.nesMemory
local function r(a)return emu.read(a,m)end
local function w(a,v)emu.write(a,v,m)end
local METEOR_STATE=0x6474
local frame,age,phase,errors=0,0,0,0
local base,pending=nil,false
local f=assert(io.open(OUTPUT_DIR..'/meteor.txt','w'))
local function check(ok,msg)
    f:write((ok and 'PASS ' or 'FAIL ')..msg..'\n');f:flush()
    if not ok then errors=errors+1 end
end
local phases={
    {name='METEOR dive and shockwave',spell=true,enemy=false},
    {name='no spell: Down+B stays an ordinary volley',spell=false,enemy=false},
    {name='METEOR shockwave kills floor Bot',spell=true,enemy=true},
}
local st
local function setupPhase()
    emu.loadSavestate(base)
    local p=phases[phase]
    age=0
    st={dived=false,diveVy=true,landAge=nil,landY=nil,placed={},
        waveY={},maxDx=0,killed=false,startX=nil,groundY=r(0x29)}
    for s=0,5 do if r(0xB6+s)==1 and r(0xA1+s)~=0x02 then w(0xB6+s,0) end end
    for _,a in ipairs({0x5F1,0x5F7,0x5F8,0x5FC,0x5FD,0x5FE,0x5FF,0x8D,0x8E})do w(a,0)end
    w(0x6400,0);w(0x6410,0);w(0x6420,0);w(METEOR_STATE,0)
    w(0x76F,p.spell and 0x10 or 0)
    w(0x774,255);w(0x0518,0);w(0x050C,0)
    w(0x5F,1);w(0x9F,1);w(0x70,0)
end
local function liveWaves()
    local out={}
    for s=0,1 do
        local v=r(0x8D+s)
        if v>0 and v<0x80 and (r(0x5FC+s)&0xC0)==0xC0 then
            out[#out+1]={y=r(0x36+s),x=r(0x5A+s)+256*r(0x48+s)}
        end
    end
    for b=0x6400,0x6420,0x10 do
        local v=r(b)
        if v>0 and v<0x80 and (r(b+9)&0xC0)==0xC0 then
            out[#out+1]={y=r(b+1),x=r(b+2)+256*r(b+3)}
        end
    end
    return out
end
local function finish()
    local p=phases[phase]
    local info=string.format('(land=%s y0=%d landY=%s placed=%d)',
        tostring(st.landAge),st.groundY,tostring(st.landY),#st.placed)
    if p.spell then
        check(st.dived,p.name..': Down+B in mid-air starts the dive '..info)
        check(st.diveVy,p.name..': dive holds fall speed at the native cap (6)')
        check(st.landAge~=nil,p.name..': dive lands '..info)
        local dirs,flat,cls,yok={},true,true,true
        for _,s in ipairs(st.placed)do
            dirs[s.dir]=true
            if (s.flags&0xC0)~=0xC0 then flat=false end
            if s.class~=0 then cls=false end
            if st.landY and s.y~=(st.landY+0x12)%256 then yok=false end
        end
        check(#st.placed==2 and dirs[1] and dirs[2],p.name..': landing emits one wave each way '..info)
        check(flat and cls,p.name..': waves carry the flat flag and fire class')
        check(yok,p.name..': waves start at floor level ($29+$12)')
        check(#st.waveY>0,p.name..': waves still live 20 frames after landing')
        local still=true
        for _,y in ipairs(st.waveY)do if st.landY and y~=(st.landY+0x12)%256 then still=false end end
        check(still,p.name..': waves stay flat (no vertical drift)')
        check(st.maxDx>=36,p.name..': waves travel along the floor, dx='..st.maxDx)
        if p.enemy then check(st.killed,p.name..': floor Bot hit by the shockwave') end
        check(r(METEOR_STATE)==0,p.name..': dive state clears after landing')
    else
        check(not st.dived,p.name..': no dive without the spell')
        local ordinary=#st.placed>0
        for _,s in ipairs(st.placed)do
            if (s.flags&0xC0)==0xC0 or s.class~=0 then ordinary=false end
        end
        check(ordinary,p.name..': B emitted ordinary fire-class volley shots '..info)
    end
    check(r(0x736)==11 and r(0xB5)==1,p.name..': still alive in side view')
end

assert(LABELS and LABELS.BarbaVolleyPlaced,'build must export BarbaVolleyPlaced')
emu.addMemoryCallback(function()
    if phase==0 or not phases[phase] or base==nil then return end
    local s=emu.getState()
    if (s['mapper.prgReg'] or ((s['mapper.registers6'] or -1)//2))~=0 then return end
    local x=s['cpu.x'];if x>1 then return end
    st.placed[#st.placed+1]={dir=r(0x6D+x),flags=r(0x5FC+x),y=r(0x36+x),class=r(0x5CA+x)}
    f:write(string.format('PLACED age=%d slot=%d dir=%d flags=%02X y=%d class=%02X\n',
        age,x,r(0x6D+x),r(0x5FC+x),r(0x36+x),r(0x5CA+x)));f:flush()
end,emu.callbackType.exec,LABELS.BarbaVolleyPlaced)

emu.addEventCallback(function()
    local buttons=newGameInput(frame)
    if base and phases[phase] then
        local landed=st.landAge~=nil
        buttons={start=false,select=false,a=false,b=(age==8),
            up=false,down=(age>=4 and not landed),left=false,right=false}
    end
    emu.setInput(buttons,0)
end,emu.eventType.inputPolled)

emu.addMemoryCallback(function()
    if not pending then return end
    pending=false
    if not base then base=emu.createSavestate() end
    if phase>0 then finish() end
    phase=phase+1
    if not phases[phase] then
        f:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..'\n');f:close()
        stopScenario(errors==0 and 0 or 1);return
    end
    setupPhase()
end,emu.callbackType.exec,0xC07B)

emu.addEventCallback(function()
    frame=frame+1
    if not base then
        if frame==1000 then
            w(0x707,3);w(0x706,0);w(0x769,3);w(0x561,5)
            w(0x701,0);w(0x75C,0);w(0x704,0);w(0x736,0);w(0x73D,0);w(0x726,1)
        end
        if frame==1150 then pending=true end
        return
    end
    if pending or not phases[phase] then return end
    age=age+1
    local p=phases[phase]
    if age==2 then
        w(0x4D,r(0x4D)+64)  -- room to show both waves
        st.startX=r(0x4D)+256*r(0x3B)
        f:write(string.format('BEGIN %s y=%d air=%d x=%d\n',p.name,r(0x29),r(0x479),st.startX));f:flush()
        if p.enemy then
            local s=1
            w(0xB6+s,1);w(0xA1+s,0x04);w(0xC2+s,8);w(0x040E+s,0);w(0x71+s,0)
            w(0xA8+s,0);w(0x19+s+1,1);w(0x444+s,0)
            local ex=r(0x4D)+56
            w(0x4E+s,ex%256);w(0x3C+s,r(0x3B)+(ex>=256 and 1 or 0));w(0x2A+s,(st.groundY+16)%256)
        end
        -- Launch Barba 48 px up, falling.
        w(0x29,st.groundY-48);w(0x479,1);w(0x57D,0)
    end
    if age>2 and p.enemy and (r(0xB6+1)~=1 or r(0xC2+1)<8 or r(0x40E+1)>0) then st.killed=true end
    if r(METEOR_STATE)~=0 then
        st.dived=true
        if r(0x479)~=0 and age>10 and r(0x57D)~=6 then st.diveVy=false end
    end
    if age>8 and not st.landAge and r(0x479)==0 then
        st.landAge=age;st.landY=r(0x29)
    end
    if st.landAge and age==st.landAge+6 then screenshot('meteor-'..phase) end
    if st.landAge and age==st.landAge+20 then
        for _,wv in ipairs(liveWaves())do
            st.waveY[#st.waveY+1]=wv.y
            local dx=math.abs(wv.x-st.startX)
            if dx>st.maxDx then st.maxDx=dx end
        end
    end
    if age==90 then pending=true end
end,emu.eventType.endFrame)
