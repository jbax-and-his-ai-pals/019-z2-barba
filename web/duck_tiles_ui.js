(() => {
  const data = window.DUCK_TILES_DATA;
  if (!data) return;

  const NES_PAL = data.nes_palette;
  const palettes = data.palettes;

  const TAG_OPTIONS = [
    { value: 'ok', label: 'OK' },
    { value: 'inspect_chr', label: 'Inspect CHR (Something Wrong)' },
    { value: 'top_half_only', label: 'Is Top Half Only' },
    { value: 'needs_bottom_half', label: 'Needs Bottom Half' },
    { value: 'wrong_tiles', label: 'Wrong Source Tiles' },
    { value: 'wrong_pal', label: 'Wrong Palette' },
    { value: 'misaligned', label: 'Misaligned / Clipped' },
    { value: 'duplicate', label: 'Duplicate / Nix' },
  ];
  const STORAGE_KEY = 'barba_duck_tile_tags_v1';
  const NOTES_KEY = 'barba_duck_tile_notes_v1';

  function loadTags() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    } catch {
      return {};
    }
  }
  function saveTags(tags) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(tags));
    } catch {}
  }
  function loadNotes() {
    try {
      return JSON.parse(localStorage.getItem(NOTES_KEY) || '{}');
    } catch {
      return {};
    }
  }
  function saveNotes(notes) {
    try {
      localStorage.setItem(NOTES_KEY, JSON.stringify(notes));
    } catch {}
  }

  const ui = {
    subtab: 'all',
    category: 'all',
    tagFilter: 'all',
    backdrop: 'sky',
    zoom: 4,
    animMode: 'animate',
    showGrid: true,
    bankId: 'r0_villagers',
    bankPal: 'spr0',
    bankZoom: 3,
    bgPal: 'bg_forest',
    highlightTids: null, // { bank: string, tids: Set<number> }
    animTick: 0,
    palOverrides: {}, // sprite.id -> palIdx
    tags: loadTags(), // sprite.id -> tag value
    notes: loadNotes(), // sprite.id -> note string
  };

  const rgbCss = idx => {
    const [r, g, b] = NES_PAL[idx & 0x3f];
    return `rgb(${r},${g},${b})`;
  };

  function drawGridToCanvas(canvas, flatPixels, w, h, palColors, zoom, backdrop, tileMap, showGrid) {
    const targetW = w * zoom;
    const targetH = h * zoom;
    if (canvas.width !== targetW) canvas.width = targetW;
    if (canvas.height !== targetH) canvas.height = targetH;
    const ctx = canvas.getContext('2d');
    ctx.imageSmoothingEnabled = false;

    // Backdrop
    if (backdrop === 'sky') {
      ctx.fillStyle = rgbCss(0x21);
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    } else if (backdrop === 'forest') {
      ctx.fillStyle = rgbCss(0x0f);
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    } else if (backdrop === 'dark') {
      ctx.fillStyle = '#0d1017';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    } else {
      const sz = Math.max(4, zoom * 2);
      for (let y = 0; y < canvas.height; y += sz) {
        for (let x = 0; x < canvas.width; x += sz) {
          ctx.fillStyle = ((x / sz + y / sz) & 1) ? '#1c212c' : '#262d3c';
          ctx.fillRect(x, y, sz, sz);
        }
      }
    }

    // Pixels
    for (let y = 0; y < h; y++) {
      const rowOff = y * w;
      for (let x = 0; x < w; x++) {
        const c = flatPixels.charCodeAt(rowOff + x) - 48;
        if (c > 0 && c <= 3) {
          ctx.fillStyle = rgbCss(palColors[c]);
          ctx.fillRect(x * zoom, y * zoom, zoom, zoom);
        }
      }
    }

    if (showGrid) {
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.22)';
      ctx.lineWidth = 1;
      for (let x = 8; x < w; x += 8) {
        ctx.beginPath();
        ctx.moveTo(x * zoom + 0.5, 0);
        ctx.lineTo(x * zoom + 0.5, canvas.height);
        ctx.stroke();
      }
      for (let y = 8; y < h; y += 8) {
        ctx.beginPath();
        ctx.moveTo(0, y * zoom + 0.5);
        ctx.lineTo(canvas.width, y * zoom + 0.5);
        ctx.stroke();
      }
      if (tileMap && zoom >= 3) {
        const cols = w / 8;
        ctx.font = `bold ${Math.max(8, zoom * 2 + 1)}px ui-monospace, monospace`;
        ctx.textBaseline = 'top';
        tileMap.forEach((tid, idx) => {
          if (tid === 0xff) return;
          const tx = (idx % cols) * 8 * zoom;
          const ty = Math.floor(idx / cols) * 8 * zoom;
          const label = tid.toString(16).toUpperCase().padStart(2, '0');
          ctx.fillStyle = 'rgba(0,0,0,0.65)';
          ctx.fillRect(tx + 1, ty + 1, 14, 10);
          ctx.fillStyle = '#ffd166';
          ctx.fillText(label, tx + 2, ty + 1);
        });
      }
    }
  }

  function renderStats() {
    const tc = data.tile_counts;
    const flagged = data.sprites.filter(s => (ui.tags[s.id] || 'ok') !== 'ok').length;
    const noted = data.sprites.filter(s => (ui.notes[s.id] || '').trim().length > 0).length;
    const z2Count = data.sprites.filter(s => s.category.startsWith('z2_')).length;
    const el = document.getElementById('duck-stats');
    el.innerHTML = [
      `<span class="stat">R0 A: <strong>${tc.villagers}/96</strong></span>`,
      `<span class="stat">R0 B: <strong>${tc.villagers2 ?? 0}/96</strong></span>`,
      `<span class="stat">R0 C: <strong>${tc.villagers3 ?? 0}/96</strong></span>`,
      `<span class="stat">R0 D: <strong>${tc.villagers4 ?? 0}/96</strong></span>`,
      `<span class="stat">R0 E: <strong>${tc.villagers5 ?? 0}/96</strong></span>`,
      `<span class="stat">Clay: <strong>${tc.clay}/96</strong></span>`,
      `<span class="stat">Barba: <strong>${tc.barba}/112</strong></span>`,
      `<span class="stat">Z2 Ref: <strong>${z2Count}</strong></span>`,
      `<span class="stat">Total: <strong>${data.sprites.length}</strong></span>`,
      `<span class="stat">Flagged: <strong>${flagged}</strong></span>`,
      `<span class="stat">Notes: <strong>${noted}</strong></span>`,
    ].join('');
  }

  function renderSprites() {
    const grid = document.getElementById('duck-sprite-grid');
    grid.innerHTML = '';

    const items = data.sprites.filter(s => {
      if (ui.subtab !== 'all' && s.tab !== ui.subtab) return false;
      if (ui.category === 'z2_all') {
        if (!s.category.startsWith('z2_')) return false;
      } else if (ui.category === 'dh_mismatch') {
        if (s.mapping_status !== 'mismatch') return false;
      } else if (ui.category !== 'all' && s.category !== ui.category) {
        return false;
      }
      const tag = ui.tags[s.id] || 'ok';
      if (ui.tagFilter === 'flagged') return tag !== 'ok';
      if (ui.tagFilter !== 'all' && tag !== ui.tagFilter) return false;
      return true;
    });
    for (const spr of items) {
      const card = document.createElement('div');
      const curTag = ui.tags[spr.id] || 'ok';
      card.className = 'duck-card';
      if (curTag !== 'ok') card.classList.add('is-flagged');
      if (ui.highlightTids && ui.highlightTids.spriteId === spr.id) {
        card.classList.add('is-selected');
      }

      const head = document.createElement('div');
      head.className = 'duck-card-head';
      const title = document.createElement('strong');
      title.textContent = spr.name;
      const badge = document.createElement('span');
      badge.className = 'duck-badge';
      badge.textContent = `${spr.w}x${spr.h}`;
      head.append(title, badge);
      card.appendChild(head);

      const frameIdx =
        ui.animMode === 'animate'
          ? ui.animTick % spr.frames.length
          : Math.min(Number(ui.animMode), spr.frames.length - 1);

      const palIdx = ui.palOverrides[spr.id] ?? spr.pal;
      const palColors = palettes[`spr${palIdx}`].colors;
      const tmap = spr.tile_maps ? spr.tile_maps[frameIdx] : null;

      const wrap = document.createElement('div');
      wrap.className = 'duck-canvas-wrap';
      const canvas = document.createElement('canvas');
      drawGridToCanvas(
        canvas,
        spr.frames[frameIdx],
        spr.w,
        spr.h,
        palColors,
        spr.w > 32 ? Math.min(ui.zoom, 3) : ui.zoom,
        ui.backdrop,
        tmap,
        ui.showGrid
      );
      wrap.appendChild(canvas);
      card.appendChild(wrap);

      const meta = document.createElement('div');
      meta.className = 'duck-meta';
      meta.textContent = spr.source || '';
      card.appendChild(meta);

      if (spr.dh_mapping) {
        const mapBadge = document.createElement('div');
        mapBadge.className = 'duck-meta';
        mapBadge.style.padding = '3px 6px';
        mapBadge.style.borderRadius = '4px';
        mapBadge.style.fontWeight = '600';
        if (spr.mapping_status === 'match') {
          mapBadge.style.background = 'rgba(76, 208, 108, 0.14)';
          mapBadge.style.color = '#7ae582';
        } else if (spr.mapping_status === 'mismatch') {
          mapBadge.style.background = 'rgba(255, 107, 107, 0.16)';
          mapBadge.style.color = '#ff8787';
        } else {
          mapBadge.style.background = 'rgba(148, 163, 184, 0.12)';
          mapBadge.style.color = '#94a3b8';
        }
        mapBadge.textContent = spr.dh_mapping;
        card.appendChild(mapBadge);
      }

      const controls = document.createElement('div');
      controls.className = 'duck-card-controls';

      const palSel = document.createElement('select');
      for (let p = 0; p < 4; p++) {
        const opt = document.createElement('option');
        opt.value = String(p);
        opt.textContent = `Pal ${p}${p === spr.pal ? ' (def)' : ''}`;
        if (p === palIdx) opt.selected = true;
        palSel.appendChild(opt);
      }
      palSel.onchange = () => {
        ui.palOverrides[spr.id] = Number(palSel.value);
        card._updateFrame();
        if (ui.highlightTids && ui.highlightTids.spriteId === spr.id) {
          ui.bankPal = `spr${palSel.value}`;
          document.getElementById('duck-bank-pal').value = ui.bankPal;
          renderChrBank();
        }
      };

      const inspectBtn = document.createElement('button');
      inspectBtn.type = 'button';
      inspectBtn.className = 'feud-mini-btn';
      inspectBtn.textContent = 'Inspect CHR';
      inspectBtn.onclick = () => {
        const tids = new Set();
        if (tmap) {
          tmap.forEach(t => { if (t !== 0xff) tids.add(t); });
        } else if (spr.metasprite) {
          spr.metasprite.forEach(([t]) => tids.add(t));
        } else if (spr.highlight_tids) {
          spr.highlight_tids.forEach(t => tids.add(t));
        }
        ui.bankId = spr.chr_bank;
        ui.bankPal = `spr${palIdx}`;
        ui.highlightTids = { spriteId: spr.id, bank: spr.chr_bank, tids };
        document.getElementById('duck-bank-sel').value = ui.bankId;
        document.getElementById('duck-bank-pal').value = ui.bankPal;
        renderSprites();
        renderChrBank();
        document.getElementById('duck-chr-panel').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      };

      controls.append(palSel, inspectBtn);
      card.appendChild(controls);

      const tagRow = document.createElement('div');
      tagRow.className = 'duck-card-controls';
      const tagSel = document.createElement('select');
      tagSel.style.width = '100%';
      for (const optDef of TAG_OPTIONS) {
        const opt = document.createElement('option');
        opt.value = optDef.value;
        opt.textContent = optDef.label;
        if (optDef.value === curTag) opt.selected = true;
        tagSel.appendChild(opt);
      }
      tagSel.onchange = () => {
        if (tagSel.value === 'ok') {
          delete ui.tags[spr.id];
        } else {
          ui.tags[spr.id] = tagSel.value;
        }
        saveTags(ui.tags);
        renderStats();
        card.classList.toggle('is-flagged', tagSel.value !== 'ok');
        if (ui.tagFilter !== 'all') {
          renderSprites();
        }
      };
      tagRow.appendChild(tagSel);
      card.appendChild(tagRow);

      const noteBox = document.createElement('textarea');
      noteBox.rows = 2;
      noteBox.placeholder = 'Jot notes for this character...';
      noteBox.value = ui.notes[spr.id] || '';
      noteBox.style.cssText = 'width:100%;box-sizing:border-box;font-size:0.74rem;padding:4px 6px;border-radius:4px;border:1px solid rgba(255,255,255,0.14);background:#0f1420;color:#e6edf7;resize:vertical;font-family:inherit;';
      noteBox.oninput = () => {
        const val = noteBox.value;
        if (val.trim()) {
          ui.notes[spr.id] = val;
        } else {
          delete ui.notes[spr.id];
        }
        saveNotes(ui.notes);
        renderStats();
      };
      card.appendChild(noteBox);

      if (spr.metasprite) {
        const mapLine = document.createElement('div');
        mapLine.className = 'duck-tile-list';
        mapLine.textContent = `${spr.metasprite.length} OAM tiles in R1`;
        card.appendChild(mapLine);
      }

      let lastFrameKey = `${frameIdx}|${palIdx}|${ui.zoom}|${ui.backdrop}|${ui.showGrid}`;
      card._updateFrame = () => {
        const nextFrame =
          ui.animMode === 'animate'
            ? ui.animTick % spr.frames.length
            : Math.min(Number(ui.animMode), spr.frames.length - 1);
        const nextPalIdx = ui.palOverrides[spr.id] ?? spr.pal;
        const frameKey = `${nextFrame}|${nextPalIdx}|${ui.zoom}|${ui.backdrop}|${ui.showGrid}`;
        if (frameKey === lastFrameKey) return;
        lastFrameKey = frameKey;
        const nextPalColors = palettes[`spr${nextPalIdx}`].colors;
        const nextTmap = spr.tile_maps ? spr.tile_maps[nextFrame] : null;
        drawGridToCanvas(
          canvas,
          spr.frames[nextFrame],
          spr.w,
          spr.h,
          nextPalColors,
          spr.w > 32 ? Math.min(ui.zoom, 3) : ui.zoom,
          ui.backdrop,
          nextTmap,
          ui.showGrid
        );
      };

      grid.appendChild(card);
    }
  }

  function renderBgDiffs() {
    const wrap = document.getElementById('duck-bg-diffs');
    wrap.innerHTML = '';
    const palColors = palettes[ui.bgPal].colors;
    const z = 4;

    for (const item of data.bg_patches) {
      const card = document.createElement('div');
      card.className = 'duck-diff-card';

      const head = document.createElement('div');
      head.className = 'duck-diff-head';
      head.innerHTML = `<strong>$${item.tid.toString(16).toUpperCase().padStart(2, '0')}</strong> <span>${item.bank}</span>`;
      card.appendChild(head);

      const row = document.createElement('div');
      row.className = 'duck-diff-row';

      const addTileBox = (label, flat) => {
        const box = document.createElement('div');
        box.className = 'duck-diff-slot';
        const c = document.createElement('canvas');
        drawGridToCanvas(c, flat, 8, 8, palColors, z, 'dark', null, false);
        const cap = document.createElement('span');
        cap.textContent = label;
        box.append(c, cap);
        row.appendChild(box);
      };

      addTileBox('Vanilla', item.orig);
      addTileBox('Patched', item.patched);
      if (item.z2_src) {
        addTileBox('Z2 Src', item.z2_src);
      }
      card.appendChild(row);

      const note = document.createElement('div');
      note.className = 'duck-meta';
      note.textContent = item.note;
      card.appendChild(note);

      wrap.appendChild(card);
    }
  }

  function renderChrBank() {
    const bank = data.chr_banks.find(b => b.id === ui.bankId) || data.chr_banks[0];
    const palColors = palettes[ui.bankPal].colors;
    const z = ui.bankZoom;
    const cell = 8 * z + 1;
    const cols = 16;
    const rows = Math.ceil(bank.tiles.length / cols);
    const padL = 26;
    const padT = 18;

    const canvas = document.getElementById('duck-chr-canvas');
    canvas.width = padL + cols * cell + 1;
    canvas.height = padT + rows * cell + 1;
    const ctx = canvas.getContext('2d');
    ctx.imageSmoothingEnabled = false;
    ctx.fillStyle = '#0d1017';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Column & row hex headers
    ctx.font = '11px ui-monospace, monospace';
    ctx.fillStyle = '#8b95a7';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    for (let cx = 0; cx < cols; cx++) {
      ctx.fillText(cx.toString(16).toUpperCase(), padL + cx * cell + (8 * z) / 2, padT / 2);
    }
    ctx.textAlign = 'right';
    for (let ry = 0; ry < rows; ry++) {
      const rowTid = bank.base_tid + ry * 16;
      ctx.fillText(rowTid.toString(16).toUpperCase().padStart(2, '0'), padL - 5, padT + ry * cell + (8 * z) / 2);
    }

    const hl = ui.highlightTids && ui.highlightTids.bank === bank.id ? ui.highlightTids.tids : null;

    for (let i = 0; i < bank.tiles.length; i++) {
      const tx = i % cols;
      const ty = Math.floor(i / cols);
      const ox = padL + tx * cell;
      const oy = padT + ty * cell;
      const flat = bank.tiles[i];

      ctx.fillStyle = rgbCss(palColors[0]);
      ctx.fillRect(ox, oy, 8 * z, 8 * z);

      for (let py = 0; py < 8; py++) {
        for (let px = 0; px < 8; px++) {
          const c = flat.charCodeAt(py * 8 + px) - 48;
          if (c > 0 && c <= 3) {
            ctx.fillStyle = rgbCss(palColors[c]);
            ctx.fillRect(ox + px * z, oy + py * z, z, z);
          }
        }
      }

      const tid = bank.base_tid + i;
      if (hl && hl.has(tid)) {
        ctx.strokeStyle = '#ffd166';
        ctx.lineWidth = 2;
        ctx.strokeRect(ox + 1, oy + 1, 8 * z - 2, 8 * z - 2);
      }
    }

    canvas.onmousemove = ev => {
      const rect = canvas.getBoundingClientRect();
      const mx = ev.clientX - rect.left - padL;
      const my = ev.clientY - rect.top - padT;
      const tx = Math.floor(mx / cell);
      const ty = Math.floor(my / cell);
      const info = document.getElementById('duck-chr-hover');
      if (tx < 0 || tx >= cols || ty < 0 || ty >= rows) {
        info.textContent = 'Hover any tile to inspect its $ID';
        return;
      }
      const idx = ty * cols + tx;
      if (idx >= bank.tiles.length) return;
      const tid = bank.base_tid + idx;
      info.textContent = `${bank.label} — Tile $${tid.toString(16).toUpperCase().padStart(2, '0')} (index ${idx})`;
      const zoomCanvas = document.getElementById('duck-chr-zoom');
      drawGridToCanvas(zoomCanvas, bank.tiles[idx], 8, 8, palColors, 8, 'dark', null, true);
    };
  }

  function initControls() {
    const bankSel = document.getElementById('duck-bank-sel');
    const groups = [
      ['compiled', 'Compiled Barba\'s Hunt Banks'],
      ['vanilla', 'Vanilla Duck Hunt'],
      ['z2', 'Zelda II Source Banks'],
    ];
    for (const [gKey, gLabel] of groups) {
      const og = document.createElement('optgroup');
      og.label = gLabel;
      for (const b of data.chr_banks.filter(x => x.group === gKey)) {
        const opt = document.createElement('option');
        opt.value = b.id;
        opt.textContent = b.label;
        og.appendChild(opt);
      }
      bankSel.appendChild(og);
    }
    bankSel.value = ui.bankId;
    bankSel.onchange = () => {
      ui.bankId = bankSel.value;
      const b = data.chr_banks.find(x => x.id === ui.bankId);
      if (b && b.default_pal) {
        ui.bankPal = b.default_pal;
        document.getElementById('duck-bank-pal').value = ui.bankPal;
      }
      renderChrBank();
    };

    const palSel = document.getElementById('duck-bank-pal');
    const bgPalSel = document.getElementById('duck-bg-pal');
    for (const [k, p] of Object.entries(palettes)) {
      const opt1 = document.createElement('option');
      opt1.value = k;
      opt1.textContent = p.label;
      palSel.appendChild(opt1);

      const opt2 = document.createElement('option');
      opt2.value = k;
      opt2.textContent = p.label;
      bgPalSel.appendChild(opt2);
    }
    palSel.value = ui.bankPal;
    palSel.onchange = () => { ui.bankPal = palSel.value; renderChrBank(); };
    bgPalSel.value = ui.bgPal;
    bgPalSel.onchange = () => { ui.bgPal = bgPalSel.value; renderBgDiffs(); };

    const catSel = document.getElementById('duck-cat');
    if (data.categories) {
      catSel.innerHTML = '';
      const counts = {};
      for (const s of data.sprites) {
        counts[s.category] = (counts[s.category] || 0) + 1;
      }
      const z2Total = data.sprites.filter(s => s.category.startsWith('z2_')).length;
      const mismatchTotal = data.sprites.filter(s => s.mapping_status === 'mismatch').length;
      const opts = [
        ['all', `All Sprites (${data.sprites.length})`],
        ['z2_all', `All Z2 Enemies & Bosses (${z2Total})`],
        ['dh_mismatch', `DH 1:1 Mismatches (${mismatchTotal})`],
        ...data.categories.map(([val, label]) => [val, `${label} (${counts[val] || 0})`]),
      ];
      for (const [val, label] of opts) {
        const opt = document.createElement('option');
        opt.value = val;
        opt.textContent = label;
        catSel.appendChild(opt);
      }
    }
    catSel.value = ui.category;
    catSel.onchange = e => { ui.category = e.target.value; renderSprites(); };
    document.getElementById('duck-tag-filter').onchange = e => { ui.tagFilter = e.target.value; renderSprites(); };
    document.getElementById('duck-bg').onchange = e => { ui.backdrop = e.target.value; renderSprites(); };
    document.getElementById('duck-zoom').onchange = e => { ui.zoom = Number(e.target.value); renderSprites(); };
    const animSel = document.getElementById('duck-anim');
    animSel.value = ui.animMode;
    animSel.onchange = e => { ui.animMode = e.target.value; renderSprites(); };
    document.getElementById('duck-grid').onchange = e => { ui.showGrid = e.target.checked; renderSprites(); };
    document.getElementById('duck-bank-zoom').onchange = e => { ui.bankZoom = Number(e.target.value); renderChrBank(); };
    const subtabBar = document.getElementById('duck-subtabs');
    if (subtabBar) {
      const tabCounts = { all: data.sprites.length, barba: 0, dh_enemies: 0, z2_ref: 0 };
      for (const s of data.sprites) {
        if (s.tab && tabCounts[s.tab] !== undefined) tabCounts[s.tab]++;
      }
      for (const btn of subtabBar.querySelectorAll('[data-duck-tab]')) {
        const key = btn.getAttribute('data-duck-tab');
        const baseText = btn.textContent.replace(/\s*\(\d+\)$/, '');
        btn.textContent = `${baseText} (${tabCounts[key] ?? 0})`;
        btn.onclick = () => {
          ui.subtab = key;
          for (const b of subtabBar.querySelectorAll('[data-duck-tab]')) {
            b.classList.toggle('active', b === btn);
          }
          renderSprites();
        };
      }
    }

    document.getElementById('duck-copy-tags').onclick = () => {
      const report = data.sprites
        .filter(s => (ui.tags[s.id] || 'ok') !== 'ok' || (ui.notes[s.id] || '').trim().length > 0)
        .map(s => ({
          id: s.id,
          name: s.name,
          tag: ui.tags[s.id] || 'ok',
          note: (ui.notes[s.id] || '').trim(),
          source: s.source,
        }));
      navigator.clipboard.writeText(JSON.stringify(report, null, 2));
      document.getElementById('duck-toast').textContent = `Copied ${report.length} flagged/noted sprite(s) to clipboard.`;
    };
    document.getElementById('duck-reset-tags').onclick = () => {
      ui.tags = {};
      saveTags(ui.tags);
      renderStats();
      renderSprites();
      document.getElementById('duck-toast').textContent = 'Cleared all sprite tags.';
    };
  }

  initControls();
  let duckRendered = false;
  function ensureDuckRendered() {
    if (duckRendered) return;
    duckRendered = true;
    renderStats();
    renderSprites();
    renderBgDiffs();
    renderChrBank();
  }
  const viewDuck = document.getElementById('view-duck');
  if (viewDuck && !viewDuck.classList.contains('hidden')) {
    ensureDuckRendered();
  }
  window.addEventListener('barba:tab', e => {
    if (e.detail?.tab === 'duck') ensureDuckRendered();
  });

  let gridVisible = true;
  const spriteGrid = document.getElementById('duck-sprite-grid');
  if (spriteGrid) {
    if ('contentVisibility' in document.documentElement.style) {
      spriteGrid.addEventListener('contentvisibilityautostatechange', ev => {
        gridVisible = !ev.skipped;
      });
    } else if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver(entries => {
        for (const entry of entries) {
          gridVisible = entry.isIntersecting;
        }
      }, { rootMargin: '200px' });
      observer.observe(spriteGrid);
    }
  }

  setInterval(() => {
    const view = document.getElementById('view-duck');
    if (view && !view.classList.contains('hidden') && gridVisible && ui.animMode === 'animate') {
      ui.animTick++;
      const grid = document.getElementById('duck-sprite-grid');
      if (grid) {
        for (const card of grid.children) {
          if (card._updateFrame) card._updateFrame();
        }
      }
    }
  }, 500);
})();
