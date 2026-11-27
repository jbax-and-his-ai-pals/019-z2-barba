(() => {
  const data = window.TITLE_REVIEW_DATA;
  if (!data) return;

  const isPublic = window.BARBA_DASHBOARD_FLAVOR === 'public';
  const STORAGE_KEY = 'barba_title_review_v2';

  function loadState() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    } catch {
      return {};
    }
  }
  function saveState(st) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(st));
    } catch {}
  }

  const saved = loadState();
  const ui = {
    zoom: 2,
    gameNotes: saved.gameNotes || {},
    gameStatus: saved.gameStatus || {},
  };

  function persist() {
    saveState({
      gameNotes: ui.gameNotes,
      gameStatus: ui.gameStatus,
    });
  }

  function setToast(msg) {
    const el = document.getElementById('titles-toast');
    if (el) el.textContent = msg;
  }

  function buildMarkdownSummary() {
    const lines = ['# Title Screen Review Feedback', ''];
    for (const g of data.games) {
      if (isPublic && g.visibility === 'local') continue;
      const screens = isPublic ? g.screens.filter(s => s.visibility !== 'local') : g.screens;
      if (isPublic && !screens.length) continue;
      const st = ui.gameStatus[g.id] || 'approved';
      lines.push(`## ${g.name} [${st}]`);
      if (ui.gameNotes[g.id]) lines.push(`- Notes: ${ui.gameNotes[g.id]}`);
      lines.push('');
    }
    return lines.join('\n');
  }

  function renderSide(side, isOurs) {
    const box = document.createElement('div');
    box.className = 'flag-item' + (isOurs ? ' is-selected' : '');
    if (isOurs) box.style.borderColor = 'var(--ember)';
    box.innerHTML = `
      <div class="flag-head">
        <strong>${side.label}</strong>
        ${isOurs ? '<span class="pill-on">Our Version</span>' : '<span class="badge">Vanilla</span>'}
      </div>
      <img src="${side.img}" alt="${side.label}" loading="lazy" decoding="async" style="width:${256 * ui.zoom}px;max-width:100%;height:auto;image-rendering:pixelated;border-radius:6px;border:1px solid var(--border);">
      <div class="flag-desc">${side.caption}</div>
    `;
    return box;
  }

  function render() {
    const listEl = document.getElementById('titles-list');
    if (!listEl) return;
    listEl.innerHTML = '';

    for (const g of data.games) {
      if (isPublic && g.visibility === 'local') continue;
      const screens = isPublic ? g.screens.filter(s => s.visibility !== 'local') : g.screens;
      if (isPublic && !screens.length) continue;

      const isGameLocal = !isPublic && g.visibility === 'local';
      const localScreensCount = isPublic ? 0 : screens.filter(s => s.visibility === 'local').length;
      const card = document.createElement('section');
      card.className = 'card' + (isGameLocal ? ' local-only-card' : '');

      const curStatus = ui.gameStatus[g.id] || 'approved';
      const head = document.createElement('div');
      head.className = 'flag-head';
      const statusSelectHtml = isPublic ? '' : `
          <select class="title-game-status" data-game="${g.id}">
            <option value="needs_work" ${curStatus === 'needs_work' ? 'selected' : ''}>Needs Work</option>
            <option value="in_review" ${curStatus === 'in_review' ? 'selected' : ''}>In Review</option>
            <option value="approved" ${curStatus === 'approved' ? 'selected' : ''}>Sign Off / Approved</option>
          </select>`;
      const buildBadge = g.build_number != null
        ? `<span class="badge b-built">Build #${g.build_number}</span>`
        : `<span class="badge b-built">${g.status_label}</span>`;
      const extraBadge = (g.build_number != null && g.status_label && g.status_label !== `Build #${g.build_number}`)
        ? `<span class="badge">${g.status_label}</span>`
        : '';
      const archivedBadgeHtml = g.archived
        ? '<span class="badge b-archived">Archived · Post-2.0</span>'
        : '';
      const localBadgeHtml = isGameLocal
        ? '<span class="badge b-local">Local Only · Hidden on GitHub Pages</span>'
        : (localScreensCount > 0 ? `<span class="badge b-local">${localScreensCount} Local Only</span>` : '');
      head.innerHTML = `
        <div>
          <h2 style="border:none;padding:0;margin:0;">${g.name}</h2>
          <div class="flag-desc" style="margin-top:4px;">${g.summary}</div>
        </div>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
          ${archivedBadgeHtml}
          ${localBadgeHtml}
          ${buildBadge}
          ${extraBadge}
          ${statusSelectHtml}
        </div>
      `;
      card.appendChild(head);

      if (isGameLocal) {
        const banner = document.createElement('div');
        banner.className = 'local-only-banner';
        banner.setAttribute('role', 'note');
        banner.innerHTML = 'Local Only — Not Published on GitHub Pages <span class="local-sub">Omitted from public builds until marked public.</span>';
        card.appendChild(banner);
      }

      for (const scr of screens) {
        const isScreenLocal = !isPublic && !isGameLocal && scr.visibility === 'local';
        const targetParent = isScreenLocal ? document.createElement('div') : card;
        if (isScreenLocal) {
          targetParent.className = 'flag-item is-local-only';
          targetParent.innerHTML = `
            <div class="flag-head">
              <strong style="color:var(--gold);">${scr.title}</strong>
              <span class="badge b-local">Local Only · Hidden on GitHub Pages</span>
            </div>
            <div class="local-only-banner" role="note">Local Only — Not Published on GitHub Pages <span class="local-sub">Visible only in the local dashboard until unveiled.</span></div>
          `;
        } else if (screens.length > 1) {
          const st = document.createElement('div');
          st.className = 'stage-title';
          st.textContent = scr.title;
          targetParent.appendChild(st);
        }
        const pairRow = document.createElement('div');
        pairRow.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;';
        pairRow.appendChild(renderSide(scr.vanilla, false));
        pairRow.appendChild(renderSide(scr.ours, true));
        targetParent.appendChild(pairRow);
        if (isScreenLocal) card.appendChild(targetParent);
      }

      if (!isPublic) {
        const noteWrap = document.createElement('div');
        noteWrap.style.cssText = 'display:flex;flex-direction:column;gap:4px;margin-top:4px;';
        noteWrap.innerHTML = `
          <label style="font-size:0.82rem;color:var(--muted);">Notes for ${g.name}</label>
          <textarea class="title-game-note" data-game="${g.id}" rows="2" placeholder="Optional tweak or sign-off notes..." style="width:100%;font:inherit;color:var(--text);background:var(--panel-alt);border:1px solid var(--border);border-radius:8px;padding:8px 10px;">${ui.gameNotes[g.id] || ''}</textarea>
        `;
        card.appendChild(noteWrap);
      }
      listEl.appendChild(card);
    }

    listEl.querySelectorAll('.title-game-status').forEach(sel => {
      sel.onchange = () => {
        ui.gameStatus[sel.dataset.game] = sel.value;
        persist();
      };
    });
    listEl.querySelectorAll('.title-game-note').forEach(ta => {
      ta.oninput = () => {
        ui.gameNotes[ta.dataset.game] = ta.value;
        persist();
      };
    });
  }

  document.getElementById('titles-zoom')?.addEventListener('change', e => {
    ui.zoom = Number(e.target.value);
    render();
  });
  document.getElementById('titles-copy-md')?.addEventListener('click', () => {
    navigator.clipboard?.writeText(buildMarkdownSummary());
    setToast('Copied Markdown feedback summary to clipboard.');
  });
  document.getElementById('titles-copy-json')?.addEventListener('click', () => {
    navigator.clipboard?.writeText(JSON.stringify({
      gameNotes: ui.gameNotes,
      gameStatus: ui.gameStatus,
    }, null, 2));
    setToast('Copied JSON feedback to clipboard.');
  });

  let rendered = false;
  function ensureRendered() {
    if (rendered) return;
    rendered = true;
    render();
  }
  const viewTitles = document.getElementById('view-titles');
  if (viewTitles && !viewTitles.classList.contains('hidden')) {
    ensureRendered();
  }
  window.addEventListener('barba:tab', e => {
    if (e.detail?.tab === 'titles') ensureRendered();
  });
})();
