-- Generate F1-F10 save states for standalone Family Feud: Barba Edition (play/feud-barba.nes).
local ALL_MAIN = {
    [0]={'HORSE HEAD','HELMET HEAD','REBONACK','CAROCK','GOOMA','BARBA','THUNDER BIRD','DARK LINK'},
    [1]={'CANDLE','GLOVE','RAFT','BOOTS','FLUTE','CROSS','HAMMER','MAGIC KEY'},
    [2]={'SHIELD','JUMP','LIFE','FAIRY','FIRE','REFLECT','SPELL','THUNDER'},
    [3]={'SWORD','DOWN STAB','UP STAB','BEAM','FIREBALL','THUNDER'},
    [4]={'PARAPA PALACE','MIDORO PALACE','ISLAND PALACE','MAZE PALACE','OCEAN PALACE','THREE-EYE ROCK','GREAT PALACE'},
    [5]={'RAURU','RUTO','SARIA','MIDO','NABOORU','DARUNIA','NEW KASUTO','OLD KASUTO'},
    [6]={'200','500','1000','2000','3000','5000','8000'},
    [7]={'100','300','700','1200','2200','3500','6000'},
    [8]={'50','150','400','800','1500','2500','4000'},
    [9]={'STALFOS','IRON KNUCKLE','BOT','BIT','BUBBLE','RA'},
    [10]={'IRON KNUCKLE','STALFOS','GORIYA','DOOM KNOCKER','MAU','BUBBLE'},
    [11]={'WIZZROBE','MAGO','IRON KNUCKLE','STALFOS','BUBBLE','MOA'},
    [12]={'FOKKA','FOKKERU','BUBBLE','BOT','THUNDER BIRD','DARK LINK'},
    [13]={'DARIA','TEKTITE','OCTOROK','GORIYA','BUBBLE'},
    [14]={'GRASS','SWAMP','DESERT','FOREST','GRAVEYARD','LAVA'},
    [15]={'HEALER','ERROR','SAGE','BAGU','KNIGHT','CHIMNEY'},
    [16]={'RAFT','BOOTS','FAIRY SPELL','BRIDGE'},
    [17]={'P-BAG','RED MAGIC JAR','BLUE MAGIC JAR','KEY'},
    [18]={'FAIRY','LIFE SPELL','TOWN LADY','LEVEL UP','RED MAGIC JAR'},
    [19]={'THUNDER BIRD','DARK LINK','OLD MAN'},
    [20]={'CAVE','WATER','DESERT','SWAMP','TOWN'},
    [21]={'DEATH MOUNTAIN','CAVE','RAURU','MAZE ISLAND','OLD KASUTO'},
    [22]={'ATTACK','MAGIC','LIFE'},
    [23]={'LINK','ZELDA','BARBA','ERROR','GANON','BAGU','IMPA'},
    [24]={'ROAD','BRIDGE','CAVE','TOWN','PALACE','RIVER'},
    [25]={'COURAGE','POWER','WISDOM'},
    [26]={'SHIELD','JUMP','LIFE','FAIRY'},
    [27]={'FIRE','REFLECT','SPELL','THUNDER'},
    [28]={'FAIRY','FOKKA','THUNDER BIRD','FOKKERU','ACHE','MOA'},
    [29]={'HEAL','LEARN SPELL','MAGIC','TALK','QUEST'},
    [30]={'P-BAG','KILL ENEMIES','PALACE CRYSTAL','BOSS'},
    [31]={'IRON KNUCKLE','STALFOS','REBONACK','FOKKA','DOOM KNOCKER'},
    [32]={'ROCK','TREE','SPECTACLE ROCK'},
    [33]={'GELDARM','LEEVER','MOBLIN','OCTOROK','BOT'},
    [34]={'THUNDER','FAIRY','SPELL','LIFE'},
}
local FM_ANS1 = {
    [0]='SCALES', [1]='200', [2]='ORANGE', [3]='TROPHY', [4]='LIFE',
    [5]='MOBLIN', [6]='WEST HYRULE', [7]='DOLL', [8]='RED', [9]='LAVA',
    [10]='LIFE', [11]='BARBA', [12]='GANON', [13]='ROCK', [14]='SPELL',
    [15]='PARAPA PALACE', [16]='NABOORU', [17]='8', [18]='SIGNS', [19]='ERROR',
    [20]='FORWARD', [21]='BARBA', [22]='BARBA', [23]='RED', [24]='LIFE',
    [25]='TEKTITE', [26]='PIT',
}
local FM_ANS2 = {
    [0]='METEOR', [1]='100', [2]='RED', [3]='MIRROR', [4]='MAGIC',
    [5]='OCTOROK', [6]='EAST HYRULE', [7]='XP', [8]='BLUE', [9]='WATER',
    [10]='MAGIC', [11]='LAVA', [12]='LINK', [13]='FIRE', [14]='UP STAB',
    [15]='RAURU', [16]='DARUNIA', [17]='9', [18]='VILLAGERS', [19]='BAGU',
    [20]='DOWN', [21]='LAVA', [22]='CAROCK', [23]='BLUE', [24]='MAGIC',
    [25]='BOT', [26]='LAVA',
}

