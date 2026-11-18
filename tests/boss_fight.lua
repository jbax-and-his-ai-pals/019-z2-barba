-- Shared palace boss fight driver. Use reflect=true to fight with reflected bolts.
-- Warps to a palace boss room with Downward/Upward Thrust removed, then walks in,
-- keeps ~28px from the boss, hops and breathes. Other enemies (not doors, keys or
-- the boss phases) are cleared so the fight stays deterministic. After the boss
-- dies it walks to the dropped key and on through the door.
-- cfg: name, world, region, number, room, page, kind, bosses={[id]=true}, final=id (last phase),
--      attack, frames, exitPage, p56C (palace 6 = 1), checks(check,fight)
dofile(TEST_DIR..'/newgame.lua')
function runBossFight(cfg)
    local mem=emu.memType.nesMemory
    local function r(a)return emu.read(a,mem)end
    local function w(a,v)emu.write(a,v,mem)end
    local report=assert(io.open(OUTPUT_DIR..'/'..cfg.name..'.txt','w'))
    local errors=0
    local function check(ok,message)
        report:write((ok and 'PASS ' or 'FAIL ')..message..string.char(10))
        if not ok then errors=errors+1 end
    end
    local frame=0
    local fight={damage={},seen={},hits=0,fireHits=0,reflectHits=0,stabSeen=false,
        sawBossShadow=false,bossShadowTall=true}
    local target,defeatedAt,keyAt=nil,nil,nil
    local fcAtDefeat=nil
    local lastHp={}
    emu.addMemoryCallback(function()
        if frame>1100 and (r(0xC9)&0xF0)==0 and r(0x0754)==0 then
            local py=r(0x29)
            local p=r(0x80)
            if py>=0x30 and py<0xE0 and (p~=6 and p~=7 or r(0x0479)~=0) then
                fight.sawBossShadow=true
                if r(0x0270)~=(py-0x10) or r(0x0254)~=py or r(0x0260)~=(py+0x10)
                    or (r(0x0256)&3)~=2 or (r(0x0272)&3)~=2 then
                    fight.bossShadowTall=false
                end
            end
        end
    end,emu.callbackType.exec,0xDD1E)
    -- Observe the native HP store directly so lethal hits count even when HP underflows.
    emu.addMemoryCallback(function()
        local state=emu.getState()
        local slot=state['cpu.x']
        if frame>1100 and slot<6 and r(0xB6+slot)==1 and cfg.bosses[r(0xA1+slot)] then
            fight.hits=fight.hits+1
            local sp=state['cpu.sp']
            for i=1,10 do
                local lo,hi=r(0x100+((sp+i)%256)),r(0x100+((sp+i+1)%256))
                if hi==0xE4 and lo==0xAA then fight.fireHits=fight.fireHits+1;break end
                if hi==0xAD and lo==0x6D then fight.reflectHits=fight.reflectHits+1;break end
            end
            if r(0x80)==0x09 then fight.stabSeen=true end
        end
    end,emu.callbackType.exec,0xE735)

    emu.addEventCallback(function()
        local b=newGameInput(frame)
        if frame>1150 then
            b={start=false,select=false,a=false,b=false,up=false,down=false,left=false,right=false}
            local px=r(0x3B)*256+r(0x4D)
            if target then
                local bx=r(0x3C+target)*256+r(0x4E+target)
                if bx<px-96 then b.left=true
                elseif bx>px+96 then b.right=true
                elseif bx<px-28 then b.left=(frame%6<4)
                elseif bx>px+28 then b.right=(frame%6<4)
                elseif bx<px and r(0x9F)~=2 and frame%40==0 then b.left=true
                elseif bx>px and r(0x9F)~=1 and frame%40==0 then b.right=true end
                b.a=not cfg.reflect and (frame%90<25)
                b.b=not cfg.reflect and (frame%10<3)
                b.down=cfg.reflect and r(0x728)~=0 and not (b.left or b.right)
            elseif defeatedAt then
                local key=nil
                for s=0,5 do if r(0xB6+s)>0 and r(0xA1+s)==0x01 then key=s end end
                if key then
                    local kx=r(0x3C+key)*256+r(0x4E+key)
                    b.left=kx<px-4;b.right=kx>px+4
                else b.right=true end
                b.a=(frame%40<20)                      -- hop out of pits/lava onto ledges
            else
                b.right=true
            end
        end
        emu.setInput(b,0)
    end,emu.eventType.inputPolled)

    emu.addEventCallback(function()
        frame=frame+1
        if frame==1000 then
            w(0x700,9)
            w(0x777,cfg.attack);w(0x778,8);w(0x779,8)
            w(0x783,8);w(0x784,8);w(0x773,255);w(0x774,255)
            for a=0x77B,0x782 do w(a,1)end
            for a=0x785,0x78C do w(a,1)end
            w(0x793,0);w(0x796,0)                  -- no keys; no Downward/Upward Thrust
            w(0x76F,0);w(0x749,0);w(0x74A,0)
            w(0x770,0xFF);w(0x771,0xFF)
            w(0x707,cfg.world);w(0x706,cfg.region);w(0x769,cfg.kind)
            w(0x561,cfg.room);w(0x568,cfg.number-1);w(0x56B,cfg.number);w(0x56C,cfg.p56C or 0)
            w(0x701,0);w(0x75C,cfg.page);w(0x704,0)
            w(0x736,0);w(0x73D,0);w(0x726,1)
        end
        if frame>1100 then
            if frame%30==0 then w(0x774,255);w(0x773,255) end
            local best=nil
            for s=0,5 do
                if r(0xB6+s)>0 then
                    local id=r(0xA1+s)
                    if cfg.bosses[id] then
                        if r(0xB6+s)==1 then best=s end
                        fight.seen[id]=true
                        local hp=r(0xC2+s)
                        local k=s..':'..id
                        if lastHp[k] and hp<lastHp[k] and lastHp[k]<0xF0 then
                            fight.damage[id]=(fight.damage[id] or 0)+(lastHp[k]-hp)
                        end
                        lastHp[k]=hp
                    elseif id~=0x01 and id~=0x02 and frame%30==0 then
                        w(0xB6+s,0)
                    end
                end
            end
            target=best
            if target and cfg.reflect and not defeatedAt then w(0x710,1) end
            local finalAlive=false
            for s=0,5 do if r(0xB6+s)==1 and r(0xA1+s)==cfg.final then finalAlive=true end end
            if fight.seen[cfg.final] and not finalAlive and not defeatedAt then
                defeatedAt=frame;fcAtDefeat=r(0x12)
            end
            if defeatedAt and frame==defeatedAt+30 then fight.running=(r(0x12)~=fcAtDefeat) end
            if defeatedAt and not keyAt and r(0x728)==0 then keyAt=frame end
        end
        if fight.reported then return end
        local finished=keyAt and r(0x3B)>=cfg.exitPage
        if finished or frame==1100+cfg.frames then
            fight.reported=true
            local ids={}
            local objs=''
            for s=0,5 do if r(0xB6+s)>0 then objs=objs..string.format(' %d:%02X/b6=%d/x%d/y%d',s,r(0xA1+s),r(0xB6+s),r(0x3C+s)*256+r(0x4E+s),r(0x2A+s)) end end
            report:write(string.format('end px=%d py=%d 728=%d keys=%d objs=%s',r(0x3B)*256+r(0x4D),r(0x29),r(0x728),r(0x793),objs)..string.char(10))
            screenshot(cfg.name..'_end')
            for id in pairs(fight.seen) do ids[#ids+1]=string.format('%02X:%d',id,fight.damage[id] or 0) end
            report:write(string.format('frame=%d defeated=%s keyUnfreeze=%s page=%d hits=%d fireHits=%d reflectHits=%d bosses=%s',
                frame,tostring(defeatedAt),tostring(keyAt),r(0x3B),fight.hits,fight.fireHits,fight.reflectHits,table.concat(ids,' '))..string.char(10))
            cfg.checks(check,fight)
            check(r(0x796)==0 and not fight.stabSeen,'no Downward Thrust available or used')
            if cfg.reflect then
                check(fight.hits>0 and fight.reflectHits==fight.hits,'every boss hit came from a reflected bolt')
            else
                check(fight.hits>0 and fight.fireHits==fight.hits,'every boss hit came from a fireball')
            end
            check(defeatedAt~=nil,'boss defeated')
            check(fight.running==true,'game keeps running after the kill (no NMI hang)')
            check(fight.sawBossShadow and fight.bossShadowTall,
                'boss-defeat shadow renders 48px tall with two torso chunks and black palette 2')
            check(keyAt~=nil,'boss key collected; scroll lock released ($0728 = 0)')
            check(r(0x3B)>=cfg.exitPage,'walked through the locked door past the boss')
            report:write('RESULT '..(errors==0 and 'PASS' or 'FAIL')..string.char(10))
            report:close()
            stopScenario(errors==0 and 0 or 1)
        end
    end,emu.eventType.endFrame)
end
