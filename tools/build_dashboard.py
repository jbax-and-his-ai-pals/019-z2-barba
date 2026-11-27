"""Standardized builder for both Barba Enterprise dashboard flavors.

Generates:
  - public (`web/index.html`): GitHub Pages presentation build (Flags & Showcase,
    Title Screens showcase, Client-Side BPS ROM Patcher).
  - local  (`web/local.html` + `web/local_state.js`, gitignored): Internal dev
    dashboard with Build State bar, CLI Build command, Title Screen Review
    (status/notes/export), Where's Barba? Tile Tagger, Family Feud Cast, and
    Barba's Hunt Tiles / CHR Inspector.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import fe_catalog  # noqa: E402

ROOT = _TOOLS_DIR.parent
TEMPLATE_PATH = _TOOLS_DIR / "dashboard_template.html"
WEB_DIR = ROOT / "web"

DEV_TABS_HTML = """\
      <button type="button" class="tab-btn" data-tab="waldo">Where's Barba? Tile Tagger</button>
      <button type="button" class="tab-btn" data-tab="feud">Family Feud Cast</button>
      <button type="button" class="tab-btn" data-tab="duck">Barba's Hunt Tiles</button>"""

CLI_ROW_HTML = """\
      <div class="row">
        <label for="cli-cmd">CLI Build</label>
        <input id="cli-cmd" class="mono" readonly>
        <button id="copy-cli" type="button">Copy CLI</button>
      </div>"""

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
      el.innerHTML =
        `<span>Latest Build: <strong>${bnum}</strong></span>` +
        `<span>SHA-256: <code>${sha}</code></span>` +
        `<span>Built: <strong>${ts}</strong></span>` +
        (wired ? `<span>Wired CLI Toggles: <strong>${wired}</strong></span>` : '');
    })();"""


def collect_local_state() -> dict[str, Any]:
    """Read current build-report.json and .build-history.sqlite3 if available."""
    state: dict[str, Any] = {
        "build_number": None,
        "sha256": None,
        "built_at": None,
        "wired_flags": list(fe_catalog.WIRED_FLAG_IDS),
        "flag_count": len(fe_catalog.FLAGS),
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


def write_web_catalog() -> None:
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(fe_catalog.catalog_payload(), indent=2)
    (WEB_DIR / "catalog.json").write_text(payload + "\n", encoding="utf-8")
    (WEB_DIR / "catalog.js").write_text(f"window.BARBA_FE_CATALOG = {payload};\n", encoding="utf-8")


def render_flavor(template: str, flavor: str) -> str:
    if flavor not in ("public", "local"):
        raise ValueError(f"Unknown flavor: {flavor}")
    is_local = flavor == "local"

    replacements = {
        "{{FLAVOR}}": flavor,
        "{{PAGE_TITLE}}": (
            "Zelda II: Barba Enterprise (Internal Dev) — Flags, Graphics & State"
            if is_local
            else "Zelda II: Barba Enterprise — Visual Flag & Seed Builder"
        ),
        "{{HEADER_BADGE}}": (
            ' <span class="badge b-coupled" style="vertical-align:middle;margin-left:8px;">Internal Dev</span>'
            if is_local
            else ""
        ),
        "{{HEADER_SUBTITLE}}": (
            "Internal dev workspace — flag/seed builder, build state, title review, and graphics/tile iteration"
            if is_local
            else "Composable ROM flag builder &amp; seed showcase — Vanilla Z2 baseline to full Barba Mode"
        ),
        "{{LOCAL_STATE_BAR}}": LOCAL_STATE_BAR_HTML if is_local else "",
        "{{TITLES_TAB_LABEL}}": "Title Screen Review" if is_local else "Title Screens",
        "{{DEV_TABS}}": DEV_TABS_HTML if is_local else "",
        "{{CLI_ROW}}": CLI_ROW_HTML if is_local else "",
        "{{TITLES_EXPORT_ACTIONS}}": TITLES_EXPORT_HTML if is_local else "",
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

    if is_local:
        out = out.replace(start_marker, "").replace(end_marker, "")
        out = out.replace(waldo_start, "").replace(waldo_end, "")
    else:
        out = out.replace(start_marker, "").replace(end_marker, "")
        out = out.replace(waldo_start, "").replace(waldo_end, "")

    return out


def build_flavors(flavor: str = "all", refresh_catalog: bool = True) -> list[Path]:
    if refresh_catalog:
        write_web_catalog()
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if flavor in ("public", "all"):
        pub_path = WEB_DIR / "index.html"
        pub_path.write_text(render_flavor(template, "public"), encoding="utf-8")
        written.append(pub_path)

    if flavor in ("local", "all"):
        state_path = WEB_DIR / "local_state.js"
        state_payload = json.dumps(collect_local_state(), indent=2)
        state_path.write_text(f"window.BARBA_LOCAL_STATE = {state_payload};\n", encoding="utf-8")
        written.append(state_path)

        loc_path = WEB_DIR / "local.html"
        loc_path.write_text(render_flavor(template, "local"), encoding="utf-8")
        written.append(loc_path)

    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Barba Enterprise public & local dashboard flavors")
    parser.add_argument("--flavor", choices=["public", "local", "all"], default="all")
    parser.add_argument("--no-catalog", action="store_true", help="Skip regenerating web/catalog.{json,js}")
    parser.add_argument("--serve", action="store_true", help="Serve web/ locally after building")
    parser.add_argument("--port", type=int, default=8765, help="Port for --serve (default 8765)")
    args = parser.parse_args()

    written = build_flavors(flavor=args.flavor, refresh_catalog=not args.no_catalog)
    for p in written:
        print(f"Wrote {p.relative_to(ROOT)}")

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
