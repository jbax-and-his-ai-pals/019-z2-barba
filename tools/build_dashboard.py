"""Standardized builder for both Barba Enterprise dashboard flavors.

Generates:
  - public (`web/index.html`): GitHub Pages presentation build (Flags & Showcase,
    Title Screens showcase, and 10 visual-only Vanilla vs. Modded subgame tabs).
  - local  (`web/local.html` + `web/local_state.js`, gitignored): Internal dev
    dashboard with Build State bar, CLI Build command, Title Screen Review
    (status/notes/export), 10 subgame showcase tabs, Where's Barba? Tile Tagger,
    Family Feud Cast, and Barba's Hunt Tiles / CHR Inspector.
"""
from __future__ import annotations

import argparse
import functools
import html
import http.server
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import capture_subgame_previews  # noqa: E402
import fe_catalog  # noqa: E402
import ow_tiles_dashboard  # noqa: E402
import title_dashboard  # noqa: E402
import z2_strings_dashboard  # noqa: E402

ROOT = _TOOLS_DIR.parent
TEMPLATE_PATH = _TOOLS_DIR / "dashboard_template.html"
WEB_DIR = ROOT / "web"

SUBGAME_TABS: list[tuple[str, str]] = [
    (g["id"], g["tab_label"]) for g in capture_subgame_previews.SUBGAMES
]


