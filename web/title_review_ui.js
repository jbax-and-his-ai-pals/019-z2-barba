(() => {
  const data = window.TITLE_REVIEW_DATA;
  if (!data) return;

  const STORAGE_KEY = 'barba_title_review_v1';
  const RANKS = ['', '1st (Top Pick)', '2nd', '3rd', 'Pass'];
  const GAME_STATES = ['needs_work', 'in_review', 'approved'];

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
    subtab: 'main', // 'main' | 'mask'
    filter: 'all',
    zoom: 2,
    animate: true,
    tick: 0,
    ranks: saved.ranks || {},         // candidateId -> rank string
    candNotes: saved.candNotes || {}, // candidateId -> string
    gameNotes: saved.gameNotes || {}, // gameId -> string
    gameStatus: saved.gameStatus || {}, // gameId -> 'needs_work'|'in_review'|'approved'
  };

  function persist() {
    saveState({
      ranks: ui.ranks,
      candNotes: ui.candNotes,
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
    const allItems = [...data.games, ...(data.jason_mask_lab || [])];
    for (const g of allItems) {
      const st = ui.gameStatus[g.id] || 'in_review';
      lines.push(`## ${g.name} [${st}]`);
      if (ui.gameNotes[g.id]) lines.push(`- Notes: ${ui.gameNotes[g.id]}`);
      for (const c of g.candidates) {
        const rk = ui.ranks[c.id] || 'unranked';
        const nt = ui.candNotes[c.id] ? ` — ${ui.candNotes[c.id]}` : '';
        lines.push(`- ${c.label}: **${rk}**${nt}`);
      }
      lines.push('');
    }
    return lines.join('\n');
  }

  function render() {
    const doneEl = document.getElementById('titles-done-strip');
    if (doneEl) {
      doneEl.innerHTML = data.done_games.map(d =>
        `<span class="badge b-toggleable" title="${d.note}">✓ ${d.name}</span>`
      ).join('');
    }

    const listEl = document.getElementById('titles-list');
    if (!listEl) return;
    listEl.innerHTML = '';

    const games = ui.subtab === 'mask'
      ? (data.jason_mask_lab || [])
      : data.games.filter(g => {
          if (ui.filter === 'all') return true;
          if (ui.filter === 'prototype') return g.status === 'prototype' || g.status === 'not_started';
          if (ui.filter === 'rework') return g.status === 'needs_rework' || g.status === 'fixed_needs_title';
          if (ui.filter === 'discuss') return g.status === 'discussion' || g.status === 'align';
          return true;
        });

    const btnMain = document.getElementById('titles-subtab-main');
    const btnMask = document.getElementById('titles-subtab-mask');
    if (btnMain && btnMask) {
      btnMain.classList.toggle('primary', ui.subtab === 'main');
      btnMask.classList.toggle('primary', ui.subtab === 'mask');
    }

    for (const g of games) {
      const card = document.createElement('section');
      card.className = 'card';

      const curStatus = ui.gameStatus[g.id] || 'in_review';
      const head = document.createElement('div');
      head.className = 'flag-head';
      head.innerHTML = `
        <div>
          <h2 style="border:none;padding:0;margin:0;">${g.name}</h2>
          <div class="flag-desc" style="margin-top:4px;">${g.summary}</div>
          <div class="flag-req" style="margin-top:2px;">Context: ${g.context_note}</div>
        </div>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
          <span class="badge b-built">${g.status_label}</span>
          <select class="title-game-status" data-game="${g.id}">
            <option value="needs_work" ${curStatus === 'needs_work' ? 'selected' : ''}>Needs Work</option>
            <option value="in_review" ${curStatus === 'in_review' ? 'selected' : ''}>In Review</option>
            <option value="approved" ${curStatus === 'approved' ? 'selected' : ''}>Sign Off / Approved</option>
          </select>
        </div>
      `;
      card.appendChild(head);

      // Current Screens Row
      const curTitle = document.createElement('div');
      curTitle.className = 'stage-title';
      curTitle.textContent = 'Current ROM State & Context';
      card.appendChild(curTitle);

      const curRow = document.createElement('div');
      curRow.style.cssText = 'display:flex;flex-wrap:wrap;gap:12px;';
      for (const item of g.current) {
        const box = document.createElement('div');
        box.className = 'stage-slot';
        box.style.alignItems = 'flex-start';
        box.innerHTML = `
          <strong>${item.label}</strong>
          <img src="${item.img}" alt="${item.label}" style="width:${256 * ui.zoom}px;max-width:100%;height:auto;image-rendering:pixelated;border-radius:6px;border:1px solid var(--border);">
          <span>${item.caption}</span>
        `;
        curRow.appendChild(box);
      }
      card.appendChild(curRow);

      // Candidates Row
      if (g.candidates.length > 0) {
        const candTitle = document.createElement('div');
        candTitle.className = 'stage-title';
        candTitle.style.marginTop = '6px';
        candTitle.textContent = 'Candidates (Vote / Rank / Note)';
        card.appendChild(candTitle);

        const candRow = document.createElement('div');
        candRow.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px;';
        for (const c of g.candidates) {
          const rankVal = ui.ranks[c.id] || '';
          const isTop = rankVal === '1st (Top Pick)';
          const box = document.createElement('div');
          box.className = 'flag-item' + (isTop ? ' is-selected' : '');
          if (isTop) box.style.borderColor = 'var(--ember)';

          const imgSrc = (ui.animate && c.anim_img && (ui.tick % 2 === 1)) ? c.anim_img : c.img;
          box.innerHTML = `
            <div class="flag-head">
              <strong>${c.label}</strong>
              ${c.anim_img ? '<span class="badge b-coupled">Animated Intro↔Title</span>' : ''}
            </div>
            <img class="title-cand-img" data-main="${c.img}" data-anim="${c.anim_img || ''}" src="${imgSrc}" alt="${c.label}" style="width:${256 * ui.zoom}px;max-width:100%;height:auto;image-rendering:pixelated;border-radius:6px;border:1px solid var(--border);">
            <div class="flag-desc">${c.caption}</div>
            <div class="row" style="gap:6px;">
              ${RANKS.filter(Boolean).map(r => `
                <button type="button" class="title-rank-btn ${rankVal === r ? 'primary' : ''}" data-cand="${c.id}" data-rank="${r}" style="font-size:0.78rem;padding:4px 9px;">${r}</button>
              `).join('')}
            </div>
            <input type="text" class="title-cand-note" data-cand="${c.id}" placeholder="Notes on this candidate..." value="${(ui.candNotes[c.id] || '').replace(/"/g, '&quot;')}" style="width:100%;font-size:0.84rem;">
          `;
          candRow.appendChild(box);
        }
        card.appendChild(candRow);
      }

      // Open Game Notes
      const noteWrap = document.createElement('div');
      noteWrap.style.cssText = 'display:flex;flex-direction:column;gap:4px;margin-top:4px;';
      noteWrap.innerHTML = `
        <label style="font-size:0.82rem;color:var(--muted);">Open Notes / Direction for ${g.name}</label>
        <textarea class="title-game-note" data-game="${g.id}" rows="2" placeholder="Add direction, palette preferences, font tweaks, or sign-off notes..." style="width:100%;font:inherit;color:var(--text);background:var(--panel-alt);border:1px solid var(--border);border-radius:8px;padding:8px 10px;">${ui.gameNotes[g.id] || ''}</textarea>
      `;
      card.appendChild(noteWrap);
      listEl.appendChild(card);
    }

    listEl.querySelectorAll('.title-game-status').forEach(sel => {
      sel.onchange = () => {
        ui.gameStatus[sel.dataset.game] = sel.value;
        persist();
      };
    });
    listEl.querySelectorAll('.title-rank-btn').forEach(btn => {
      btn.onclick = () => {
        const cid = btn.dataset.cand;
        const rk = btn.dataset.rank;
        ui.ranks[cid] = (ui.ranks[cid] === rk) ? '' : rk;
        persist();
        render();
      };
    });
    listEl.querySelectorAll('.title-cand-note').forEach(inp => {
      inp.oninput = () => {
        ui.candNotes[inp.dataset.cand] = inp.value;
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

  document.getElementById('titles-subtab-main')?.addEventListener('click', () => {
    ui.subtab = 'main';
    render();
  });
  document.getElementById('titles-subtab-mask')?.addEventListener('click', () => {
    ui.subtab = 'mask';
    render();
  });
  document.getElementById('titles-filter')?.addEventListener('change', e => {
    ui.filter = e.target.value;
    render();
  });
  document.getElementById('titles-zoom')?.addEventListener('change', e => {
    ui.zoom = Number(e.target.value);
    render();
  });
  document.getElementById('titles-anim')?.addEventListener('change', e => {
    ui.animate = e.target.checked;
    render();
  });
  document.getElementById('titles-copy-md')?.addEventListener('click', () => {
    navigator.clipboard?.writeText(buildMarkdownSummary());
    setToast('Copied Markdown feedback summary to clipboard.');
  });
  document.getElementById('titles-copy-json')?.addEventListener('click', () => {
    navigator.clipboard?.writeText(JSON.stringify({
      ranks: ui.ranks,
      candNotes: ui.candNotes,
      gameNotes: ui.gameNotes,
      gameStatus: ui.gameStatus,
    }, null, 2));
    setToast('Copied JSON feedback to clipboard.');
  });

  setInterval(() => {
    if (!ui.animate) return;
    ui.tick++;
    document.querySelectorAll('.title-cand-img').forEach(img => {
      const anim = img.dataset.anim;
      if (anim) img.src = (ui.tick % 2 === 1) ? anim : img.dataset.main;
    });
  }, 1100);

  render();
})();
