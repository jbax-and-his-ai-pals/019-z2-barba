(() => {
  const data = window.Z2_STRINGS_DATA;
  if (!data) return;

  const STORAGE_KEY = 'barba_z2_strings_review_v1';

  function loadEdits() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      return parsed && typeof parsed.edits === 'object' && parsed.edits ? parsed.edits : {};
    } catch {
      return {};
    }
  }

  function saveEdits(edits) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ edits }));
    } catch {}
  }

  const ui = {
    edits: loadEdits(),
    groupBy: 'area',
    statusFilter: 'all',
    areaFilter: 'all',
    charFilter: 'all',
    search: '',
  };

  function getText(item) {
    return Object.prototype.hasOwnProperty.call(ui.edits, item.id)
      ? ui.edits[item.id]
      : item.text;
  }

  function isModified(item) {
    return Object.prototype.hasOwnProperty.call(ui.edits, item.id) && ui.edits[item.id] !== item.text;
  }

  function analyzeString(item, text) {
    const c = item.constraints;
    const lines = text.split('\n');
    const lineCount = lines.length;
    const maxFoundLen = lines.reduce((m, l) => Math.max(m, l.length), 0);

    let byteCount = 0;
    if (c.wrap_mode === 'newline') {
      byteCount = lines.reduce((s, l) => s + l.length, 0) + lines.length;
    } else if (c.includes_terminator_in_bytes) {
      if (item.id === 'title_story_scroll') {
        byteCount = lines.reduce((s, l) => s + l.length + 1, 0);
      } else {
        byteCount = lines.reduce((s, l) => s + l.length, 0) + 1;
      }
    } else {
      byteCount = lines.reduce((s, l) => s + l.length, 0);
    }

    const errors = [];
    const warnings = [];
    const lineReports = [];

    if (lineCount > c.max_lines) {
      errors.push(`Too many lines: ${lineCount}/${c.max_lines} max`);
    }
    if (c.exact_line_len && item.id === 'title_story_scroll' && lineCount !== c.max_lines) {
      errors.push(`Must have exactly ${c.max_lines} rows (currently ${lineCount})`);
    }
    if (c.exact_line_len && item.id === 'ending_zelda_wakeup' && lineCount !== c.max_lines) {
      errors.push(`Must have exactly ${c.max_lines} rows (currently ${lineCount})`);
    }

    const allowedRe = c.allowed_regex ? new RegExp(c.allowed_regex) : null;
    const invalidChars = [];
    if (allowedRe && !allowedRe.test(text)) {
      const charTestRe = new RegExp(c.allowed_regex.replace(/^\^/, '').replace(/\+\$$/, '').replace(/\[([^\]]+)\]/, '[$1]'));
      for (const ch of text) {
        if (ch === '\n') continue;
        if (!charTestRe.test(ch) && !invalidChars.includes(ch)) {
          invalidChars.push(ch);
        }
      }
      if (invalidChars.length) {
        errors.push(`Unsupported char(s): ${invalidChars.map(ch => JSON.stringify(ch)).join(', ')}`);
      }
    }

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const len = line.length;
      let lineState = 'ok';
      let note = '';

      if (len > c.max_line_len) {
        lineState = 'err';
        note = `over by ${len - c.max_line_len}`;
        errors.push(`Line ${i + 1} exceeds ${c.max_line_len} chars (${len})`);
      } else if (c.exact_line_len && len !== c.max_line_len) {
        lineState = 'err';
        note = `must be ${c.max_line_len}`;
        errors.push(`Line ${i + 1} must be exact ${c.max_line_len} chars (${len})`);
      } else if (c.wrap_mode === 'newline') {
        if (len === 0 || line.trim().length === 0) {
          lineState = 'warn';
          note = 'empty line';
          warnings.push(`Line ${i + 1} is empty`);
        } else if (line !== line.trim()) {
          lineState = 'warn';
          note = 'leading/trailing space';
          warnings.push(`Line ${i + 1} has leading/trailing spaces`);
        }
      }

      if (c.wrap_mode === 'newline' && i < lines.length - 1) {
        const curTrim = line.trimEnd();
        const nextTrim = lines[i + 1].trimStart();
        const firstWord = nextTrim.split(/\s+/)[0] || '';
        if (curTrim.length > 0 && firstWord.length > 0) {
          const combined = curTrim.length + 1 + firstWord.length;
          if (combined <= c.max_line_len) {
            if (lineState === 'ok') lineState = 'warn';
            note = note ? `${note}; '${firstWord}' fits (${combined}/${c.max_line_len})` : `'${firstWord}' fits here (${combined}/${c.max_line_len})`;
            warnings.push(`Line ${i + 1}: "${firstWord}" could fit (${combined}/${c.max_line_len})`);
          }
        }
      }

      lineReports.push({
        index: i + 1,
        len,
        max: c.max_line_len,
        state: lineState,
        note,
      });
    }

    if (c.max_bytes != null && byteCount > c.max_bytes) {
      errors.push(`Byte budget exceeded: ${byteCount}/${c.max_bytes} B`);
    }

    const status = errors.length ? 'error' : (warnings.length ? 'warn' : 'ok');
    return {
      status,
      errors,
      warnings,
      lines,
      lineCount,
      maxFoundLen,
      byteCount,
      lineReports,
    };
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function setToast(msg) {
    const el = document.getElementById('z2str-toast');
    if (el) el.textContent = msg;
  }

  function populateDropdowns() {
    const areaSel = document.getElementById('z2str-area');
    const charSel = document.getElementById('z2str-char');
    if (areaSel && areaSel.options.length <= 1) {
      for (const a of data.areas) {
        const opt = document.createElement('option');
        opt.value = a;
        opt.textContent = a;
        areaSel.appendChild(opt);
      }
    }
    if (charSel && charSel.options.length <= 1) {
      for (const ch of data.characters) {
        const opt = document.createElement('option');
        opt.value = ch;
        opt.textContent = ch;
        charSel.appendChild(opt);
      }
    }
  }

  function updateSummaryStats(analyzed) {
    const statsEl = document.getElementById('z2str-stats');
    if (!statsEl) return;
    let okCount = 0;
    let warnCount = 0;
    let errCount = 0;
    let modCount = 0;
    for (const entry of analyzed) {
      if (entry.report.status === 'ok') okCount++;
      else if (entry.report.status === 'warn') warnCount++;
      else errCount++;
      if (entry.modified) modCount++;
    }
    statsEl.innerHTML =
      `<span>Total Z2 Strings: <strong>${analyzed.length}</strong></span>` +
      `<span>Fits Cleanly: <strong style="color:var(--green);">${okCount}</strong></span>` +
      `<span>Split / Fit Notes: <strong style="color:var(--amber);">${warnCount}</strong></span>` +
      `<span>Overflow / Invalid: <strong style="color:var(--ember);">${errCount}</strong></span>` +
      `<span>Edited Locally: <strong style="color:var(--cyan);">${modCount}</strong></span>`;
  }

  function buildCard(entry) {
    const { item, text, report, modified } = entry;
    const c = item.constraints;
    const card = document.createElement('div');
    card.className = `z2str-card st-${report.status}` + (modified ? ' is-modified' : '');
    card.dataset.id = item.id;

    const statusLabel =
      report.status === 'error' ? 'OVERFLOW / INVALID'
        : (report.status === 'warn' ? 'SPLIT / FIT NOTE' : 'FITS CLEANLY');
    const statusCls =
      report.status === 'error' ? 'b-err'
        : (report.status === 'warn' ? 'b-warn' : 'b-ok');

    const byteStr = c.max_bytes != null
      ? `${report.byteCount} / ${c.max_bytes} B`
      : `${report.byteCount} B`;

    const rulerWidth = Math.max(c.max_line_len, report.maxFoundLen);
    const ruler = Array.from({ length: rulerWidth }, (_, i) => ((i + 1) % 10)).join('');

    const rows = Math.max(1, Math.min(14, Math.max(c.max_lines, report.lineCount)));

    card.innerHTML = `
      <div class="z2str-card-head">
        <div>
          <div class="z2str-title">${escapeHtml(item.label)}</div>
          <div class="z2str-meta-row">
            <span class="badge">${escapeHtml(item.area)}</span>
            <span class="badge">${escapeHtml(item.character)}</span>
            <span class="z2str-loc">${escapeHtml(item.source_file)} · ${escapeHtml(item.location)}</span>
          </div>
        </div>
        <div class="z2str-head-right">
          ${modified ? '<span class="badge b-built">Modified</span>' : ''}
          <span class="badge ${statusCls}" data-role="status-badge">${statusLabel}</span>
          ${modified ? `<button type="button" class="feud-mini-btn" data-action="reset">Reset</button>` : ''}
        </div>
      </div>
      <div class="z2str-editor-wrap">
        <div class="z2str-ruler" aria-hidden="true">${escapeHtml(ruler)}</div>
        <textarea class="z2str-textarea" rows="${rows}" spellcheck="false" style="--max-cols:${c.max_line_len};">${escapeHtml(text)}</textarea>
      </div>
      <div class="z2str-metrics" data-role="metrics">
        <span>Max Line: <strong>${report.maxFoundLen} / ${c.max_line_len}${c.exact_line_len ? ' (exact)' : ''}</strong></span>
        <span>Lines: <strong>${report.lineCount} / ${c.max_lines}</strong></span>
        <span>Bytes: <strong>${byteStr}</strong></span>
        <span>Allowed: <code>${escapeHtml(c.allowed_chars)}</code></span>
      </div>
      <div class="z2str-lines" data-role="lines"></div>
      <div class="z2str-issues" data-role="issues"></div>
      ${item.vanilla_text != null ? `<details class="z2str-vanilla"><summary>Vanilla Reference</summary><pre>${escapeHtml(item.vanilla_text)}</pre></details>` : ''}
      ${item.notes ? `<div class="z2str-notes">${escapeHtml(item.notes)}</div>` : ''}
    `;

    renderCardReport(card, item, report, modified);

    const ta = card.querySelector('.z2str-textarea');
    ta.addEventListener('input', () => {
      const val = ta.value;
      if (val === item.text) delete ui.edits[item.id];
      else ui.edits[item.id] = val;
      saveEdits(ui.edits);
      const nextReport = analyzeString(item, val);
      const nextMod = isModified(item);
      card.className = `z2str-card st-${nextReport.status}` + (nextMod ? ' is-modified' : '');
      renderCardReport(card, item, nextReport, nextMod);
      refreshSummaryOnly();
    });

    card.querySelector('[data-action="reset"]')?.addEventListener('click', () => {
      delete ui.edits[item.id];
      saveEdits(ui.edits);
      render();
      setToast(`Reset "${item.label}" to source.`);
    });

    return card;
  }

  function renderCardReport(card, item, report, modified) {
    const c = item.constraints;
    const badge = card.querySelector('[data-role="status-badge"]');
    if (badge) {
      badge.textContent =
        report.status === 'error' ? 'OVERFLOW / INVALID'
          : (report.status === 'warn' ? 'SPLIT / FIT NOTE' : 'FITS CLEANLY');
      badge.className = 'badge ' + (
        report.status === 'error' ? 'b-err'
          : (report.status === 'warn' ? 'b-warn' : 'b-ok')
      );
    }

    const metricsEl = card.querySelector('[data-role="metrics"]');
    if (metricsEl) {
      const byteStr = c.max_bytes != null
        ? `${report.byteCount} / ${c.max_bytes} B`
        : `${report.byteCount} B`;
      metricsEl.innerHTML =
        `<span>Max Line: <strong>${report.maxFoundLen} / ${c.max_line_len}${c.exact_line_len ? ' (exact)' : ''}</strong></span>` +
        `<span>Lines: <strong>${report.lineCount} / ${c.max_lines}</strong></span>` +
        `<span>Bytes: <strong>${byteStr}</strong></span>` +
        `<span>Allowed: <code>${escapeHtml(c.allowed_chars)}</code></span>`;
    }

    const linesEl = card.querySelector('[data-role="lines"]');
    if (linesEl) {
      linesEl.innerHTML = report.lineReports.map(lr => {
        const cls = lr.state === 'err' ? 'is-err' : (lr.state === 'warn' ? 'is-warn' : 'is-ok');
        const note = lr.note ? ` · ${escapeHtml(lr.note)}` : '';
        return `<span class="z2str-line-pill ${cls}">L${lr.index}: ${lr.len}/${lr.max}${note}</span>`;
      }).join('');
    }

    const issuesEl = card.querySelector('[data-role="issues"]');
    if (issuesEl) {
      const allMsgs = [
        ...report.errors.map(m => `<div class="z2str-issue err">Error: ${escapeHtml(m)}</div>`),
        ...report.warnings.map(m => `<div class="z2str-issue warn">Note: ${escapeHtml(m)}</div>`),
      ];
      issuesEl.innerHTML = allMsgs.join('');
    }

    const headRight = card.querySelector('.z2str-head-right');
    if (headRight) {
      let modBadge = headRight.querySelector('.b-built');
      let resetBtn = headRight.querySelector('[data-action="reset"]');
      if (modified && !modBadge) {
        modBadge = document.createElement('span');
        modBadge.className = 'badge b-built';
        modBadge.textContent = 'Modified';
        headRight.prepend(modBadge);
      } else if (!modified && modBadge) {
        modBadge.remove();
      }
      if (modified && !resetBtn) {
        resetBtn = document.createElement('button');
        resetBtn.type = 'button';
        resetBtn.className = 'feud-mini-btn';
        resetBtn.dataset.action = 'reset';
        resetBtn.textContent = 'Reset';
        resetBtn.onclick = () => {
          delete ui.edits[item.id];
          saveEdits(ui.edits);
          render();
          setToast(`Reset "${item.label}" to source.`);
        };
        headRight.appendChild(resetBtn);
      } else if (!modified && resetBtn) {
        resetBtn.remove();
      }
    }
  }

  function getAnalyzedAll() {
    return data.strings.map(item => {
      const text = getText(item);
      return {
        item,
        text,
        modified: isModified(item),
        report: analyzeString(item, text),
      };
    });
  }

  function refreshSummaryOnly() {
    updateSummaryStats(getAnalyzedAll());
  }

  function render() {
    populateDropdowns();
    const analyzed = getAnalyzedAll();
    updateSummaryStats(analyzed);

    const q = ui.search.trim().toLowerCase();
    const filtered = analyzed.filter(entry => {
      const { item, text, report, modified } = entry;
      if (ui.areaFilter !== 'all' && item.area !== ui.areaFilter) return false;
      if (ui.charFilter !== 'all' && item.character !== ui.charFilter) return false;
      if (ui.statusFilter === 'error' && report.status !== 'error') return false;
      if (ui.statusFilter === 'warn' && report.status !== 'warn') return false;
      if (ui.statusFilter === 'issues' && report.status === 'ok') return false;
      if (ui.statusFilter === 'modified' && !modified) return false;
      if (q) {
        const hay = `${item.id} ${item.label} ${item.area} ${item.character} ${item.location} ${item.source_file} ${text}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });

    const container = document.getElementById('z2str-groups');
    if (!container) return;
    container.innerHTML = '';

    if (!filtered.length) {
      container.innerHTML = '<div class="card"><div class="subtitle">No strings match the current filters.</div></div>';
      return;
    }

    const groups = new Map();
    for (const entry of filtered) {
      const key = ui.groupBy === 'none'
        ? 'All Zelda II Strings'
        : (entry.item[ui.groupBy] || 'Other');
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(entry);
    }

    for (const [groupName, items] of groups.entries()) {
      const sec = document.createElement('section');
      sec.className = 'card';
      const errC = items.filter(e => e.report.status === 'error').length;
      const warnC = items.filter(e => e.report.status === 'warn').length;
      const badgeSummary =
        (errC ? `<span class="badge b-err">${errC} error</span>` : '') +
        (warnC ? `<span class="badge b-warn">${warnC} note</span>` : '') +
        `<span class="badge">${items.length} strings</span>`;

      sec.innerHTML = `
        <div class="flag-head" style="border-bottom:1px solid var(--border);padding-bottom:8px;">
          <h2 style="border:none;padding:0;margin:0;">${escapeHtml(groupName)}</h2>
          <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">${badgeSummary}</div>
        </div>
        <div class="z2str-grid"></div>
      `;
      const grid = sec.querySelector('.z2str-grid');
      for (const entry of items) {
        grid.appendChild(buildCard(entry));
      }
      container.appendChild(sec);
    }
  }

  function buildMarkdownReport() {
    const analyzed = getAnalyzedAll();
    const lines = ['# Zelda II String Review Report', ''];
    for (const entry of analyzed) {
      const { item, text, report, modified } = entry;
      if (!modified && report.status === 'ok') continue;
      lines.push(`## ${item.label} (${item.area} / ${item.character}) [${report.status.toUpperCase()}${modified ? ', MODIFIED' : ''}]`);
      lines.push(`- Source: \`${item.source_file}\` (${item.location})`);
      lines.push(`- Dimensions: ${report.lineCount}/${item.constraints.max_lines} lines, max line ${report.maxFoundLen}/${item.constraints.max_line_len}, ${report.byteCount}${item.constraints.max_bytes != null ? '/' + item.constraints.max_bytes : ''} bytes`);
      if (report.errors.length) lines.push(`- Errors: ${report.errors.join('; ')}`);
      if (report.warnings.length) lines.push(`- Notes: ${report.warnings.join('; ')}`);
      lines.push('```');
      lines.push(text);
      lines.push('```');
      lines.push('');
    }
    if (lines.length === 2) {
      lines.push('All Zelda II strings fit cleanly with zero edits or warnings.');
    }
    return lines.join('\n');
  }

  function buildJsonExport() {
    const analyzed = getAnalyzedAll();
    return JSON.stringify(
      analyzed.map(({ item, text, modified, report }) => ({
        id: item.id,
        label: item.label,
        area: item.area,
        character: item.character,
        source_file: item.source_file,
        location: item.location,
        text,
        modified,
        status: report.status,
        max_line_len: report.maxFoundLen,
        max_line_limit: item.constraints.max_line_len,
        lines: report.lineCount,
        max_lines: item.constraints.max_lines,
        bytes: report.byteCount,
        max_bytes: item.constraints.max_bytes,
        errors: report.errors,
        warnings: report.warnings,
      })),
      null,
      2
    );
  }

  document.getElementById('z2str-groupby')?.addEventListener('change', e => {
    ui.groupBy = e.target.value;
    render();
  });
  document.getElementById('z2str-status')?.addEventListener('change', e => {
    ui.statusFilter = e.target.value;
    render();
  });
  document.getElementById('z2str-area')?.addEventListener('change', e => {
    ui.areaFilter = e.target.value;
    render();
  });
  document.getElementById('z2str-char')?.addEventListener('change', e => {
    ui.charFilter = e.target.value;
    render();
  });
  document.getElementById('z2str-search')?.addEventListener('input', e => {
    ui.search = e.target.value;
    render();
  });
  document.getElementById('z2str-reset-all')?.addEventListener('click', () => {
    ui.edits = {};
    saveEdits(ui.edits);
    render();
    setToast('Reset all Z2 strings to repo source.');
  });
  document.getElementById('z2str-copy-md')?.addEventListener('click', () => {
    navigator.clipboard?.writeText(buildMarkdownReport());
    setToast('Copied Markdown string review report to clipboard.');
  });
  document.getElementById('z2str-copy-json')?.addEventListener('click', () => {
    navigator.clipboard?.writeText(buildJsonExport());
    setToast('Copied Z2 strings JSON to clipboard.');
  });

  let rendered = false;
  function ensureRendered() {
    if (rendered) return;
    rendered = true;
    render();
  }
  const view = document.getElementById('view-z2strings');
  if (view && !view.classList.contains('hidden')) {
    ensureRendered();
  }
  window.addEventListener('barba:tab', e => {
    if (e.detail && e.detail.tab === 'z2strings') {
      ensureRendered();
    }
  });
})();
