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
    return "\n".join(
        f'    <div id="view-sub-{g["id"]}" class="hidden"></div>'
        for g in subgame_tabs_for_flavor(flavor, games=games)
    )

DEV_TABS_HTML = """\
      <button type="button" class="tab-btn is-local-only" data-tab="z2strings" title="Local only — not published on GitHub Pages">Z2 String Review<span class="tab-local-pill">Local</span></button>
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


def render_flavor(
    template: str, flavor: str, subgames: list[dict[str, Any]] | None = None
) -> str:
    if flavor not in ("public", "local"):
        raise ValueError(f"Unknown flavor: {flavor}")
    is_local = flavor == "local"

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
        "{{FE_TAB_LABEL}}": "Barba Enterprise (Flags &amp; Seed)" if is_local else "Zelda 2",
        "{{TITLES_TAB_LABEL}}": "Title Screen Review" if is_local else "Title Screens",
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
