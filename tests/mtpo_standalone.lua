-- Mesen headless verification for Barba's Punch-Out!! standalone ROM (Mapper 176)

local frame = 0
local pass_count = 0
local fail_count = 0
local current_inp = {}

local function log_pass(msg)
  pass_count = pass_count + 1
  print("PASS: " .. msg)
end

local function log_fail(msg)
  fail_count = fail_count + 1
  print("FAIL: " .. msg)
end

local function save_shot(name)
  local png = emu.takeScreenshot()
  local f = assert(io.open(OUTPUT_DIR .. "/scratch/" .. name, "wb"))
  f:write(png)
  f:close()
end

local function screen_nonzero()
  local buf = emu.getScreenBuffer()
  local first = buf[1]
  for i = 2, #buf, 64 do
    if buf[i] ~= first then
      return true
    end
  end
  return false
end

local seeded = false
local saw_intro = false
local title_first_frame = nil
local saw_title = false
local tape_first_frame = nil
local saw_tape = false
local saw_fight = false
local saw_punched = false
local saw_roar_dmc = false
local saw_quit_restore = false
local saw_win_restore = false

local phase = "boot"
local phase_frame = 0
local fight_active_frames = 0
local restore_pc = 0xFF90
local start_select_hold = 0
local dmc_e2_hits = 0

emu.addMemoryCallback(function(addr, value)
  if value == 0xE2 then
    dmc_e2_hits = dmc_e2_hits + 1
    saw_roar_dmc = true
  end
end, emu.callbackType.write, 0x4012)

emu.addMemoryCallback(function()
  if phase == "quit_hold" then
    saw_quit_restore = true
    local reward = emu.read(0x63BA, emu.memType.nesMemory)
    if reward == 0 then
      log_pass("Start+Select 60-frame exit hit $FF90 without setting $63BA")
    else
      log_fail(string.format("Start+Select exit left $63BA = $%02X", reward))
    end
    phase = "win_test"
    phase_frame = 0
    emu.write(0xA001, 0xA3, emu.memType.nesMemory)
    emu.write(0x7FFF, 0x00, emu.memType.nesMemory)
    -- Restore R7 = 29 (MTPO Bank 13 at $A000-$BFFF) before jumping to $AC6C
    emu.write(0x8000, 0x07, emu.memType.nesMemory)
    emu.write(0x8001, 29, emu.memType.nesMemory)
    local state = emu.getState()
    state["cpu.pc"] = 0xAC6C
    emu.setState(state)
  elseif phase == "win_test" then
    saw_win_restore = true
    local reward = emu.read(0x63BA, emu.memType.nesMemory)
    if reward ~= 0 then
      log_pass(string.format("Win hook $AC6C set $63BA = $%02X and reached $FF90", reward))
    else
      log_fail("Win hook did not set $63BA in WRAM bank 0")
    end
    phase = "done"
  end
end, emu.callbackType.exec, restore_pc)

