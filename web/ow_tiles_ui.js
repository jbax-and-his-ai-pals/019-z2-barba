(() => {
  const data = window.OW_TILES_DATA;
  if (!data) return;

  const STORAGE_KEY = 'barba_ow_tiles_lab_v1';
  const NES_PAL = data.nes_palette;
  const PALS = data.palettes;

  function loadState() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      return {
        stars: parsed.stars && typeof parsed.stars === 'object' ? parsed.stars : {},
        notes: parsed.notes && typeof parsed.notes === 'object' ? parsed.notes : {},
        sandbox: parsed.sandbox && typeof parsed.sandbox === 'object' ? parsed.sandbox : {},
      };
    } catch {
      return { stars: {}, notes: {}, sandbox: {} };
    }
  }

  function saveState() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        stars: ui.stars,
        notes: ui.notes,
        sandbox: ui.sandbox,
      }));
    } catch {}
  }

  const saved = loadState();
  const ui = {
    filter: 'all',
    region: 'west',
    zoom: 6,
    speed: 1,
    playing: true,
    showGrid: true,
    tick: 0,
    stars: saved.stars,
    notes: saved.notes,
    sandbox: saved.sandbox,
    sbTarget: 'grass',
    sbFrame: 1,
    sbColor: 3,
    sbFps: 4,
    isActiveTab: false,
  };

  const canvases = [];

  const rgbCss = idx => {
    const [r, g, b] = NES_PAL[idx & 0x3f];
    return `rgb(${r},${g},${b})`;
  };

  function resolvePal(palKey) {
    if (ui.region === 'east' && palKey === 'west_foliage') {
      return PALS.east_foliage.colors;
    }
    return (PALS[palKey] || PALS.west_foliage).colors;
  }

  function drawTile8(ctx, flat, ox, oy, scale, colors, transparentZero = false) {
    for (let y = 0; y < 8; y++) {
      const row = y * 8;
      for (let x = 0; x < 8; x++) {
        const c = flat[row + x];
        if (transparentZero && c === 0) continue;
        ctx.fillStyle = rgbCss(colors[c & 3]);
        ctx.fillRect(ox + x * scale, oy + y * scale, scale, scale);
      }
    }
  }

  function drawGridOverlay(ctx, w, h, stepPx) {
    if (!ui.showGrid || stepPx < 4) return;
    ctx.save();
    ctx.strokeStyle = 'rgba(255,255,255,0.14)';
    ctx.lineWidth = 1;
    for (let x = stepPx; x < w; x += stepPx) {
      ctx.beginPath();
      ctx.moveTo(x + 0.5, 0);
      ctx.lineTo(x + 0.5, h);
      ctx.stroke();
    }
    for (let y = stepPx; y < h; y += stepPx) {
      ctx.beginPath();
      ctx.moveTo(0, y + 0.5);
      ctx.lineTo(w, y + 0.5);
      ctx.stroke();
    }
    ctx.restore();
  }

  function showToast(msg) {
    const el = document.getElementById('owt-toast');
    if (!el) return;
    el.textContent = msg;
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => { el.textContent = ''; }, 2400);
  }

  // Deterministic pseudo-random helper for repeatable async patch demos
  function hash2d(x, y, seed = 17) {
    let n = (x * 73856093) ^ (y * 19349663) ^ (seed * 83492791);
    n = ((n >> 13) ^ n) * 1274126177;
    return ((n >> 16) ^ n) >>> 0;
  }

  function drawEnvCardCanvas(item, tick) {
    const { kind, env, mode, singleCanvas, patchCanvas } = item;
    const scale = ui.zoom;
    const colors = resolvePal(env.pal);

    // Single tile / 2x2 metatile
    const is2x2 = kind === 'forest' || kind === 'mountain' || kind === 'graveyard';
    const sw = (is2x2 ? 16 : 8) * scale;
    const sh = (is2x2 ? 16 : 8) * scale;
    if (singleCanvas.width !== sw) singleCanvas.width = sw;
    if (singleCanvas.height !== sh) singleCanvas.height = sh;
    const sctx = singleCanvas.getContext('2d');
    sctx.imageSmoothingEnabled = false;

    if (kind === 'water' || kind === 'swamp') {
      const step = Math.floor(tick / 16) % env.frames.length;
      drawTile8(sctx, env.frames[step], 0, 0, scale, colors);
    } else if (kind === 'desert') {
      drawTile8(sctx, env.frames[0], 0, 0, scale, colors);
      const p = data.particles.desert_glint;
      const f = Math.floor(tick / 10) % (p.frames.length + 2);
      if (f < p.frames.length) {
        drawTile8(sctx, p.frames[f], scale, scale, scale, resolvePal(p.pal), true);
      }
    } else if (kind === 'mountain') {
      drawTile8(sctx, env.frames[0], 0, 0, scale, colors);
      drawTile8(sctx, env.frames[1], 0, 8 * scale, scale, colors);
      drawTile8(sctx, env.frames[2], 8 * scale, 0, scale, colors);
      drawTile8(sctx, env.frames[3], 8 * scale, 8 * scale, scale, colors);
    } else if (kind === 'graveyard') {
      sctx.fillStyle = rgbCss(colors[0]);
      sctx.fillRect(0, 0, sw, sh);
      drawTile8(sctx, env.frames[0], 0, 0, scale, colors);
      drawTile8(sctx, env.frames[1], 0, 8 * scale, scale, colors);
      drawTile8(sctx, env.frames[0], 8 * scale, 0, scale, colors);
      drawTile8(sctx, env.frames[1], 8 * scale, 8 * scale, scale, colors);
    } else if (kind === 'forest') {
      const tlKeys = Object.keys(env.variants_tl);
      const trKeys = Object.keys(env.variants_tr);
      const idx = Math.floor(tick / 18) % (tlKeys.length + 1);
      const tl = idx === 0 ? env.frames[0] : env.variants_tl[tlKeys[idx - 1]];
      const tr = idx === 0 ? env.frames[2] : env.variants_tr[trKeys[idx - 1]];
      drawTile8(sctx, tl, 0, 0, scale, colors);
      drawTile8(sctx, env.frames[1], 0, 8 * scale, scale, colors);
      drawTile8(sctx, tr, 8 * scale, 0, scale, colors);
      drawTile8(sctx, env.frames[3], 8 * scale, 8 * scale, scale, colors);
    } else if (kind === 'grass') {
      const keys = Object.keys(env.variants);
      const idx = Math.floor(tick / 18) % (keys.length + 1);
      const tile = idx === 0 ? env.frames[0] : env.variants[keys[idx - 1]];
      drawTile8(sctx, tile, 0, 0, scale, colors);
    }
    drawGridOverlay(sctx, sw, sh, 8 * scale);

    // Multi-tile overworld patch (48x32 NES px -> scaled by max(3, floor(scale*0.65)))
    const pScale = Math.max(3, Math.floor(scale * 0.65));
    const cols = 6;
    const rows = 4;
    const pw = cols * 8 * pScale;
    const ph = rows * 8 * pScale;
    if (patchCanvas.width !== pw) patchCanvas.width = pw;
    if (patchCanvas.height !== ph) patchCanvas.height = ph;
    const pctx = patchCanvas.getContext('2d');
    pctx.imageSmoothingEnabled = false;

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        let tile = env.frames[0];
        if (kind === 'water' || kind === 'swamp') {
          const step = Math.floor(tick / 16) % env.frames.length;
          tile = env.frames[step];
        } else if (kind === 'mountain') {
          const idx = ((c & 1) << 1) | (r & 1);
          tile = env.frames[idx];
        } else if (kind === 'graveyard') {
          tile = env.frames[r & 1];
        } else if (kind === 'forest') {
          const idx = ((c & 1) << 1) | (r & 1);
          tile = env.frames[idx];
          const treeId = Math.floor(c / 2) + Math.floor(r / 2) * 3;
          const phase = Math.floor((tick + treeId * 11) / 18) % 4;
          if (idx === 0 && phase > 0) {
            const k = Object.keys(env.variants_tl)[(treeId + phase) % 6];
            tile = env.variants_tl[k];
          } else if (idx === 2 && phase > 0) {
            const k = Object.keys(env.variants_tr)[(treeId + phase) % 6];
            tile = env.variants_tr[k];
          }
        } else if (kind === 'grass') {
          const h = hash2d(c, r, 9);
          const keys = Object.keys(env.variants);
          const period = 20 + (h % 19);
          const phase = Math.floor((tick + (h % 37)) / period) % 5;
          if ((h % 3) !== 0 && phase > 0 && phase < 3) {
            tile = env.variants[keys[(h + phase) % keys.length]];
          }
        }
        drawTile8(pctx, tile, c * 8 * pScale, r * 8 * pScale, pScale, colors);
      }
    }

    // Overlay OAM particles for settled particle environments
    if (env.particle && data.particles[env.particle]) {
      const part = data.particles[env.particle];
      const pPal = resolvePal(part.pal);
      const dur = part.duration;
      for (let slot = 0; slot < 3; slot++) {
        const localT = (tick + slot * Math.floor(dur * 0.7)) % (dur + 24);
        if (localT >= dur) continue;
        const cycle = Math.floor((tick + slot * Math.floor(dur * 0.7)) / (dur + 24));
        const h = hash2d(slot, cycle, 42);
        const px = 4 + (h % (cols * 8 - 10));
        let py = 4 + ((h >> 8) % (rows * 8 - 10));
        if (kind === 'swamp' || kind === 'graveyard') {
          py -= Math.floor(localT / 8);
        } else if (kind === 'mountain') {
          py -= Math.floor(localT / 4);
        }
        const fIdx = Math.min(
          part.frames.length - 1,
          Math.floor((localT / dur) * part.frames.length)
        );
        if (py >= 0 && py < rows * 8 - 4) {
          drawTile8(pctx, part.frames[fIdx], px * pScale, py * pScale, pScale, pPal, true);
        }
      }
    }
    drawGridOverlay(pctx, pw, ph, 8 * pScale);
  }

  function drawGrassOption(item, tick) {
    const { opt, singleCanvas, patchCanvas } = item;
    const scale = ui.zoom;
    const colors = resolvePal('west_foliage');
    const sw = 8 * scale;
    const sh = 8 * scale;
    if (singleCanvas.width !== sw) singleCanvas.width = sw;
    if (singleCanvas.height !== sh) singleCanvas.height = sh;
    const sctx = singleCanvas.getContext('2d');
    sctx.imageSmoothingEnabled = false;

    const seq = opt.sequences[0] || ['base'];
    const step = Math.floor(tick / opt.frames_per_step) % seq.length;
    const tile = opt.tiles[seq[step]] || opt.tiles.base;
    drawTile8(sctx, tile, 0, 0, scale, colors);
    if (opt.mode === 'oam_meadow' && opt.oam_frames) {
      const f = Math.floor(tick / 12) % (opt.oam_frames.length + 2);
      if (f < opt.oam_frames.length) {
        drawTile8(sctx, opt.oam_frames[f], scale, scale, scale, resolvePal('spr0'), true);
      }
    }
    drawGridOverlay(sctx, sw, sh, 8 * scale);

    const pScale = Math.max(3, Math.floor(scale * 0.65));
    const cols = 6;
    const rows = 4;
    const pw = cols * 8 * pScale;
    const ph = rows * 8 * pScale;
    if (patchCanvas.width !== pw) patchCanvas.width = pw;
    if (patchCanvas.height !== ph) patchCanvas.height = ph;
    const pctx = patchCanvas.getContext('2d');
    pctx.imageSmoothingEnabled = false;

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        let cellTile = opt.tiles.base;
        if (opt.mode === 'wave_meadow') {
          const wStep = Math.floor((tick + c * 6 + r * 2) / opt.frames_per_step) % seq.length;
          cellTile = opt.tiles[seq[wStep]] || opt.tiles.base;
        } else if (opt.mode === 'async_meadow') {
          const h = hash2d(c, r, 13);
          const sIdx = h % opt.sequences.length;
          const cellSeq = opt.sequences[sIdx];
          const period = opt.frames_per_step + (h % 11);
          const cStep = Math.floor((tick + (h % 31)) / period) % (cellSeq.length + 2);
          if (cStep < cellSeq.length && (h % 4) !== 0) {
            cellTile = opt.tiles[cellSeq[cStep]] || opt.tiles.base;
          }
        }
        drawTile8(pctx, cellTile, c * 8 * pScale, r * 8 * pScale, pScale, colors);
      }
    }
    if (opt.mode === 'oam_meadow' && opt.oam_frames) {
      const sprPal = resolvePal('spr0');
      for (let slot = 0; slot < 3; slot++) {
        const localT = (tick + slot * 19) % 48;
        if (localT >= 28) continue;
        const cyc = Math.floor((tick + slot * 19) / 48);
        const h = hash2d(slot, cyc, 77);
        const px = 4 + (h % (cols * 8 - 10));
        const py = 4 + ((h >> 8) % (rows * 8 - 10)) - Math.floor(localT / 10);
        const f = Math.floor(localT / 8) % opt.oam_frames.length;
        if (py >= 0) {
          drawTile8(pctx, opt.oam_frames[f], px * pScale, py * pScale, pScale, sprPal, true);
        }
      }
    }
    drawGridOverlay(pctx, pw, ph, 8 * pScale);
  }

  function drawForestOption(item, tick) {
    const { opt, singleCanvas, patchCanvas } = item;
    const scale = ui.zoom;
    const colors = resolvePal('west_foliage');
    const sw = 16 * scale;
    const sh = 16 * scale;
    if (singleCanvas.width !== sw) singleCanvas.width = sw;
    if (singleCanvas.height !== sh) singleCanvas.height = sh;
    const sctx = singleCanvas.getContext('2d');
    sctx.imageSmoothingEnabled = false;

    const tlSeq = opt.tl_sequences[0] || ['base'];
    const trSeq = opt.tr_sequences[0] || ['base'];
    const stepL = Math.floor(tick / opt.frames_per_step) % tlSeq.length;
    const stepR = Math.floor(tick / opt.frames_per_step) % trSeq.length;
    const tl = opt.tl_variants[tlSeq[stepL]] || opt.base.tl;
    const tr = opt.tr_variants[trSeq[stepR]] || opt.base.tr;

    drawTile8(sctx, tl, 0, 0, scale, colors);
    drawTile8(sctx, opt.base.bl, 0, 8 * scale, scale, colors);
    drawTile8(sctx, tr, 8 * scale, 0, scale, colors);
    drawTile8(sctx, opt.base.br, 8 * scale, 8 * scale, scale, colors);
    if (opt.mode === 'oam_forest' && opt.oam_frames) {
      const f = Math.floor(tick / 10) % opt.oam_frames.length;
      const fallY = Math.floor((tick % 36) / 6);
      drawTile8(sctx, opt.oam_frames[f], 4 * scale, (3 + fallY) * scale, scale, resolvePal('spr0'), true);
    }
    drawGridOverlay(sctx, sw, sh, 8 * scale);

    const pScale = Math.max(3, Math.floor(scale * 0.65));
    const cols = 6;
    const rows = 4;
    const pw = cols * 8 * pScale;
    const ph = rows * 8 * pScale;
    if (patchCanvas.width !== pw) patchCanvas.width = pw;
    if (patchCanvas.height !== ph) patchCanvas.height = ph;
    const pctx = patchCanvas.getContext('2d');
    pctx.imageSmoothingEnabled = false;

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const idx = ((c & 1) << 1) | (r & 1);
        const treeId = Math.floor(c / 2) + Math.floor(r / 2) * 3;
        let tile = [opt.base.tl, opt.base.bl, opt.base.tr, opt.base.br][idx];
        if (opt.mode === 'async_forest') {
          const h = hash2d(Math.floor(c / 2), Math.floor(r / 2), 29);
          const period = opt.frames_per_step + (h % 9);
          const phIdx = Math.floor((tick + treeId * 13) / period);
          if (idx === 0) {
            const s = opt.tl_sequences[treeId % opt.tl_sequences.length];
            const k = s[phIdx % (s.length + 1)];
            if (k && opt.tl_variants[k]) tile = opt.tl_variants[k];
          } else if (idx === 2) {
            const s = opt.tr_sequences[treeId % opt.tr_sequences.length];
            const k = s[phIdx % (s.length + 1)];
            if (k && opt.tr_variants[k]) tile = opt.tr_variants[k];
          }
        }
        drawTile8(pctx, tile, c * 8 * pScale, r * 8 * pScale, pScale, colors);
      }
    }
    if (opt.mode === 'oam_forest' && opt.oam_frames) {
      const sprPal = resolvePal('spr0');
      for (let slot = 0; slot < 2; slot++) {
        const localT = (tick + slot * 23) % 44;
        if (localT >= 32) continue;
        const cyc = Math.floor((tick + slot * 23) / 44);
        const h = hash2d(slot, cyc, 51);
        const px = 4 + (h % (cols * 8 - 10));
        const py = 2 + ((h >> 8) % (rows * 8 - 12)) + Math.floor(localT / 6);
        const f = Math.floor(localT / 8) % opt.oam_frames.length;
        if (py < rows * 8 - 4) {
          drawTile8(pctx, opt.oam_frames[f], px * pScale, py * pScale, pScale, sprPal, true);
        }
      }
    }
    drawGridOverlay(pctx, pw, ph, 8 * pScale);
  }

  // ---- Sandbox state & helpers ----
  function getSandboxFrames(target) {
    if (!ui.sandbox[target]) {
      let base;
      if (target === 'grass') {
        base = data.environments.find(e => e.id === 'grass').frames[0];
      } else if (target === 'forest_tl') {
        base = data.environments.find(e => e.id === 'forest').frames[0];
      } else {
        base = data.environments.find(e => e.id === 'forest').frames[2];
      }
      ui.sandbox[target] = [
        [...base],
        [...base],
        [...base],
      ];
    }
    return ui.sandbox[target];
  }

  function renderSandbox() {
    const editorCanvas = document.getElementById('owt-sb-editor');
    const previewCanvas = document.getElementById('owt-sb-preview');
    const palBar = document.getElementById('owt-sb-palette');
    const frameTabs = document.getElementById('owt-sb-frames');
    if (!editorCanvas || !previewCanvas || !palBar || !frameTabs) return;

    const colors = resolvePal('west_foliage');
    const frames = getSandboxFrames(ui.sbTarget);

    // Palette buttons
    palBar.innerHTML = colors.map((nesIdx, cIdx) => {
      const active = ui.sbColor === cIdx ? ' active' : '';
      return `<button type="button" class="filter-btn${active}" data-sb-col="${cIdx}" style="display:inline-flex;align-items:center;gap:6px;">` +
        `<span style="display:inline-block;width:14px;height:14px;border-radius:3px;border:1px solid #fff3;background:${rgbCss(nesIdx)};"></span>` +
        `Idx ${cIdx} ($${nesIdx.toString(16).toUpperCase().padStart(2, '0')})</button>`;
    }).join('');
    palBar.querySelectorAll('[data-sb-col]').forEach(btn => {
      btn.onclick = () => {
        ui.sbColor = Number(btn.dataset.sbCol);
        renderSandbox();
      };
    });

    // Frame selector buttons
    frameTabs.innerHTML = frames.map((_, idx) => {
      const label = idx === 0 ? 'Frame 0 (Base)' : `Frame ${idx}`;
      const active = ui.sbFrame === idx ? ' active' : '';
      return `<button type="button" class="filter-btn${active}" data-sb-frame="${idx}">${label}</button>`;
    }).join('');
    frameTabs.querySelectorAll('[data-sb-frame]').forEach(btn => {
      btn.onclick = () => {
        ui.sbFrame = Number(btn.dataset.sbFrame);
        renderSandbox();
      };
    });

    // Draw editor 8x8 at 24px/pixel (192x192)
    const cell = 24;
    editorCanvas.width = 8 * cell;
    editorCanvas.height = 8 * cell;
    const ectx = editorCanvas.getContext('2d');
    ectx.imageSmoothingEnabled = false;
    drawTile8(ectx, frames[ui.sbFrame], 0, 0, cell, colors);
    ectx.strokeStyle = 'rgba(255,255,255,0.22)';
    ectx.lineWidth = 1;
    for (let i = 1; i < 8; i++) {
      ectx.beginPath();
      ectx.moveTo(i * cell + 0.5, 0);
      ectx.lineTo(i * cell + 0.5, 192);
      ectx.stroke();
      ectx.beginPath();
      ectx.moveTo(0, i * cell + 0.5);
      ectx.lineTo(192, i * cell + 0.5);
      ectx.stroke();
    }

    const paintAt = ev => {
      const rect = editorCanvas.getBoundingClientRect();
      const x = Math.floor(((ev.clientX - rect.left) / rect.width) * 8);
      const y = Math.floor(((ev.clientY - rect.top) / rect.height) * 8);
      if (x >= 0 && x < 8 && y >= 0 && y < 8) {
        frames[ui.sbFrame][y * 8 + x] = ui.sbColor;
        saveState();
        drawTile8(ectx, frames[ui.sbFrame], 0, 0, cell, colors);
        ectx.strokeStyle = 'rgba(255,255,255,0.22)';
        for (let i = 1; i < 8; i++) {
          ectx.beginPath();
          ectx.moveTo(i * cell + 0.5, 0);
          ectx.lineTo(i * cell + 0.5, 192);
          ectx.stroke();
          ectx.beginPath();
          ectx.moveTo(0, i * cell + 0.5);
          ectx.lineTo(192, i * cell + 0.5);
          ectx.stroke();
        }
      }
    };
    let drawing = false;
    editorCanvas.onmousedown = ev => { drawing = true; paintAt(ev); };
    window.addEventListener('mouseup', () => { drawing = false; });
    editorCanvas.onmousemove = ev => { if (drawing) paintAt(ev); };
  }

  function drawSandboxPreview(tick) {
    const previewCanvas = document.getElementById('owt-sb-preview');
    if (!previewCanvas) return;
    const colors = resolvePal('west_foliage');
    const frames = getSandboxFrames(ui.sbTarget);
    const stepFrames = Math.max(1, Math.round(60 / ui.sbFps));
    const fIdx = Math.floor(tick / stepFrames) % frames.length;
    const pScale = 4;
    const pw = 6 * 8 * pScale;
    const ph = 4 * 8 * pScale;
    if (previewCanvas.width !== pw) previewCanvas.width = pw;
    if (previewCanvas.height !== ph) previewCanvas.height = ph;
    const pctx = previewCanvas.getContext('2d');
    pctx.imageSmoothingEnabled = false;

    const forestEnv = data.environments.find(e => e.id === 'forest');
    for (let r = 0; r < 4; r++) {
      for (let c = 0; c < 6; c++) {
        let tile = frames[0];
        if (ui.sbTarget === 'grass') {
          const h = hash2d(c, r, 19);
          const localIdx = Math.floor((tick + (h % 23)) / stepFrames) % frames.length;
          tile = ((h % 3) !== 0) ? frames[localIdx] : frames[0];
        } else {
          const idx = ((c & 1) << 1) | (r & 1);
          if (idx === 0) {
            tile = ui.sbTarget === 'forest_tl' ? frames[fIdx] : forestEnv.frames[0];
          } else if (idx === 1) {
            tile = forestEnv.frames[1];
          } else if (idx === 2) {
            tile = ui.sbTarget === 'forest_tr' ? frames[fIdx] : forestEnv.frames[2];
          } else {
            tile = forestEnv.frames[3];
          }
        }
        drawTile8(pctx, tile, c * 8 * pScale, r * 8 * pScale, pScale, colors);
      }
    }
    drawGridOverlay(pctx, pw, ph, 8 * pScale);
  }

  function renderAll() {
    canvases.length = 0;
    const envGrid = document.getElementById('owt-env-grid');
    const grassGrid = document.getElementById('owt-grass-grid');
    const forestGrid = document.getElementById('owt-forest-grid');
    const statsEl = document.getElementById('owt-stats');
    if (!envGrid || !grassGrid || !forestGrid) return;

    const filteredEnvs = data.environments.filter(e => {
      if (ui.filter === 'settled') return e.status === 'settled';
      if (ui.filter === 'iterating') return e.status === 'iterating';
      return true;
    });

    if (statsEl) {
      const settledCount = data.environments.filter(e => e.status === 'settled').length;
      const iterCount = data.environments.filter(e => e.status === 'iterating').length;
      const starCount = Object.values(ui.stars).filter(Boolean).length;
      statsEl.innerHTML =
        `<span>Source: <strong>${data.source}</strong></span>` +
        `<span>Settled Types: <strong>${settledCount}</strong></span>` +
        `<span>Iterating (Forest &amp; Grass): <strong>${iterCount}</strong></span>` +
        `<span>Shortlisted Options: <strong>${starCount}</strong></span>`;
    }

    envGrid.innerHTML = '';
    for (const env of filteredEnvs) {
      const card = document.createElement('section');
      card.className = 'card';
      const badgeCls = env.status === 'settled' ? 'b-built' : 'b-local';
      const badgeTxt = env.status === 'settled' ? 'Settled' : 'Iterating (Not Settled)';
      card.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;">
          <h2 style="margin:0;">${env.name} <span class="mono" style="font-size:0.78rem;color:var(--muted);">${env.tile_ids}</span></h2>
          <span class="badge ${badgeCls}">${badgeTxt}</span>
        </div>
        <div style="font-size:0.84rem;color:var(--muted);line-height:1.4;">
          <div><strong>Mechanism:</strong> ${env.mechanism}</div>
          <div><strong>Timing:</strong> ${env.timing}</div>
          <div>${env.notes}</div>
        </div>
        <div style="display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap;margin-top:4px;">
          <div>
            <div style="font-size:0.75rem;color:var(--muted);margin-bottom:4px;">Tile / Metatile</div>
            <canvas class="owt-canvas" style="image-rendering:pixelated;border:1px solid var(--border);border-radius:6px;"></canvas>
          </div>
          <div>
            <div style="font-size:0.75rem;color:var(--muted);margin-bottom:4px;">Overworld Patch</div>
            <canvas class="owt-canvas" style="image-rendering:pixelated;border:1px solid var(--border);border-radius:6px;"></canvas>
          </div>
        </div>
      `;
      const [singleCanvas, patchCanvas] = card.querySelectorAll('canvas');
      canvases.push({ type: 'env', kind: env.kind, env, singleCanvas, patchCanvas });
      envGrid.appendChild(card);
    }

    const renderOptionCards = (container, list, type) => {
      container.innerHTML = '';
      for (const opt of list) {
        const card = document.createElement('section');
        card.className = 'card';
        const starred = Boolean(ui.stars[opt.id]);
        const noteVal = ui.notes[opt.id] || '';
        const statusBadge = opt.status === 'current'
          ? '<span class="badge b-planned">Current ROM</span>'
          : '<span class="badge b-local">Candidate</span>';
        card.innerHTML = `
          <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;">
            <h2 style="margin:0;font-size:0.96rem;">${opt.name}</h2>
            <div style="display:flex;gap:6px;align-items:center;">
              ${statusBadge}
              <button type="button" class="filter-btn${starred ? ' active' : ''}" data-star="${opt.id}">${starred ? 'Shortlisted' : 'Shortlist'}</button>
            </div>
          </div>
          <div style="font-size:0.82rem;color:var(--muted);line-height:1.4;">
            <div><strong>How:</strong> ${opt.mechanism}</div>
            <div><strong>Pros:</strong> ${opt.pros}</div>
            <div>${opt.notes}</div>
          </div>
          <div style="display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap;">
            <div>
              <div style="font-size:0.74rem;color:var(--muted);margin-bottom:4px;">Zoomed</div>
              <canvas style="image-rendering:pixelated;border:1px solid var(--border);border-radius:6px;"></canvas>
            </div>
            <div>
              <div style="font-size:0.74rem;color:var(--muted);margin-bottom:4px;">Patch Preview</div>
              <canvas style="image-rendering:pixelated;border:1px solid var(--border);border-radius:6px;"></canvas>
            </div>
          </div>
          <input type="text" data-note="${opt.id}" placeholder="Iteration notes for ${opt.name}..." value="${noteVal.replace(/"/g, '&quot;')}" style="width:100%;font-size:0.82rem;background:#0e121a;color:var(--text);border:1px solid var(--border);border-radius:6px;padding:6px 8px;">
        `;
        const [singleCanvas, patchCanvas] = card.querySelectorAll('canvas');
        canvases.push({ type, opt, singleCanvas, patchCanvas });
        card.querySelector('[data-star]').onclick = () => {
          ui.stars[opt.id] = !ui.stars[opt.id];
          saveState();
          renderAll();
        };
        card.querySelector('[data-note]').oninput = ev => {
          ui.notes[opt.id] = ev.target.value;
          saveState();
        };
        container.appendChild(card);
      }
    };

    renderOptionCards(grassGrid, data.grass_possibilities, 'grass_opt');
    renderOptionCards(forestGrid, data.forest_possibilities, 'forest_opt');
    renderSandbox();
    drawFrame(ui.tick);
  }

  function drawFrame(tick) {
    for (const item of canvases) {
      if (item.type === 'env') {
        drawEnvCardCanvas(item, tick);
      } else if (item.type === 'grass_opt') {
        drawGrassOption(item, tick);
      } else if (item.type === 'forest_opt') {
        drawForestOption(item, tick);
      }
    }
    drawSandboxPreview(tick);
  }

  function bindControls() {
    const filterEl = document.getElementById('owt-filter');
    const regionEl = document.getElementById('owt-region');
    const zoomEl = document.getElementById('owt-zoom');
    const speedEl = document.getElementById('owt-speed');
    const playEl = document.getElementById('owt-play');
    const stepEl = document.getElementById('owt-step');
    const gridEl = document.getElementById('owt-grid');
    const sbTargetEl = document.getElementById('owt-sb-target');
    const sbCloneEl = document.getElementById('owt-sb-clone');
    const sbShiftLEl = document.getElementById('owt-sb-shiftl');
    const sbShiftREl = document.getElementById('owt-sb-shiftr');
    const sbResetEl = document.getElementById('owt-sb-reset');
    const sbCopyEl = document.getElementById('owt-sb-copy');
    const copyMdEl = document.getElementById('owt-copy-md');

    if (filterEl) filterEl.onchange = () => { ui.filter = filterEl.value; renderAll(); };
    if (regionEl) regionEl.onchange = () => { ui.region = regionEl.value; drawFrame(ui.tick); renderSandbox(); };
    if (zoomEl) zoomEl.onchange = () => { ui.zoom = Number(zoomEl.value); drawFrame(ui.tick); };
    if (speedEl) speedEl.onchange = () => { ui.speed = Number(speedEl.value); };
    if (playEl) {
      playEl.onclick = () => {
        ui.playing = !ui.playing;
        playEl.textContent = ui.playing ? 'Pause' : 'Play';
      };
    }
    if (stepEl) {
      stepEl.onclick = () => {
        ui.playing = false;
        if (playEl) playEl.textContent = 'Play';
        ui.tick += 1;
        drawFrame(ui.tick);
      };
    }
    if (gridEl) {
      gridEl.onchange = () => {
        ui.showGrid = gridEl.checked;
        drawFrame(ui.tick);
      };
    }
    if (sbTargetEl) {
      sbTargetEl.onchange = () => {
        ui.sbTarget = sbTargetEl.value;
        renderSandbox();
        drawSandboxPreview(ui.tick);
      };
    }
    if (sbCloneEl) {
      sbCloneEl.onclick = () => {
        const frames = getSandboxFrames(ui.sbTarget);
        frames[ui.sbFrame] = [...frames[0]];
        saveState();
        renderSandbox();
      };
    }
    const shiftSandboxRow = dir => {
      const frames = getSandboxFrames(ui.sbTarget);
      const cur = frames[ui.sbFrame];
      const next = [...cur];
      for (let r = 0; r < 8; r++) {
        for (let c = 0; c < 8; c++) {
          const nc = (c - dir + 8) % 8;
          next[r * 8 + c] = cur[r * 8 + nc];
        }
      }
      frames[ui.sbFrame] = next;
      saveState();
      renderSandbox();
    };
    if (sbShiftLEl) sbShiftLEl.onclick = () => shiftSandboxRow(-1);
    if (sbShiftREl) sbShiftREl.onclick = () => shiftSandboxRow(1);
    if (sbResetEl) {
      sbResetEl.onclick = () => {
        delete ui.sandbox[ui.sbTarget];
        saveState();
        renderSandbox();
        showToast('Sandbox reset to base ROM tile');
      };
    }
    if (sbCopyEl) {
      sbCopyEl.onclick = async () => {
        const frames = getSandboxFrames(ui.sbTarget);
        const lines = frames.map((f, idx) => {
          const rows = [];
          for (let r = 0; r < 8; r++) {
            rows.push("'" + f.slice(r * 8, (r + 1) * 8).join('') + "'");
          }
          return `    # ${ui.sbTarget} frame ${idx}\n    encode_tile([\n        ${rows.join(',\n        ')},\n    ]),`;
        });
        const text = `[\n${lines.join('\n')}\n]`;
        try {
          await navigator.clipboard.writeText(text);
          showToast('Copied Python encode_tile() snippet');
        } catch {
          showToast('Clipboard blocked; check console');
          console.log(text);
        }
      };
    }
    if (copyMdEl) {
      copyMdEl.onclick = async () => {
        const lines = ['# Overworld Tile Animation Notes', ''];
        for (const group of [
          ['Grass ($6D)', data.grass_possibilities],
          ['Forest ($68-$6B)', data.forest_possibilities],
        ]) {
          lines.push(`## ${group[0]}`);
          for (const opt of group[1]) {
            const star = ui.stars[opt.id] ? ' [SHORTLISTED]' : '';
            const note = ui.notes[opt.id] ? ` — ${ui.notes[opt.id]}` : '';
            lines.push(`- **${opt.name}**${star}${note}`);
          }
          lines.push('');
        }
        try {
          await navigator.clipboard.writeText(lines.join('\n'));
          showToast('Copied Markdown iteration notes');
        } catch {
          showToast('Clipboard blocked');
        }
      };
    }
  }

  let rafId = null;
  let lastTs = 0;
  let accum = 0;
  function loop(ts) {
    if (!ui.isActiveTab) {
      rafId = null;
      return;
    }
    if (!lastTs) lastTs = ts;
    const dt = Math.min(100, ts - lastTs);
    lastTs = ts;
    if (ui.playing) {
      accum += dt * ui.speed;
      const stepMs = 1000 / 60;
      if (accum >= stepMs) {
        const steps = Math.floor(accum / stepMs);
        accum -= steps * stepMs;
        ui.tick += steps;
        drawFrame(ui.tick);
      }
    }
    rafId = requestAnimationFrame(loop);
  }

  window.addEventListener('barba:tab', ev => {
    const active = ev.detail && ev.detail.tab === 'owtiles';
    ui.isActiveTab = active;
    if (active && !rafId) {
      lastTs = 0;
      rafId = requestAnimationFrame(loop);
    }
  });

  bindControls();
  renderAll();
})();
