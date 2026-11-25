(() => {
  const data = window.FEUD_CAST_DATA;
  if (!data) return;

  const NES_PAL = data.nes_palette;
  const WALL_RGB = NES_PAL[0x16];
  const USABLE_ROWS = [
    [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C],
    [0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1C],
    [0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x2B, 0x2C],
    [0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x3B, 0x3C],
  ];
  const Z2_PRESETS = {
    Std: '312',
    Dress: '321',
    Robe: '211',
    Enemy: '213',
  };
  const MAP_VAL_LABELS = { '0': 'bg', '1': 'c1', '2': 'c2', '3': 'blk' };

  const cloneCfg = obj => {
    const copy = JSON.parse(JSON.stringify(obj));
    for (const c of copy.characters || []) {
      c.sprite_type = c.sprite_type === 'top_half' ? 'top_half' : 'full';
    }
    return copy;
  };
  let cfg = cloneCfg(data.config);

  const spritesById = Object.fromEntries(data.sprites.map(s => [s.id, s]));
  const charById = () => Object.fromEntries(cfg.characters.map(c => [c.id, c]));

  const ui = {
    stagePool: 'z2',
    palPool: 'z2',
    varIdx: 0,
    poseMode: 'animate',
    filterPool: 'all',
    filterStatus: 'all',
    filterType: 'all',
    backdrop: 'stage',
    zoom: 3,
    highlightId: null,
    editingPal: null, // { pool, slot, varIdx, colorIdx }
    stageSeats: { z2: [], barba: [] },
    animFrame: 0,
    animSeat: -1,
    animPose: 0,
  };

  // Load real podium stage backdrop
  const stageBgImg = new Image();
  let stageBgReady = false;
  if (data.has_stage_bg) {
    stageBgImg.onload = () => {
      stageBgReady = true;
      renderStage();
    };
    stageBgImg.src = 'previews/feud_stage_bg.png';
  }

  const hex2 = n => '$' + n.toString(16).toUpperCase().padStart(2, '0');
  const rgbCss = idx => {
    const [r, g, b] = NES_PAL[idx & 0x3F];
    return `rgb(${r},${g},${b})`;
  };
  const lum = idx => {
    const [r, g, b] = NES_PAL[idx & 0x3F];
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const textOn = idx => (lum(idx) > 132 ? '#111' : '#f4f6fa');

  const setToast = (msg, isWarn = false) => {
    const el = document.getElementById('feud-toast');
    el.textContent = msg;
    el.style.color = isWarn ? 'var(--amber)' : 'var(--green)';
  };

  // Compile one 32x48 frame (1536 chars '0'..'3') matching tools/feud_cast.py
  function compileFrame(spr, ch, frameIdx) {
    const isTop = ch.sprite_type === 'top_half';
    const frames = (isTop && spr.raw_frames_top) ? spr.raw_frames_top : spr.raw_frames;
    const raw = frames[frameIdx] || frames[0];
    if (spr.pool === 'barba') return raw;

    const mapStr = ch.mapping || '312';
    const mapArr = ['0', mapStr[0], mapStr[1], mapStr[2]];
    const mapped = new Uint8Array(32 * 48);
    for (let i = 0; i < 1536; i++) {
      mapped[i] = Number(mapArr[Number(raw[i])]);
    }

    let out = mapped;
    if (ch.outline !== false) {
      out = new Uint8Array(mapped);
      for (let y = 0; y < 47; y++) {
        const rowOff = y * 32;
        for (let x = 0; x < 32; x++) {
          const p = rowOff + x;
          if (mapped[p] === 0) {
            if (
              (y > 0 && mapped[p - 32] !== 0) ||
              (y < 47 && mapped[p + 32] !== 0) ||
              (x > 0 && mapped[p - 1] !== 0) ||
              (x < 31 && mapped[p + 1] !== 0)
            ) {
              out[p] = 3;
            }
          }
        }
      }
    }

    const yKeeps = isTop ? (spr.y_keeps_top || spr.y_keeps) : spr.y_keeps;
    const yKeep = yKeeps ? yKeeps[frameIdx] : spr.y_keep;
    if (frameIdx > 0 && yKeep < 48) {
      const f0 = compileFrame(spr, ch, 0);
      for (let y = yKeep; y < 48; y++) {
        for (let x = 0; x < 32; x++) {
          out[y * 32 + x] = Number(f0[y * 32 + x]);
        }
      }
    }

    let s = '';
    for (let i = 0; i < 1536; i++) s += out[i];
    return s;
  }

  function getPalPair(pool, slot, varIdx) {
    const key = pool === 'barba' ? 'barba_palettes' : 'z2_palettes';
    return cfg[key][String(slot)][varIdx];
  }

  function drawGrid(ctx, gridStr, palPair, scale, ox, oy, bgMode) {
    if (bgMode === 'stage') {
      ctx.fillStyle = rgbCss(0x16);
      ctx.fillRect(ox, oy, 32 * scale, 48 * scale);
    } else if (bgMode === 'dark') {
      ctx.fillStyle = '#0d1017';
      ctx.fillRect(ox, oy, 32 * scale, 48 * scale);
    } else if (bgMode === 'checker') {
      for (let y = 0; y < 48; y += 4) {
        for (let x = 0; x < 32; x += 4) {
          ctx.fillStyle = ((x + y) / 4) % 2 === 0 ? '#1b202c' : '#262d3d';
          ctx.fillRect(ox + x * scale, oy + y * scale, 4 * scale, 4 * scale);
        }
      }
    }

    const c1 = rgbCss(palPair[0]);
    const c2 = rgbCss(palPair[1]);
    const c3 = rgbCss(0x0F);
    const cols = [null, c1, c2, c3];
    for (let y = 0; y < 48; y++) {
      const rowOff = y * 32;
      for (let x = 0; x < 32; x++) {
        const v = Number(gridStr[rowOff + x]);
        if (v !== 0) {
          ctx.fillStyle = cols[v];
          ctx.fillRect(ox + x * scale, oy + y * scale, scale, scale);
        }
      }
    }
  }

  function rollStageLineup(pool = ui.stagePool) {
    const candidates = cfg.characters.filter(c => c.pool === pool && c.included);
    const poolList = candidates.length >= 5
      ? candidates
      : cfg.characters.filter(c => c.pool === pool);
    const copy = poolList.slice();
    for (let i = copy.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [copy[i], copy[j]] = [copy[j], copy[i]];
    }
    ui.stageSeats[pool] = copy.slice(0, 5).map(c => c.id);
    if (pool === 'z2' && candidates.some(c => c.id === 'z2_moblin')) {
      // Keep current rolled order
    }
  }

  function initLineups() {
    rollStageLineup('z2');
    rollStageLineup('barba');
  }

  function renderStage() {
    const canvas = document.getElementById('feud-stage-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.imageSmoothingEnabled = false;
    const scale = 2;

    if (stageBgReady) {
      ctx.drawImage(stageBgImg, 0, 0, 256 * scale, 104 * scale);
    } else {
      ctx.fillStyle = rgbCss(0x16);
      ctx.fillRect(0, 0, 256 * scale, 84 * scale);
      ctx.fillStyle = rgbCss(0x27);
      ctx.fillRect(0, 84 * scale, 256 * scale, 20 * scale);
      ctx.fillStyle = rgbCss(0x2C);
      ctx.fillRect(48 * scale, 56 * scale, 160 * scale, 6 * scale);
    }

    const pool = ui.stagePool;
    const seats = ui.stageSeats[pool];
    const byId = charById();
    const seatXs = [48, 80, 112, 144, 176];
    const altPat = [2, 1, 3, 2, 1];

    const chips = document.getElementById('feud-seat-chips');
    chips.innerHTML = '';

    seats.forEach((cid, idx) => {
      const ch = byId[cid];
      const spr = spritesById[cid];
      if (!ch || !spr) return;
      const slot = pool === 'barba' ? altPat[idx] : ch.pal_slot;
      const palPair = getPalPair(pool, slot, ui.varIdx);
      let fIdx = 0;
      if (ui.poseMode === 'animate') {
        fIdx = idx === ui.animSeat ? ui.animPose : 0;
      } else {
        fIdx = Number(ui.poseMode);
      }
      const grid = compileFrame(spr, ch, fIdx);
      drawGrid(ctx, grid, palPair, scale, seatXs[idx] * scale, 8 * scale, 'none');

      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'feud-seat-chip' + (idx === 2 ? ' is-center' : '');
      const sw1 = `<span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${rgbCss(palPair[0])};border:1px solid rgba(255,255,255,0.3)"></span>`;
      const sw2 = `<span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${rgbCss(palPair[1])};border:1px solid rgba(255,255,255,0.3)"></span>`;
      chip.innerHTML = `<strong>#${idx + 1}</strong> ${ch.label} ${sw1}${sw2} <span style="color:var(--muted)">S${slot}</span>`;
      chip.onclick = () => {
        ui.highlightId = ch.id;
        renderCards();
        const card = document.querySelector(`[data-char-id="${ch.id}"]`);
        if (card) card.scrollIntoView({ behavior: 'smooth', block: 'center' });
      };
      chips.appendChild(chip);
    });
  }

  function renderPalettePanel() {
    document.getElementById('feud-pal-tab-z2').classList.toggle('active', ui.palPool === 'z2');
    document.getElementById('feud-pal-tab-barba').classList.toggle('active', ui.palPool === 'barba');

    const palKey = ui.palPool === 'barba' ? 'barba_palettes' : 'z2_palettes';
    const slotsEl = document.getElementById('feud-pal-slots');
    slotsEl.innerHTML = '';

    const slotNotes = ui.palPool === 'z2'
      ? { '1': 'Slot 1 (Red / Warm)', '2': 'Slot 2 (Blue / Cool)', '3': 'Slot 3 (Green / Gold)' }
      : { '1': 'Slot 1 (Ember / Red)', '2': 'Slot 2 (Cobalt / Slate)', '3': 'Slot 3 (Emerald / Gold)' };

    for (const slot of ['1', '2', '3']) {
      const box = document.createElement('div');
      box.className = 'feud-pal-slot';
      const head = document.createElement('div');
      head.className = 'row';
      head.style.justifyContent = 'space-between';
      head.innerHTML = `<strong style="font-size:0.84rem;color:var(--gold)">${slotNotes[slot]}</strong>`;
      box.appendChild(head);

      const vars = document.createElement('div');
      vars.className = 'feud-pal-vars';
      cfg[palKey][slot].forEach((pair, vIdx) => {
        const vb = document.createElement('div');
        vb.className = 'feud-var-box' + (vIdx === ui.varIdx ? ' is-active' : '');
        const lbl = document.createElement('span');
        lbl.textContent = `V${vIdx + 1}`;
        lbl.style.cursor = 'pointer';
        lbl.title = 'Preview this variation';
        lbl.onclick = () => {
          ui.varIdx = vIdx;
          document.getElementById('feud-var-sel').value = String(vIdx);
          renderAll();
        };
        vb.appendChild(lbl);

        const swWrap = document.createElement('div');
        swWrap.style.display = 'flex';
        swWrap.style.gap = '4px';
        [0, 1].forEach(cIdx => {
          const col = pair[cIdx];
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'feud-swatch';
          if (
            ui.editingPal &&
            ui.editingPal.pool === ui.palPool &&
            ui.editingPal.slot === slot &&
            ui.editingPal.varIdx === vIdx &&
            ui.editingPal.colorIdx === cIdx
          ) {
            btn.classList.add('is-editing');
          }
          btn.style.background = rgbCss(col);
          btn.style.color = textOn(col);
          btn.textContent = hex2(col).slice(1);
          btn.title = `Edit c${cIdx + 1} (${hex2(col)})`;
          btn.onclick = () => {
            ui.varIdx = vIdx;
            document.getElementById('feud-var-sel').value = String(vIdx);
            ui.editingPal = { pool: ui.palPool, slot, varIdx: vIdx, colorIdx: cIdx };
            renderPalettePanel();
            renderCards();
            renderStage();
          };
          swWrap.appendChild(btn);
        });
        vb.appendChild(swWrap);
        vars.appendChild(vb);
      });
      box.appendChild(vars);
      slotsEl.appendChild(box);
    }

    const picker = document.getElementById('feud-nes-picker');
    if (!ui.editingPal || ui.editingPal.pool !== ui.palPool) {
      picker.classList.add('hidden');
      picker.innerHTML = '';
      return;
    }

    picker.classList.remove('hidden');
    const { pool, slot, varIdx, colorIdx } = ui.editingPal;
    const curVal = cfg[palKey][slot][varIdx][colorIdx];
    const otherVal = cfg[palKey][slot][varIdx][1 - colorIdx];

    picker.innerHTML = '';
    const hdr = document.createElement('div');
    hdr.className = 'row';
    hdr.style.justifyContent = 'space-between';
    hdr.innerHTML =
      `<span style="font-size:0.84rem">Editing <strong>${pool === 'barba' ? 'Barba' : 'Zelda II'} Slot ${slot} · V${varIdx + 1} · c${colorIdx + 1}</strong> ` +
      `(current <code>${hex2(curVal)}</code>, paired with <code>${hex2(otherVal)}</code>, wall <code>$16</code>)</span>`;

    const actions = document.createElement('div');
    actions.style.display = 'flex';
    actions.style.gap = '6px';

    const syncBtn = document.createElement('button');
    syncBtn.type = 'button';
    syncBtn.className = 'feud-mini-btn';
    syncBtn.textContent = 'Apply Pair to All 4 Vars';
    syncBtn.onclick = () => {
      const p = cfg[palKey][slot][varIdx].slice();
      cfg[palKey][slot] = [p.slice(), p.slice(), p.slice(), p.slice()];
      renderAll();
      setToast(`Applied [${hex2(p[0])}, ${hex2(p[1])}] to all 4 variations of ${pool.toUpperCase()} Slot ${slot}.`);
    };
    actions.appendChild(syncBtn);

    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'feud-mini-btn';
    closeBtn.textContent = 'Close';
    closeBtn.onclick = () => {
      ui.editingPal = null;
      renderPalettePanel();
    };
    actions.appendChild(closeBtn);
    hdr.appendChild(actions);
    picker.appendChild(hdr);

    const grid = document.createElement('div');
    grid.className = 'feud-nes-grid';
    for (const row of USABLE_ROWS) {
      for (const nesId of row) {
        const cell = document.createElement('button');
        cell.type = 'button';
        cell.className = 'feud-nes-cell' + (nesId === curVal ? ' is-sel' : '');
        cell.style.background = rgbCss(nesId);
        cell.style.color = textOn(nesId);
        cell.textContent = nesId.toString(16).toUpperCase().padStart(2, '0');
        cell.title = `NES ${hex2(nesId)}`;
        cell.onclick = () => {
          cfg[palKey][slot][varIdx][colorIdx] = nesId;
          renderAll();
        };
        grid.appendChild(cell);
      }
    }
    picker.appendChild(grid);
  }

  function renderStats() {
    const barbaInc = cfg.characters.filter(c => c.pool === 'barba' && c.included).length;
    const z2Inc = cfg.characters.filter(c => c.pool === 'z2' && c.included).length;
    const barbaTot = cfg.characters.filter(c => c.pool === 'barba').length;
    const z2Tot = cfg.characters.filter(c => c.pool === 'z2').length;
    const topHalfTot = cfg.characters.filter(c => c.sprite_type === 'top_half').length;
    const warnB = barbaInc < 5 ? ' style="color:var(--ember);font-weight:700"' : '';
    const warnZ = z2Inc < 5 ? ' style="color:var(--ember);font-weight:700"' : '';
    document.getElementById('feud-stats').innerHTML =
      `<span${warnB}>Barba Included: <strong>${barbaInc} / ${barbaTot}</strong> (min 5)</span>` +
      `<span${warnZ}>Zelda II Included: <strong>${z2Inc} / ${z2Tot}</strong> (min 5)</span>` +
      `<span>Top Half: <strong>${topHalfTot} / ${cfg.characters.length}</strong></span>` +
      `<span>Total Active: <strong>${barbaInc + z2Inc} / ${cfg.characters.length}</strong></span>`;
  }

  function cardFrameIndex() {
    if (ui.poseMode === 'animate') return ui.animFrame % 3;
    return Number(ui.poseMode);
  }

  function renderCards() {
    const grid = document.getElementById('feud-grid');
    grid.innerHTML = '';
    const scale = ui.zoom;
    const fIdx = cardFrameIndex();

    const filtered = cfg.characters.filter(ch => {
      if (ui.filterPool !== 'all' && ch.pool !== ui.filterPool) return false;
      if (ui.filterStatus === 'included' && !ch.included) return false;
      if (ui.filterStatus === 'excluded' && ch.included) return false;
      if (ui.filterType !== 'all' && (ch.sprite_type || 'full') !== ui.filterType) return false;
      return true;
    });

    const buildCard = ch => {
      const spr = spritesById[ch.id];
      if (!spr) return null;
      const card = document.createElement('div');
      card.dataset.charId = ch.id;
      card.className = 'feud-card ' + (ch.included ? 'is-included' : 'is-excluded') +
        (ui.highlightId === ch.id ? ' is-highlighted' : '');

      const head = document.createElement('div');
      head.className = 'feud-card-head';
      head.innerHTML =
        `<div><div class="feud-card-title">${ch.label}</div>` +
        `<div class="feud-card-id">${ch.id} · ${ch.pool === 'barba' ? 'Barba' : 'Z2'}</div></div>`;

      const stageBtn = document.createElement('button');
      stageBtn.type = 'button';
      stageBtn.className = 'feud-mini-btn';
      stageBtn.textContent = 'Stage';
      stageBtn.title = 'Place this sprite in Center Seat #3 of the Stage Preview';
      stageBtn.onclick = () => {
        ui.stagePool = ch.pool;
        ui.palPool = ch.pool;
        document.getElementById('feud-stage-pool').value = ch.pool;
        const seats = ui.stageSeats[ch.pool];
        const prevIdx = seats.indexOf(ch.id);
        if (prevIdx !== -1 && prevIdx !== 2) {
          [seats[prevIdx], seats[2]] = [seats[2], seats[prevIdx]];
        } else {
          seats[2] = ch.id;
        }
        ui.highlightId = ch.id;
        renderPalettePanel();
        renderStage();
        renderCards();
        document.getElementById('feud-stage-canvas').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      };
      head.appendChild(stageBtn);
      card.appendChild(head);

      const wrap = document.createElement('div');
      wrap.className = 'feud-canvas-wrap';
      wrap.style.background = ui.backdrop === 'stage' ? rgbCss(0x16) : '#0d1017';
      const canvas = document.createElement('canvas');
      canvas.width = 32 * scale;
      canvas.height = 48 * scale;
      canvas.className = 'nes-canvas';
      canvas.dataset.spriteCanvas = ch.id;
      const ctx = canvas.getContext('2d');
      ctx.imageSmoothingEnabled = false;
      const palPair = getPalPair(ch.pool, ch.pal_slot, ui.varIdx);
      drawGrid(ctx, compileFrame(spr, ch, fIdx), palPair, scale, 0, 0, ui.backdrop);
      wrap.appendChild(canvas);
      card.appendChild(wrap);

      // Include / Exclude + Palette Slot selector
      const row = document.createElement('div');
      row.className = 'feud-ctrl-row';

      const incBtn = document.createElement('button');
      incBtn.type = 'button';
      incBtn.className = 'feud-mini-btn ' + (ch.included ? 'on' : 'off');
      incBtn.textContent = ch.included ? 'Included' : 'Excluded';
      incBtn.onclick = () => {
        ch.included = !ch.included;
        if (!ch.included && ui.stageSeats[ch.pool].includes(ch.id)) {
          rollStageLineup(ch.pool);
        }
        renderStats();
        renderStage();
        renderCards();
      };
      row.appendChild(incBtn);

      const slotGroup = document.createElement('div');
      slotGroup.style.marginLeft = 'auto';
      slotGroup.style.display = 'flex';
      slotGroup.style.gap = '3px';
      for (const s of [1, 2, 3]) {
        const sb = document.createElement('button');
        sb.type = 'button';
        sb.className = 'feud-mini-btn' + (ch.pal_slot === s ? ' slot-on' : '');
        const p = getPalPair(ch.pool, s, ui.varIdx);
        sb.innerHTML =
          `S${s} <span style="display:inline-block;width:7px;height:7px;border-radius:2px;background:${rgbCss(p[1])};vertical-align:middle"></span>`;
        sb.title = ch.pool === 'barba'
          ? `Preview Barba in Slot ${s} (stage alternates S1/S2/S3)`
          : `Assign ${ch.label} to Palette Slot ${s}`;
        sb.onclick = () => {
          ch.pal_slot = s;
          renderStage();
          renderCards();
        };
        slotGroup.appendChild(sb);
      }
      row.appendChild(slotGroup);
      card.appendChild(row);

      // Sprite Framing Type (Full vs Top Half behind podium table)
      const typeRow = document.createElement('div');
      typeRow.className = 'feud-map-row';
      const typeLbl = document.createElement('span');
      typeLbl.textContent = 'Sprite:';
      typeRow.appendChild(typeLbl);

      const typeGroup = document.createElement('div');
      typeGroup.style.display = 'flex';
      typeGroup.style.gap = '4px';
      typeGroup.style.marginLeft = 'auto';
      for (const [tVal, tLabel, tTitle] of [
        ['full', 'Full', 'Use the full sprite (for sprites that already look like top halves)'],
        ['top_half', 'Top Half', 'Use only the top half of the sprite so it sits behind the table'],
      ]) {
        const tb = document.createElement('button');
        tb.type = 'button';
        const isSel = (ch.sprite_type || 'full') === tVal;
        tb.className = 'feud-mini-btn' + (isSel ? ' type-on' : '');
        tb.textContent = tLabel;
        tb.title = tTitle;
        tb.setAttribute('aria-pressed', String(isSel));
        tb.setAttribute('aria-label', `${tLabel} for ${ch.label}`);
        tb.onclick = () => {
          ch.sprite_type = tVal;
          renderStats();
          renderStage();
          renderCards();
        };
        typeGroup.appendChild(tb);
      }
      typeRow.appendChild(typeGroup);
      card.appendChild(typeRow);

      // Z2 Pixel Remapping & Outline controls
      if (ch.pool === 'z2') {
        const mRow = document.createElement('div');
        mRow.className = 'feud-map-row';
        const curMap = ch.mapping || '312';
        for (let idx = 0; idx < 3; idx++) {
          const mb = document.createElement('button');
          mb.type = 'button';
          mb.className = 'feud-map-btn';
          const targetVal = curMap[idx];
          mb.textContent = `${idx + 1}→${MAP_VAL_LABELS[targetVal]}`;
          mb.title = `Click to cycle where Z2 pixel ${idx + 1} maps (bg / c1 / c2 / blk)`;
          mb.onclick = () => {
            const order = ['1', '2', '3', '0'];
            const next = order[(order.indexOf(targetVal) + 1) % order.length];
            const chars = curMap.split('');
            chars[idx] = next;
            ch.mapping = chars.join('');
            renderStage();
            renderCards();
          };
          mRow.appendChild(mb);
        }

        const outBtn = document.createElement('button');
        outBtn.type = 'button';
        outBtn.className = 'feud-map-btn' + (ch.outline !== false ? ' slot-on' : '');
        outBtn.textContent = ch.outline !== false ? 'Outline:On' : 'Outline:Off';
        outBtn.onclick = () => {
          ch.outline = ch.outline === false;
          renderStage();
          renderCards();
        };
        mRow.appendChild(outBtn);

        const preSel = document.createElement('select');
        preSel.className = 'feud-map-btn';
        preSel.style.marginLeft = 'auto';
        const customOpt = document.createElement('option');
        customOpt.value = '';
        customOpt.textContent = 'Preset…';
        preSel.appendChild(customOpt);
        for (const [pname, pval] of Object.entries(Z2_PRESETS)) {
          const opt = document.createElement('option');
          opt.value = pval;
          opt.textContent = pname;
          if (curMap === pval) opt.selected = true;
          preSel.appendChild(opt);
        }
        preSel.onchange = () => {
          if (preSel.value) {
            ch.mapping = preSel.value;
            renderStage();
            renderCards();
          }
        };
        mRow.appendChild(preSel);
        card.appendChild(mRow);
      }

      return card;
    };

    if (ui.filterPool === 'all') {
      grid.className = 'feud-split';
      const sides = [
        ['barba', 'Left Side · Barba Types'],
        ['z2', 'Right Side · Zelda II Characters'],
      ];
      for (const [poolKey, title] of sides) {
        const list = filtered.filter(ch => ch.pool === poolKey);
        const totalPool = cfg.characters.filter(ch => ch.pool === poolKey);
        const incPool = totalPool.filter(ch => ch.included).length;

        const col = document.createElement('div');
        col.className = 'feud-side-col';
        col.dataset.sidePool = poolKey;

        const hdr = document.createElement('div');
        hdr.className = 'feud-side-head';
        hdr.innerHTML = `<strong>${title}</strong><span>${list.length} shown · ${incPool}/${totalPool.length} included</span>`;
        col.appendChild(hdr);

        const innerGrid = document.createElement('div');
        innerGrid.className = 'feud-grid';
        for (const ch of list) {
          const card = buildCard(ch);
          if (card) innerGrid.appendChild(card);
        }
        col.appendChild(innerGrid);
        grid.appendChild(col);
      }
    } else {
      grid.className = 'feud-grid';
      for (const ch of filtered) {
        const card = buildCard(ch);
        if (card) grid.appendChild(card);
      }
    }
  }

  function redrawAnimationsOnly() {
    renderStage();
    const fIdx = cardFrameIndex();
    const scale = ui.zoom;
    const byId = charById();
    document.querySelectorAll('canvas[data-sprite-canvas]').forEach(canvas => {
      const cid = canvas.dataset.spriteCanvas;
      const ch = byId[cid];
      const spr = spritesById[cid];
      if (!ch || !spr) return;
      const ctx = canvas.getContext('2d');
      ctx.imageSmoothingEnabled = false;
      const palPair = getPalPair(ch.pool, ch.pal_slot, ui.varIdx);
      drawGrid(ctx, compileFrame(spr, ch, fIdx), palPair, scale, 0, 0, ui.backdrop);
    });
  }

  function renderAll() {
    const selPool = document.getElementById('feud-filter-pool');
    if (selPool) {
      const zCnt = cfg.characters.filter(c => c.pool === 'z2').length;
      const bCnt = cfg.characters.filter(c => c.pool === 'barba').length;
      for (const opt of selPool.options) {
        if (opt.value === 'all') opt.textContent = `All Cast (${cfg.characters.length})`;
        else if (opt.value === 'barba') opt.textContent = `Barba Cast — Left (${bCnt})`;
        else if (opt.value === 'z2') opt.textContent = `Zelda II Cast — Right (${zCnt})`;
      }
    }
    renderStats();
    renderPalettePanel();
    renderStage();
    renderCards();
  }

  function exportConfigJson() {
    return JSON.stringify(cfg, null, 2) + '\n';
  }

  // Bind controls
  document.getElementById('feud-stage-pool').onchange = e => {
    ui.stagePool = e.target.value;
    ui.palPool = e.target.value;
    renderPalettePanel();
    renderStage();
  };
  document.getElementById('feud-pose').onchange = e => {
    ui.poseMode = e.target.value;
    redrawAnimationsOnly();
  };
  document.getElementById('feud-roll-stage').onclick = () => {
    rollStageLineup(ui.stagePool);
    renderStage();
  };
  document.getElementById('feud-pal-tab-z2').onclick = () => {
    ui.palPool = 'z2';
    renderPalettePanel();
  };
  document.getElementById('feud-pal-tab-barba').onclick = () => {
    ui.palPool = 'barba';
    renderPalettePanel();
  };
  document.getElementById('feud-var-sel').onchange = e => {
    ui.varIdx = Number(e.target.value);
    renderAll();
  };
  document.getElementById('feud-filter-pool').onchange = e => {
    ui.filterPool = e.target.value;
    if (ui.filterPool === 'z2' || ui.filterPool === 'barba') {
      ui.palPool = ui.filterPool;
      ui.stagePool = ui.filterPool;
      document.getElementById('feud-stage-pool').value = ui.filterPool;
    }
    renderAll();
  };
  document.getElementById('feud-filter-status').onchange = e => {
    ui.filterStatus = e.target.value;
    renderCards();
  };
  document.getElementById('feud-filter-type').onchange = e => {
    ui.filterType = e.target.value;
    renderCards();
  };
  document.getElementById('feud-bg').onchange = e => {
    ui.backdrop = e.target.value;
    renderCards();
  };
  document.getElementById('feud-zoom').onchange = e => {
    ui.zoom = Number(e.target.value);
    renderCards();
  };
  document.getElementById('feud-include-all').onclick = () => {
    cfg.characters.forEach(c => { c.included = true; });
    renderAll();
    setToast(`All ${cfg.characters.length} cast sprites marked Included.`);
  };
  document.getElementById('feud-reset').onclick = () => {
    cfg = cloneCfg(data.config);
    ui.editingPal = null;
    initLineups();
    renderAll();
    setToast('Reset to current assets/feud_cast.json.');
  };
  document.getElementById('feud-copy').onclick = () => {
    const b = cfg.characters.filter(c => c.pool === 'barba' && c.included).length;
    const z = cfg.characters.filter(c => c.pool === 'z2' && c.included).length;
    if (b < 5 || z < 5) {
      setToast(`Need at least 5 included in each pool (Barba=${b}, Z2=${z}).`, true);
      return;
    }
    navigator.clipboard?.writeText(exportConfigJson());
    setToast('Copied feud_cast.json to clipboard.');
  };
  document.getElementById('feud-download').onclick = () => {
    const b = cfg.characters.filter(c => c.pool === 'barba' && c.included).length;
    const z = cfg.characters.filter(c => c.pool === 'z2' && c.included).length;
    if (b < 5 || z < 5) {
      setToast(`Need at least 5 included in each pool (Barba=${b}, Z2=${z}).`, true);
      return;
    }
    const blob = new Blob([exportConfigJson()], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'feud_cast.json';
    a.click();
    setToast('Downloaded feud_cast.json — save to assets/feud_cast.json and rebuild!');
  };

  initLineups();
  renderAll();

  // Gentle animation loop when Pose == Animate
  setInterval(() => {
    if (document.getElementById('view-feud').classList.contains('hidden')) return;
    if (ui.poseMode !== 'animate') return;
    ui.animFrame = (ui.animFrame + 1) % 6;
    if (ui.animFrame % 3 === 0) {
      ui.animSeat = Math.floor(Math.random() * 5);
      ui.animPose = Math.random() < 0.5 ? 1 : 2;
    } else if (ui.animFrame % 3 === 2) {
      ui.animSeat = -1;
      ui.animPose = 0;
    }
    redrawAnimationsOnly();
  }, 550);
})();