def subgame_tabs_for_flavor(
    flavor: str, games: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """Return subgame tab metadata visible for `flavor` ('public' or 'local')."""
    if flavor not in ("public", "local"):
        raise ValueError(f"Unknown flavor: {flavor}")
    include_local = flavor == "local"
    payload = capture_subgame_previews.build_subgames_payload(
        include_local=include_local, games=games
    )
    return payload["games"]


def _subgame_tab_bucket(g: dict[str, Any]) -> int:
    """Order bucket: 0=published & not archived, 1=local only, 2=local & archived."""
    if g.get("archived"):
        return 2
    if g.get("visibility") == "local":
        return 1
    return 0


def _render_subgame_tab_button(g: dict[str, Any], include_local: bool) -> str:
    gid = g["id"]
    label = html.escape(g["tab_label"])
    is_game_local = include_local and g.get("visibility") == "local"
    is_archived = include_local and bool(g.get("archived"))
    cls = "tab-btn is-local-only" if is_game_local else "tab-btn"
    title_attr = ' title="Local only — not published on GitHub Pages"' if is_game_local else ""
    pill = '<span class="tab-local-pill">Local</span>' if is_game_local else ""
    archived_pill = '<span class="tab-archived-pill">Archived</span>' if is_archived else ""
    return (
        f'      <button type="button" class="{cls}" data-tab="sub-{gid}"{title_attr}>'
        f"{label}{pill}{archived_pill}</button>"
    )


def render_subgame_tabs_html(flavor: str, games: list[dict[str, Any]] | None = None) -> str:
    include_local = flavor == "local"
    ordered_games = sorted(
        subgame_tabs_for_flavor(flavor, games=games),
        key=_subgame_tab_bucket,
    )
    return "\n".join(_render_subgame_tab_button(g, include_local) for g in ordered_games)


def render_workspace_tabs_html(flavor: str, games: list[dict[str, Any]] | None = None) -> str:
    include_local = flavor == "local"
    subgames = subgame_tabs_for_flavor(flavor, games=games)
    if not include_local:
        return "\n".join(_render_subgame_tab_button(g, False) for g in subgames)

    pub_tabs = [
        _render_subgame_tab_button(g, True)
        for g in subgames
        if _subgame_tab_bucket(g) == 0
    ]
    local_active_tabs = [
        _render_subgame_tab_button(g, True)
        for g in subgames
        if _subgame_tab_bucket(g) == 1
    ]
    local_archived_tabs = [
        _render_subgame_tab_button(g, True)
        for g in subgames
        if _subgame_tab_bucket(g) == 2
    ]
    parts = [*pub_tabs, *local_active_tabs, DEV_TABS_HTML, *local_archived_tabs]
    return "\n".join(p for p in parts if p)


def render_subgame_views_html(flavor: str, games: list[dict[str, Any]] | None = None) -> str:
    views = [
        f'    <div id="view-sub-{g["id"]}" class="hidden"></div>'
        for g in subgame_tabs_for_flavor(flavor, games=games)
    ]
    return "\n".join(views)

DEV_TABS_HTML = """\
      <button type="button" class="tab-btn is-local-only" data-tab="z2strings" title="Local only — not published on GitHub Pages">Z2 String Review<span class="tab-local-pill">Local</span></button>
      <button type="button" class="tab-btn is-local-only" data-tab="owtiles" title="Local only — not published on GitHub Pages">Overworld Tiles Lab<span class="tab-local-pill">Local</span></button>
      <button type="button" class="tab-btn" data-tab="waldo">Where's Barba? Tile Tagger</button>
      <button type="button" class="tab-btn" data-tab="feud">Family Feud Cast</button>
      <button type="button" class="tab-btn" data-tab="duck">Barba's Hunt Tiles</button>"""

PRESET_BAR_HTML = '<div class="preset-bar" id="presets"></div>'

CLI_ROW_HTML = """\
      <div class="row">
        <label for="cli-cmd">CLI Build</label>
        <input id="cli-cmd" class="mono" readonly>
        <button id="copy-cli" type="button">Copy CLI</button>
      </div>"""

SEED_FLAGSTRING_BOX_HTML = f"""\
    <section class="top-box" aria-label="Seed and Flagstring">
      <div class="row">
        <label for="seed-input">Seed</label>
        <input id="seed-input" class="mono" value="BARBA2026" style="max-width: 220px;">
        <button id="roll-seed" type="button">Roll Seed</button>
        <div class="filter-bar" style="margin-left: auto;">
          <span style="font-size:0.84rem;color:var(--muted)">Show:</span>
          <button type="button" class="filter-btn active" data-filter="all">All</button>
          <button type="button" class="filter-btn" data-filter="ready">Built &amp; Toggleable</button>
          <button type="button" class="filter-btn" data-filter="planned">Unbuilt / Planned</button>
        </div>
      </div>
      <div class="row">
        <label for="flagstring">Flagstring</label>
        <input id="flagstring" class="mono" spellcheck="false">
        <button id="apply-flagstring" type="button">Apply</button>
        <button id="copy-flagstring" class="primary" type="button">Copy Flags</button>
      </div>
{CLI_ROW_HTML}
      <div class="stats" id="stats"></div>
      <div class="toast" id="toast" role="status" aria-live="polite"></div>
    </section>"""

TITLES_EXPORT_HTML = """\
          <div style="margin-left:auto;display:flex;gap:8px;flex-wrap:wrap;">
            <button id="titles-copy-md" class="primary" type="button">Copy Feedback (Markdown)</button>
            <button id="titles-copy-json" type="button">Copy Feedback (JSON)</button>
          </div>"""

LOCAL_STATE_BAR_HTML = """\
    <section class="top-box local-state-bar" id="local-build-bar" aria-label="Current Local Build State" style="padding:10px 14px;margin-bottom:14px;gap:6px;">
      <div class="row" style="justify-content:space-between;">
        <div class="stats" id="local-build-stats">Loading local build state...</div>
        <a href="index.html" style="font-size:0.82rem;color:var(--cyan);text-decoration:none;">Open Public Presentation View &rarr;</a>
      </div>
    </section>"""

LOCAL_SCRIPTS_HTML = """\
  <script src="local_state.js"></script>
  <script src="local_z2_strings_data.js"></script>
  <script src="z2_strings_ui.js"></script>
  <script src="local_ow_tiles_data.js"></script>
  <script src="ow_tiles_ui.js"></script>
  <script src="waldo_tagger.js"></script>
  <script src="feud_cast_data.js"></script>
  <script src="feud_cast_ui.js"></script>
  <script src="duck_tiles_data.js"></script>
  <script src="duck_tiles_ui.js"></script>"""

LOCAL_STATE_RENDER_JS = """\
    // Internal Local Build State Bar
    (() => {
      const st = window.BARBA_LOCAL_STATE;
      const el = document.getElementById('local-build-stats');
      if (!st || !el) return;
      const bnum = st.build_number != null ? `#${st.build_number}` : 'n/a';
      const sha = st.sha256 ? st.sha256.slice(0, 12) : 'n/a';
      const ts = st.built_at || 'unknown';
      const wired = Array.isArray(st.wired_flags) ? st.wired_flags.join(', ') : '';
      const lo = st.local_only;
      let localHtml = '';
      if (lo && lo.total > 0) {
        const items = [...(lo.games || []), ...(lo.scenes || []), ...(lo.flags || []), ...(lo.titles || [])];
        const tip = items.join(', ').replace(/"/g, '&quot;');
        localHtml = `<span>Hidden from GitHub Pages: <span class="badge b-local" title="${tip}">${lo.total} local-only (${items.join(', ')})</span></span>`;
      }
      el.innerHTML =
        `<span>Latest Build: <strong>${bnum}</strong></span>` +
        `<span>SHA-256: <code>${sha}</code></span>` +
        `<span>Built: <strong>${ts}</strong></span>` +
        (wired ? `<span>Wired CLI Toggles: <strong>${wired}</strong></span>` : '') +
        localHtml;
    })();"""


def collect_local_only_inventory(
    subgames_payload: dict[str, Any] | None = None,
    catalog_payload_all: dict[str, Any] | None = None,
    titles_payload_all: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize all items marked visibility='local' across dashboard surfaces."""
    sub_data = (
        capture_subgame_previews.build_subgames_payload(include_local=True)
        if subgames_payload is None
        else subgames_payload
    )
    fe_data = (
        fe_catalog.catalog_payload(include_local=True)
        if catalog_payload_all is None
        else catalog_payload_all
    )
    title_data = (
        title_dashboard.title_catalog_payload(include_local=True)
        if titles_payload_all is None
        else titles_payload_all
    )

    games: list[str] = []
    scenes: list[str] = []
    for g in sub_data.get("games", []):
        if g.get("visibility") == "local":
            games.append(g["id"])
        else:
            for sc in g.get("scenes", []):
                if sc.get("visibility") == "local":
                    scenes.append(f"{g['id']}/{sc['id']}")

    flags = [f["id"] for f in fe_data.get("flags", []) if f.get("visibility") == "local"]

    titles: list[str] = []
    for g in title_data.get("games", []):
        if g.get("visibility") == "local":
            titles.append(f"title:{g['id']}")
        else:
            for scr in g.get("screens", []):
                if scr.get("visibility") == "local":
                    titles.append(f"title:{g['id']}/{scr['id']}")

    total = len(games) + len(scenes) + len(flags) + len(titles)
    return {
        "games": games,
        "scenes": scenes,
        "flags": flags,
        "titles": titles,
        "total": total,
    }


def collect_local_state() -> dict[str, Any]:
    """Read current build-report.json and .build-history.sqlite3 if available."""
    state: dict[str, Any] = {
        "build_number": None,
        "sha256": None,
        "built_at": None,
        "wired_flags": list(fe_catalog.WIRED_FLAG_IDS),
        "flag_count": len(fe_catalog.FLAGS),
        "local_only": collect_local_only_inventory(),
    }
    report_path = ROOT / "build" / "build-report.json"
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            state["build_number"] = report.get("build_number", state["build_number"])
            state["sha256"] = report.get("sha256") or report.get("rom_sha256")
            state["built_at"] = report.get("built_at") or report.get("timestamp")
        except (OSError, json.JSONDecodeError):
            pass

    history_db = ROOT / ".build-history.sqlite3"
    if history_db.exists():
        try:
            conn = sqlite3.connect(history_db)
            row = conn.execute(
                "SELECT build_number, sha256, built_at FROM builds ORDER BY build_number DESC LIMIT 1"
            ).fetchone()
            conn.close()
            if row:
                if state["build_number"] is None:
                    state["build_number"] = row[0]
                if not state["sha256"]:
                    state["sha256"] = row[1]
                if not state["built_at"]:
                    state["built_at"] = row[2]
        except sqlite3.Error:
            pass
    return state


def write_web_catalog(
    out_dir: Path | None = None, flavor: str = "all"
) -> list[Path]:
    target_dir = WEB_DIR if out_dir is None else out_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    if flavor in ("public", "all"):
        pub_payload = json.dumps(fe_catalog.catalog_payload(include_local=False), indent=2)
        pub_json = target_dir / "catalog.json"
        pub_js = target_dir / "catalog.js"
        pub_json.write_text(pub_payload + "\n", encoding="utf-8")
        pub_js.write_text(f"window.BARBA_FE_CATALOG = {pub_payload};\n", encoding="utf-8")
        written.extend([pub_json, pub_js])
    if flavor in ("local", "all"):
        loc_payload = json.dumps(fe_catalog.catalog_payload(include_local=True), indent=2)
        loc_js = target_dir / "local_catalog.js"
        loc_js.write_text(f"window.BARBA_FE_CATALOG = {loc_payload};\n", encoding="utf-8")
        written.append(loc_js)
    return written


RELEASE_MANIFEST_PATH = _TOOLS_DIR / "release_manifest.json"
DEFAULT_RELEASE_REPO = "jbax-and-his-ai-pals/019-z2-barba"


def load_release_manifest(path: Path = RELEASE_MANIFEST_PATH) -> dict[str, Any]:
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {
        "repo": DEFAULT_RELEASE_REPO,
        "tag": "",
        "published": False,
        "collections": [],
        "patches": [],
    }


def _fmt_bytes(size: int | None) -> str:
    if not size:
        return ""
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    return f"{max(1, round(size / 1024))} KB"


def _release_asset_url(repo: str, tag: str, filename: str) -> str:
    return f"https://github.com/{repo}/releases/download/{tag}/{filename}"


def render_release_sections(
    manifest: dict[str, Any], is_local: bool
) -> tuple[str, str, str]:
    """Return (notice_html, downloads_html, local_note_html) for the Overview tab."""
    repo = str(manifest.get("repo") or DEFAULT_RELEASE_REPO)
    tag = str(manifest.get("tag") or "")
    published = bool(manifest.get("published")) and bool(tag)
    collections = manifest.get("collections") or []
    patches = manifest.get("patches") or []

    if published:
        bnum = manifest.get("build_number")
        btxt = f" (Build #{bnum})" if bnum is not None else ""
        notice_html = (
            '<div class="overview-notice" style="background:rgba(46, 204, 113, 0.10);'
            'border-color:rgba(46, 204, 113, 0.42);">'
            f'<strong style="color:#6ee7b7;">Current Release: <code>{html.escape(tag)}</code>{html.escape(btxt)}</strong> '
            "&mdash; Download individual <code>.bps</code> patches or a collection <code>.zip</code> below, "
            "and apply to a clean headered USA ROM using a BPS patcher (e.g. Flips or RomPatcher.js).</div>"
        )
    else:
        staged_hint = (
            f" Staged target tag: <code>{html.escape(tag)}</code>."
            if tag
            else ""
        )
        notice_html = (
            '<div class="overview-notice">'
            "<strong>Latest Barba 2.0 release not yet built/uploaded:</strong> "
            "The <code>v1.05</code> GitHub Release is the earlier MMC1-only build. The current Barba 2.0 development build "
            "(NES 2.0 Mapper 176 combined ROM + 5 active subgames) hasn&apos;t been packaged into a GitHub Release yet &mdash; "
            f"upload the staged files below to GitHub Releases or build locally from source.{staged_hint}"
            "</div>"
        )

    parts: list[str] = []
    if collections:
        parts.append('<div class="release-subhead">Collection Zips</div>')
        parts.append('<div class="release-zips-grid">')
        for col in collections:
            fname = str(col.get("filename") or "")
            title = html.escape(str(col.get("title") or fname))
            desc = html.escape(str(col.get("description") or ""))
            fcount = col.get("file_count")
            size_txt = _fmt_bytes(col.get("size_bytes"))
            meta_bits = [f"<code>{html.escape(fname)}</code>"]
            if fcount:
                meta_bits.append(f"{int(fcount)} patches")
            if size_txt:
                meta_bits.append(size_txt)
            if published and fname:
                url = html.escape(_release_asset_url(repo, tag, fname))
                btn = f'<a class="btn-link primary" href="{url}" style="align-self:flex-start;">Download .zip &darr;</a>'
            else:
                btn = '<span class="btn-link is-pending" aria-disabled="true" title="Upload release assets to enable direct download" style="align-self:flex-start;">Pending Upload</span>'
            parts.append(
                '<div class="release-zip-card">'
                f"<div><h3>{title}</h3><p>{desc}</p></div>"
                f'<div class="release-meta">{" &middot; ".join(meta_bits)}</div>'
                f"{btn}"
                "</div>"
            )
        parts.append("</div>")

    if patches:
        tier_labels = [
            ("main", "Mainline Combined ROM (.bps)"),
            ("subgames", "Standalone Subgames &mdash; Flagship (.bps)"),
            ("compat", "Standalone Subgames &mdash; MMC3 Compat (.bps)"),
        ]
        parts.append('<div class="release-subhead">Individual ROM Patches (.bps)</div>')
        parts.append('<div class="release-bps-groups">')
        for tier_key, tier_title in tier_labels:
            group = [p for p in patches if p.get("tier") == tier_key]
            if not group:
                continue
            parts.append(f'<div><div class="release-bps-group-title">{tier_title}</div>')
            parts.append('<div class="release-bps-list">')
            for p in group:
                fname = str(p.get("filename") or "")
                title = html.escape(str(p.get("title") or fname))
                mapper = html.escape(str(p.get("mapper") or ""))
                base_rom = html.escape(str(p.get("base_rom") or ""))
                size_txt = _fmt_bytes(p.get("size_bytes"))
                sub_parts = [f"<code>{html.escape(fname)}</code>"]
                if size_txt:
                    sub_parts.append(size_txt)
                if mapper:
                    sub_parts.append(mapper)
                base_line = f"<span>Base: {base_rom}</span>" if base_rom else ""
                if published and fname:
                    url = html.escape(_release_asset_url(repo, tag, fname))
                    btn = f'<a class="btn-link" href="{url}" style="white-space:nowrap;">.bps &darr;</a>'
                else:
                    btn = '<span class="btn-link is-pending" aria-disabled="true" title="Upload release assets to enable direct download" style="white-space:nowrap;">Pending</span>'
                parts.append(
                    '<div class="release-bps-row">'
                    '<div class="release-bps-info">'
                    f"<strong>{title}</strong>"
                    f'<span>{" &middot; ".join(sub_parts)}</span>'
                    f"{base_line}"
                    "</div>"
                    f"{btn}"
                    "</div>"
                )
            parts.append("</div></div>")
        parts.append("</div>")

    downloads_html = "\n".join(parts)

    if is_local:
        tag_hint = html.escape(tag or "v2.0.0")
        local_note_html = (
            '<div class="local-only-banner" id="overview-local-release" style="flex-direction:column;align-items:flex-start;gap:4px;">'
            '<span><strong>Local Release Packaging:</strong> <span class="local-sub">'
            '1) Stage individual <code>.bps</code> + collection <code>.zip</code>s: '
            f'<code>python tools/package_bps.py --build-number &lt;N&gt; --version {tag_hint} --stage-release --write-manifest</code>'
            '</span></span>'
            '<span class="local-sub">'
            f'2) Upload all files in <code>dist/release-{tag_hint}/</code> to GitHub Release <code>{tag_hint}</code> '
            f'(e.g. <code>gh release create {tag_hint} dist/release-{tag_hint}/* --title "Barba Edition {tag_hint}"</code>), '
            'then run <code>python tools/package_bps.py --publish</code> &amp; <code>python tools/build_dashboard.py</code>.'
            '</span></div>'
        )
    else:
        local_note_html = ""

    return notice_html, downloads_html, local_note_html


def render_flavor(
    template: str,
    flavor: str,
    subgames: list[dict[str, Any]] | None = None,
    release_manifest: dict[str, Any] | None = None,
) -> str:
    if flavor not in ("public", "local"):
        raise ValueError(f"Unknown flavor: {flavor}")
    is_local = flavor == "local"
    manifest = load_release_manifest() if release_manifest is None else release_manifest
    release_notice, release_downloads, overview_local_note = render_release_sections(
        manifest, is_local
    )

    replacements = {
        "{{FLAVOR}}": flavor,
        "{{PAGE_TITLE}}": (
            "Zelda II: Barba Enterprise (Internal Dev) — Flags, Graphics & State"
            if is_local
            else "Zelda II: Barba Edition — Feature & Graphics Showcase"
        ),
        "{{HEADER_TITLE}}": (
            "Zelda II: <span>Barba Enterprise</span>"
            if is_local
            else "Zelda II: <span>Barba Edition</span>"
        ),
        "{{HEADER_BADGE}}": (
            ' <span class="badge b-coupled" style="vertical-align:middle;margin-left:8px;">Internal Dev</span>'
            if is_local
            else ""
        ),
        "{{HEADER_SUBTITLE}}": (
            "Internal dev workspace — flag/seed builder, build state, title review, and graphics/tile iteration"
            if is_local
            else "Visual showcase of graphics, gameplay features, audio, title screens, and subgame changes — Vanilla Z2 vs. Barba Edition"
        ),
        "{{LOCAL_STATE_BAR}}": LOCAL_STATE_BAR_HTML if is_local else "",
        "{{RELEASE_NOTICE}}": release_notice,
        "{{RELEASE_DOWNLOADS}}": release_downloads,
        "{{OVERVIEW_LOCAL_NOTE}}": overview_local_note,
        "{{FE_TAB_LABEL}}": "Barba Enterprise (Flags &amp; Seed)" if is_local else "Zelda 2",
        "{{TITLES_TAB_LABEL}}": "Title Screen Review" if is_local else "All Title Screens",
        "{{WORKSPACE_TABS}}": render_workspace_tabs_html(flavor, games=subgames),
        "{{SUBGAME_VIEWS}}": render_subgame_views_html(flavor, games=subgames),
        "{{PRESET_BAR}}": PRESET_BAR_HTML if is_local else "",
        "{{SEED_FLAGSTRING_BOX}}": SEED_FLAGSTRING_BOX_HTML if is_local else "",
        "{{TITLES_EXPORT_ACTIONS}}": TITLES_EXPORT_HTML if is_local else "",
        "{{CATALOG_JS}}": "local_catalog.js" if is_local else "catalog.js",
        "{{TITLE_DATA_JS}}": "local_title_review_data.js" if is_local else "title_review_data.js",
        "{{SUBGAMES_DATA_JS}}": "local_subgames_data.js" if is_local else "subgames_data.js",
        "{{DEV_SCRIPTS}}": LOCAL_SCRIPTS_HTML if is_local else "",
        "{{LOCAL_STATE_RENDER_JS}}": LOCAL_STATE_RENDER_JS if is_local else "",
    }
    out = template
    for key, val in replacements.items():
        if key not in out:
            raise ValueError(f"Template missing placeholder: {key}")
        out = out.replace(key, val)

    # Strip internal dev views (#view-waldo, #view-feud, #view-duck) and Waldo inline JS from public
    start_marker = "<!-- DEV_VIEWS_START -->"
    end_marker = "<!-- DEV_VIEWS_END -->"
    if start_marker in out and end_marker in out and not is_local:
        pre, rest = out.split(start_marker, 1)
        _, post = rest.split(end_marker, 1)
        out = pre + post

    waldo_start = "// DEV_WALDO_JS_START"
    waldo_end = "// DEV_WALDO_JS_END"
    if waldo_start in out and waldo_end in out and not is_local:
        pre, rest = out.split(waldo_start, 1)
        _, post = rest.split(waldo_end, 1)
        out = pre + post

    out = out.replace(start_marker, "").replace(end_marker, "")
    out = out.replace(waldo_start, "").replace(waldo_end, "")

    return out


def build_flavors(
    flavor: str = "all", refresh_catalog: bool = True, out_dir: Path | None = None
) -> list[Path]:
    target_dir = WEB_DIR if out_dir is None else out_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    if refresh_catalog:
        written.extend(write_web_catalog(out_dir=target_dir, flavor=flavor))
        written.extend(capture_subgame_previews.write_subgames_data_js(out_dir=target_dir, flavor=flavor))
        written.extend(title_dashboard.write_title_review_data_js(out_dir=target_dir, flavor=flavor))
        if flavor in ("local", "all"):
            written.append(z2_strings_dashboard.write_z2_strings_data_js(out_dir=target_dir))
            written.append(ow_tiles_dashboard.write_ow_tiles_data_js(out_dir=target_dir))
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    if flavor in ("public", "all"):
        pub_path = target_dir / "index.html"
        pub_path.write_text(render_flavor(template, "public"), encoding="utf-8")
        written.append(pub_path)

    if flavor in ("local", "all"):
        state_path = target_dir / "local_state.js"
        state_payload = json.dumps(collect_local_state(), indent=2)
        state_path.write_text(f"window.BARBA_LOCAL_STATE = {state_payload};\n", encoding="utf-8")
        written.append(state_path)

        loc_path = target_dir / "local.html"
        loc_path.write_text(render_flavor(template, "local"), encoding="utf-8")
        written.append(loc_path)

    return written


def collect_public_asset_paths(
    public_html: str,
    catalog_payload: dict[str, Any],
    subgames_payload: dict[str, Any],
    titles_payload: dict[str, Any],
) -> set[str]:
    """Return every relative `previews/...` asset referenced by the public build."""
    assets: set[str] = set()

    for f in catalog_payload.get("flags", []):
        prev = f.get("preview")
        if isinstance(prev, dict):
            for k in ("off", "on"):
                if prev.get(k):
                    assets.add(prev[k])
        aud = f.get("audio")
        if isinstance(aud, dict):
            for k in ("off_wav", "on_wav"):
                if aud.get(k):
                    assets.add(aud[k])

    for g in subgames_payload.get("games", []):
        for sc in g.get("scenes", []):
            for side in ("vanilla", "modded"):
                if isinstance(sc.get(side), dict) and sc[side].get("img"):
                    assets.add(sc[side]["img"])

    for g in titles_payload.get("games", []):
        for scr in g.get("screens", []):
            for side in ("vanilla", "ours"):
                if isinstance(scr.get(side), dict) and scr[side].get("img"):
                    assets.add(scr[side]["img"])

    for m in re.finditer(r"previews/[A-Za-z0-9_./-]+", public_html):
        assets.add(m.group(0))

    return assets


def stage_pages_bundle(out_dir: Path, web_dir: Path = WEB_DIR) -> Path:
    """Build a clean GitHub Pages bundle with zero local-only data, scripts, or previews."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    pub_html = render_flavor(template, "public")
    cat_pub = fe_catalog.catalog_payload(include_local=False)
    sub_pub = capture_subgame_previews.build_subgames_payload(include_local=False)
    tit_pub = title_dashboard.title_catalog_payload(include_local=False)

    (out_dir / "index.html").write_text(pub_html, encoding="utf-8")
    cat_json = json.dumps(cat_pub, indent=2)
    (out_dir / "catalog.json").write_text(cat_json + "\n", encoding="utf-8")
    (out_dir / "catalog.js").write_text(f"window.BARBA_FE_CATALOG = {cat_json};\n", encoding="utf-8")
    (out_dir / "subgames_data.js").write_text(
        f"window.BARBA_SUBGAMES_DATA = {json.dumps(sub_pub, indent=2)};\n",
        encoding="utf-8",
    )
    (out_dir / "title_review_data.js").write_text(
        f"window.TITLE_REVIEW_DATA = {json.dumps(tit_pub, indent=2)};\n",
        encoding="utf-8",
    )

    for script_name in ("subgames_ui.js", "title_review_ui.js"):
        src_script = web_dir / script_name
        if src_script.is_file():
            shutil.copy2(src_script, out_dir / script_name)

    for rel_asset in sorted(collect_public_asset_paths(pub_html, cat_pub, sub_pub, tit_pub)):
        src_asset = web_dir / rel_asset
        if not src_asset.is_file():
            print(f"[warn] Missing referenced public asset: {src_asset}", file=sys.stderr)
            continue
        dest_asset = out_dir / rel_asset
        dest_asset.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_asset, dest_asset)

    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Barba Enterprise public & local dashboard flavors")
    parser.add_argument("--flavor", choices=["public", "local", "all"], default="all")
    parser.add_argument("--no-catalog", action="store_true", help="Skip regenerating web/catalog.{json,js}")
    parser.add_argument("--stage-pages", type=Path, help="Write a minimal public-only GitHub Pages bundle to DIR")
    parser.add_argument("--serve", action="store_true", help="Serve web/ locally after building")
    parser.add_argument("--port", type=int, default=8765, help="Port for --serve (default 8765)")
    args = parser.parse_args()

    if args.stage_pages:
        staged = stage_pages_bundle(args.stage_pages)
        print(f"Staged public GitHub Pages bundle in {staged}")
        return

    written = build_flavors(flavor=args.flavor, refresh_catalog=not args.no_catalog)
    for p in written:
        try:
            print(f"Wrote {p.relative_to(ROOT)}")
        except ValueError:
            print(f"Wrote {p}")

    if args.serve:
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(WEB_DIR))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler)
        print(f"Serving web/ at http://127.0.0.1:{args.port}/local.html (public: /index.html)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