emu.addEventCallback(function()
  emu.setInput(current_inp, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
  frame = frame + 1
  phase_frame = phase_frame + 1

  if not seeded then
    seeded = true
    for i = 0, 7 do
      emu.write(0x7FF0 + i, 0x37 + i * 17, emu.memType.nesMemory)
    end
  end

  current_inp = {}

  if phase == "boot" then
    if frame == 250 then
      local rng = emu.read(0x18, emu.memType.nesMemory)
      if rng ~= 0 then
        log_pass(string.format("RNG seeded ($18=$%02X)", rng))
      else
        log_fail("RNG $18 remained 0")
      end
      if screen_nonzero() then
        saw_intro = true
        save_shot("mtpo_intro.png")
        log_pass("Intro screen rendered")
      else
        log_fail("Intro screen blank")
      end
      phase = "to_tape"
      phase_frame = 0
    end

  elseif phase == "to_tape" then
    if (phase_frame % 40) < 4 then
      current_inp.start = true
    end
    local vmode = emu.read(0x7F81, emu.memType.nesMemory)
    local ppu11 = emu.read(0x11, emu.memType.nesMemory)
    if vmode == 1 and (ppu11 & 0x18) == 0x18 and not title_first_frame then
      title_first_frame = frame
    end
    if title_first_frame and not saw_title and frame >= title_first_frame + 35 then
      saw_title = true
      save_shot("mtpo_title.png")
      log_pass("Title screen rendered (V_MODE=1)")
    end
    if vmode == 3 and (ppu11 & 0x18) == 0x18 and not tape_first_frame then
      tape_first_frame = frame
    end
    if tape_first_frame and not saw_tape and frame >= tape_first_frame + 35 then
      saw_tape = true
      save_shot("mtpo_tape.png")
      log_pass("Tale of the Tape rendered (V_MODE=3)")
    end
    local mode1d = emu.read(0x1D, emu.memType.nesMemory)
    if mode1d == 0 and (ppu11 & 0x18) == 0x18 and phase_frame > 60 then
      saw_fight = true
      phase = "fight"
      phase_frame = 0
      log_pass("Entered Fight mode ($1D == 0)")
    elseif phase_frame > 1300 then
      log_fail(string.format("Timed out waiting for Fight mode (V_MODE=%d, $1D=%02X, $11=%02X)", vmode, mode1d, ppu11))
      phase = "quit_hold"
      phase_frame = 0
    end

  elseif phase == "fight" then
    -- Wait until walk-in ends and Round 1 active fight starts ($51 == 0x00 and $048D == 0x16 Barba crimson)
    local m51 = emu.read(0x51, emu.memType.nesMemory)
    local c_barba = emu.read(0x048D, emu.memType.nesMemory)
    if (m51 == 0x00 or c_barba == 0x16) and not saw_punched then
      fight_active_frames = fight_active_frames + 1
      if fight_active_frames == 20 then
        if c_barba == 0x16 then
          log_pass("Barba crimson fight palette ($048D=$16) active")
        else
          log_fail(string.format("Unexpected Barba palette $048D=$%02X", c_barba))
        end
        save_shot("mtpo_fight_idle.png")
      end
      if fight_active_frames >= 30 and fight_active_frames <= 55 then
        current_inp.a = true
        current_inp.up = true
      end
      if fight_active_frames == 38 then
        save_shot("mtpo_fight_punch.png")
        saw_punched = true
        log_pass("Captured active Barba fight idle & punch frames")
        if saw_roar_dmc then
          log_pass(string.format("Barba sampled roar DPCM ($4012=$E2) triggered (%d hits)", dmc_e2_hits))
        else
          log_fail("Barba sampled roar DPCM ($4012=$E2) did not trigger")
        end
        phase = "quit_hold"
        phase_frame = 0
        start_select_hold = 0
      end
    elseif phase_frame > 1300 then
      log_fail(string.format("Timed out waiting for Round 1 active fight ($51=$%02X, $048D=$%02X)", m51, c_barba))
      phase = "quit_hold"
      phase_frame = 0
      start_select_hold = 0
    end

  elseif phase == "quit_hold" then
    current_inp.start = true
    current_inp.select = true
    start_select_hold = start_select_hold + 1
    if start_select_hold == 58 then
      if saw_quit_restore then
        log_fail("Start+Select exited before 60 frames")
      else
        log_pass("Start+Select 58-frame hold stayed inside game (debounce working)")
      end
    end
    if phase_frame > 90 and not saw_quit_restore then
      log_fail("Start+Select 60-frame hold did not trigger exit trampoline")
      phase = "done"
    end

  elseif phase == "win_test" then
    if phase_frame > 20 and not saw_win_restore then
      log_fail("Win hook $AC6C did not reach restore_addr")
      phase = "done"
    end

  elseif phase == "done" then
    print(string.format("SUMMARY: pass=%d fail=%d", pass_count, fail_count))
    if fail_count == 0 then
      print("RESULT: PASS")
    else
      print("RESULT: FAIL")
    end
    local stop = emu.exit or emu.stop
    stop(fail_count == 0 and 0 or 1)
    return
  end

  if frame > 2800 then
    log_fail("Global timeout reached")
    print("RESULT: FAIL")
    local stop = emu.exit or emu.stop
    stop(1)
  end
end, emu.eventType.endFrame)