local f = 0
local inp = {}
local done = {}
local pending_id = nil
local pending_f = 0
local submit_cool = 0
local ans_cursor = 1
local last_q = -1
local fm_q_seen = 0
local last_fm_f = -100
local phase = 1  -- 1=F1..F8 ($5k), 2=Game2 ($20k limit F9), 3=Game3 (lose F10)
local p2_base = 0
local p3_base = 0

local function rd(a) return emu.read(a, emu.memType.nesMemory) end
local function wr(a, v) emu.write(a, v, emu.memType.nesMemory) end

local function saveStateAndShot(id)
    local data = emu.createSavestate()
    local sf = assert(io.open(PACK_DIR .. '/' .. id .. '.mss', 'wb'))
    sf:write(data); sf:close()
    local png = emu.takeScreenshot()
    local pf = assert(io.open(PACK_DIR .. '/' .. id .. '.png', 'wb'))
    pf:write(png); pf:close()
end

local function queueCap(id, delay)
    if done[id] or pending_id then return end
    done[id] = true
    pending_id = id
    pending_f = f + (delay or 0)
end

local function submitText(txt)
    for i = 1, #txt do wr(0x0360 + i - 1, string.byte(txt, i)) end
    wr(0x0360 + #txt, 0); wr(0x035F, #txt); wr(0x0347, 8); wr(0x0348, 7); submit_cool = 12
end

emu.addMemoryCallback(function()
    if pending_id and f >= pending_f then
        local id = pending_id; pending_id = nil
        saveStateAndShot(id)
    end
end, emu.callbackType.exec, 0xCA77, 0xCA77)

emu.addEventCallback(function() emu.setInput(inp, 0) end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    f = f + 1
    inp = {}

    local scr = rd(0x0345)
    local mode = rd(0x04D3)
    local kbd = rd(0x035E)
    local fms = rd(0x04E2)
    local q = rd(0x0317)
    if q ~= last_q then last_q = q; ans_cursor = 1 end

    if submit_cool > 0 then
        submit_cool = submit_cool - 1
        if submit_cool >= 8 and submit_cool <= 10 then inp = {a = true} end
        return
    end

    if scr == 0x01 then
        if phase == 1 and f > 220 then queueCap('title', 10) end
        if (phase > 1 or (done['title'] and not pending_id)) and f % 20 == 0 then inp = {start = true} end
        return
    end

    if phase == 1 and f <= 520 then
        if f % 40 == 0 then inp = {start = true} end
        return
    elseif phase == 2 and p2_base > 0 and f <= p2_base + 180 then
        if f % 35 == 0 then inp = {start = true} end
        return
    elseif phase == 3 and p3_base > 0 and f <= p3_base + 180 then
        if f % 35 == 0 then inp = {start = true} end
        return
    end

    if scr == 0x05 then
        if f % 14 < 2 then inp = {a = true} end
        return
    end

    if scr == 0x06 and mode == 1 then
        if phase == 1 and f > 2140 then queueCap('overview', 25) end
        if (phase > 1 or (done['overview'] and not pending_id)) and f % 20 == 0 then inp = {a = true} end
        return
    end

    if scr == 0x09 and mode == 2 then
        if phase == 1 and f > 2450 then queueCap('faceoff', 45) end
        if (phase > 1 or (done['faceoff'] and not pending_id)) and kbd == 0 and f % 12 == 0 then inp = {a = true} end
        if kbd == 1 then submitText(phase == 3 and 'ZZZZ' or ALL_MAIN[q][1]) end
        return
    end

    if scr == 0x0D and mode == 0 and fms == 0 then
        if phase == 1 and f > 3000 then
            queueCap('stage_barba', 30)
            if kbd == 1 and not pending_id then
                if not done['stage_z2'] then
                    submitText('ZZZZ')
                else
                    wr(0x04C3, 0x2C); wr(0x04C4, 0x01)
                    local lst = ALL_MAIN[q]; local a = lst[ans_cursor] or lst[1]; ans_cursor = ans_cursor + 1
                    submitText(a)
                end
            elseif f % 16 == 0 then inp = {a = true} end
        elseif phase == 2 then
            if kbd == 1 then
                wr(0x04C3, 0x2C); wr(0x04C4, 0x01)
                local lst = ALL_MAIN[q]; local a = lst[ans_cursor] or lst[1]; ans_cursor = ans_cursor + 1
                submitText(a)
            elseif f % 16 == 0 then inp = {a = true} end
        elseif phase == 3 then
            wr(0x04C5, 0x2C); wr(0x04C6, 0x01)
            if kbd == 1 then submitText('ZZZZ') elseif f % 16 == 0 then inp = {a = true} end
        elseif f % 16 == 0 then inp = {a = true} end
        return
    end

    if scr == 0x0E and mode == 0 then
        if phase == 1 and f > 3200 then queueCap('stage_z2', 30) end
        if phase == 3 then wr(0x04C5, 0x2C); wr(0x04C6, 0x01) end
        if kbd == 1 and not pending_id then submitText('ZZZZ')
        elseif f % 16 == 0 then inp = {a = true} end
        return
    end

    if fms == 1 and scr ~= 0x03 then
        if phase == 1 then queueCap('pre_fast_money', 12) end
        if not pending_id and f % 25 == 0 then inp = {a = true} end
        return
    end

    if mode == 3 and scr == 0x03 then
        if phase == 1 and kbd == 1 then queueCap('fast_money', 10) end
        if phase == 2 and rd(0x0314) < 0x3A then
            wr(0x08, 0); wr(0x0313, 0x98); wr(0x0314, 0x3A)
        end
        if kbd == 1 and not pending_id then
            if f - last_fm_f > 25 then fm_q_seen = fm_q_seen + 1; last_fm_f = f end
            local is_p2 = (fm_q_seen > 5)
            if is_p2 then wr(0x04C7, 210); wr(0x04C8, 0) end
            local tbl = is_p2 and FM_ANS2 or FM_ANS1
            submitText(tbl[rd(0x031B)] or 'BARBA')
        elseif f % 20 == 0 then inp = {a = true} end
        return
    end

    if scr == 0x0B and phase == 1 then
        queueCap('after_fast_money', 35)
        if done['after_fast_money'] and not pending_id then
            wr(0x28, 1)
            if f % 20 == 0 then inp = {start = true} end
        end
        return
    elseif scr == 0x12 then
        if phase == 1 and done['after_fast_money'] then
            phase = 2; p2_base = f; fm_q_seen = 0; last_fm_f = -100
        end
        if f % 16 < 3 then inp = {start = true} end
        return
    end

    if scr == 0x0C and phase == 2 then
        queueCap('limit_20k', 35)
        if done['limit_20k'] and not pending_id then
            phase = 3; p3_base = f
            wr(0x28, 1)
            if f % 20 == 0 then inp = {start = true} end
        end
        return
    end

    if scr == 0x0F and phase == 3 then
        queueCap('lose_msg', 35)
        if done['lose_msg'] and not pending_id then emu.stop(0) end
        return
    end

    if f % 20 == 0 then inp = {a = true} end
    if f >= 45000 then emu.stop(1) end
end, emu.eventType.endFrame)
