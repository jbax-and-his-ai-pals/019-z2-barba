(() => {
  const data = window.BARBA_SUBGAMES_DATA;
  if (!data || !Array.isArray(data.games)) return;

  const isPublic = window.BARBA_DASHBOARD_FLAVOR === 'public';
  const gameById = Object.fromEntries(data.games.map(g => [g.id, g]));
  const renderedTabs = new Set();
  const activeCanvases = [];
  const imgCache = new Map();
  let activeSubTab = null;

  const canvasObserver = ('IntersectionObserver' in window)
    ? new IntersectionObserver(entries => {
        for (const entry of entries) entry.target._vis = entry.isIntersecting;
      }, { rootMargin: '150px' })
    : null;

  function loadSheetImage(src) {
    if (!imgCache.has(src)) {
      const img = new Image();
      img.src = src;
      imgCache.set(src, img);
    }
    return imgCache.get(src);
  }

  function createAnimCanvas(src, w, h, frames, fps, tabKey) {
    const targetW = 512;
    const targetH = Math.round(h * (targetW / w));
    const cv = document.createElement('canvas');
    cv.className = 'nes-canvas';
    cv.width = targetW;
    cv.height = targetH;
    cv._vis = !canvasObserver;
    if (canvasObserver) canvasObserver.observe(cv);
    const ctx = cv.getContext('2d');
    ctx.imageSmoothingEnabled = false;
    activeCanvases.push({
      cv,
      ctx,
      src,
      tabKey,
      img: null,
      w,
      h,
      frames: Math.max(1, frames || 1),
      fps: Math.max(1, fps || 12),
      idx: 0,
      drawnIdx: -1,
      acc: 0,
    });
    return cv;
  }

  let lastTick = performance.now();
  let tickRaf = 0;

  function ensureTicking() {
    if (tickRaf || document.hidden || !activeSubTab) return;
    lastTick = performance.now();
    tickRaf = requestAnimationFrame(tickCanvases);
  }

  function tickCanvases(now) {
    tickRaf = 0;
    if (document.hidden || !activeSubTab) return;
    const dt = Math.min(0.1, (now - lastTick) / 1000);
    lastTick = now;

    for (let i = activeCanvases.length - 1; i >= 0; i--) {
      const item = activeCanvases[i];
      if (!item.cv.isConnected) {
        if (canvasObserver) canvasObserver.unobserve(item.cv);
        activeCanvases.splice(i, 1);
        continue;
      }
      if (item.tabKey !== activeSubTab) continue;
      if (item.cv._vis === false) continue;

      if (!item.img) item.img = loadSheetImage(item.src);
      if (!item.img.complete || item.img.naturalWidth === 0) continue;

      if (item.frames > 1) {
        item.acc += dt;
        const step = 1 / item.fps;
        if (item.acc >= step) {
          item.idx = (item.idx + Math.floor(item.acc / step)) % item.frames;
          item.acc %= step;
        }
      }
      if (item.idx === item.drawnIdx) continue;
      item.drawnIdx = item.idx;

      const ctx = item.ctx;
      ctx.imageSmoothingEnabled = false;
      ctx.clearRect(0, 0, item.cv.width, item.cv.height);
      const cols = Math.max(1, Math.floor(item.img.naturalWidth / item.w));
      const rows = Math.max(1, Math.floor(item.img.naturalHeight / item.h));
      const drawIdx = item.idx % Math.max(1, Math.min(item.frames, cols * rows));
      const sx = (drawIdx % cols) * item.w;
      const sy = Math.floor(drawIdx / cols) * item.h;
      ctx.drawImage(item.img, sx, sy, item.w, item.h, 0, 0, item.cv.width, item.cv.height);
    }

    tickRaf = requestAnimationFrame(tickCanvases);
  }

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && activeSubTab) ensureTicking();
  });

  function makeTile(side, scene, isModded, tabKey) {
    const tile = document.createElement('div');
    tile.className = 'subgame-tile' + (isModded ? ' is-modded' : '');
    tile.appendChild(createAnimCanvas(side.img, scene.w, scene.h, scene.frames, scene.fps, tabKey));

    const label = document.createElement('div');
    label.className = 'choice-label';
    const badge = document.createElement('span');
    badge.className = isModded ? 'pill-on' : 'badge';
    badge.textContent = isModded ? 'Modded' : 'Vanilla';
    const text = document.createElement('span');
    text.textContent = side.label;
    label.append(badge, text);
    tile.appendChild(label);
    return tile;
  }

  function makeLocalBanner(titleText, subText) {
    const banner = document.createElement('div');
    banner.className = 'local-only-banner';
    banner.setAttribute('role', 'note');
    const title = document.createElement('span');
    title.textContent = titleText;
    const sub = document.createElement('span');
    sub.className = 'local-sub';
    sub.textContent = subText;
    banner.append(title, sub);
    return banner;
  }

  function renderSubgame(gameId) {
    const tabKey = `sub-${gameId}`;
    if (renderedTabs.has(tabKey)) return;
    const container = document.getElementById(`view-${tabKey}`);
    const game = gameById[gameId];
    if (!container || !game) return;
    if (isPublic && game.visibility === 'local') return;
    const scenes = isPublic ? game.scenes.filter(s => s.visibility !== 'local') : game.scenes;
    if (isPublic && !scenes.length) return;
    renderedTabs.add(tabKey);

    const isGameLocal = !isPublic && game.visibility === 'local';
    const localSceneCount = isPublic ? 0 : scenes.filter(s => s.visibility === 'local').length;

    const header = document.createElement('section');
    header.className = 'top-box' + (isGameLocal ? ' local-only-card' : '');
    header.setAttribute('aria-label', `${game.name} Overview`);
    const headerArchivedBadge = game.archived
      ? '<span class="badge b-archived">Archived · Post-2.0</span>'
      : '';
    const headerLocalBadge = isGameLocal
      ? '<span class="badge b-local">Local Only Game</span>'
      : (localSceneCount > 0 ? `<span class="badge b-local">${localSceneCount} Local Only</span>` : '');
    header.innerHTML = `
      <div class="row" style="justify-content:space-between;align-items:baseline;">
        <div>
          <strong style="font-size:1.1rem;color:var(--gold);">${game.name}</strong>
          <span class="subtitle" style="margin-left:8px;">(${game.original})</span>
        </div>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
          ${headerArchivedBadge}
          ${headerLocalBadge}
          <span class="badge b-built">Vanilla vs. Modded</span>
        </div>
      </div>
      <div class="subtitle" style="margin:0;">${game.summary}</div>
    `;
    if (isGameLocal) {
      header.appendChild(makeLocalBanner(
        'Local Only Game — Not Published on GitHub Pages',
        'This entire tab is omitted from public builds until marked public.'
      ));
    }
    container.appendChild(header);

    const grid = document.createElement('main');
    grid.className = 'grid';

    for (const scene of scenes) {
      const isSceneLocal = !isPublic && (isGameLocal || scene.visibility === 'local');
      const card = document.createElement('section');
      card.className = 'card' + (isSceneLocal ? ' local-only-card' : '');

      const head = document.createElement('div');
      head.className = 'flag-head';
      head.style.cssText = 'border-bottom:1px solid var(--border);padding-bottom:8px;';

      const h2 = document.createElement('h2');
      h2.style.cssText = 'border:none;padding:0;margin:0;';
      h2.textContent = scene.title;
      head.appendChild(h2);

      if (isSceneLocal) {
        const localBadge = document.createElement('span');
        localBadge.className = 'badge b-local';
        localBadge.textContent = 'Local Only · Hidden on GitHub Pages';
        head.appendChild(localBadge);
      }
      card.appendChild(head);

      if (!isPublic && !isGameLocal && scene.visibility === 'local') {
        card.appendChild(makeLocalBanner(
          'Local Only — Not Published on GitHub Pages',
          'Visible only in the local dashboard until unveiled.'
        ));
      }

      const desc = document.createElement('div');
      desc.className = 'flag-desc';
      desc.textContent = scene.description;
      card.appendChild(desc);

      const compare = document.createElement('div');
      compare.className = 'preview-compare';
      compare.appendChild(makeTile(scene.vanilla, scene, false, tabKey));
      compare.appendChild(makeTile(scene.modded, scene, true, tabKey));
      card.appendChild(compare);

      grid.appendChild(card);
    }

    container.appendChild(grid);
  }

  function handleTabChange(tab) {
    const prevTab = activeSubTab;
    if (typeof tab === 'string' && tab.startsWith('sub-')) {
      const gid = tab.slice(4);
      if (prevTab && prevTab !== tab) {
        imgCache.clear();
        for (const item of activeCanvases) {
          if (item.tabKey !== tab) {
            item.img = null;
            item.drawnIdx = -1;
          }
        }
      }
      activeSubTab = tab;
      renderSubgame(gid);
      ensureTicking();
    } else {
      activeSubTab = null;
      imgCache.clear();
      for (const item of activeCanvases) {
        item.img = null;
        item.drawnIdx = -1;
      }
    }
  }

  for (const g of data.games) {
    const el = document.getElementById(`view-sub-${g.id}`);
    if (el && !el.classList.contains('hidden')) {
      handleTabChange(`sub-${g.id}`);
      break;
    }
  }

  window.addEventListener('barba:tab', e => {
    handleTabChange(e.detail?.tab);
  });
})();
