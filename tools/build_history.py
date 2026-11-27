"""Record successful Barba builds and export the history as CSV."""
from __future__ import annotations

import csv
import json
import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY_FILE = ROOT / '.build-history.sqlite3'
# Estimated pre-numbering baseline as of 2026-11-25 (+200 over initial 59 lower bound). See docs/BUILD.md.
HISTORICAL_BASELINE = 259

# Per-subgame baselines derived from docs/STATUS.md entry counts as of 2026-11-26.
SUBGAME_BASELINES: dict[str, int] = {
    'dk': 11,
    'duck': 19,
    'f13': 14,
    'feud': 63,
    'mm2': 4,
    'mtpo': 4,
    'smb': 6,
    'waldo': 22,
    'wheel': 4,
    'zelda': 4,
}

SCHEMA = """
    CREATE TABLE IF NOT EXISTS builds (
        build_number INTEGER PRIMARY KEY,
        completed_utc TEXT NOT NULL,
        output_dir TEXT NOT NULL,
        output_sha256 TEXT NOT NULL,
        bps_sha256 TEXT NOT NULL,
        audio TEXT NOT NULL,
        waldo_portal INTEGER NOT NULL,
        git_commit TEXT,
        git_dirty INTEGER,
        release TEXT
    )
"""

SUBGAME_SCHEMA = """
    CREATE TABLE IF NOT EXISTS subgame_builds (
        game TEXT NOT NULL,
        build_number INTEGER NOT NULL,
        completed_utc TEXT NOT NULL,
        mapper TEXT NOT NULL,
        output_path TEXT NOT NULL,
        output_sha256 TEXT NOT NULL,
        git_commit TEXT,
        git_dirty INTEGER,
        PRIMARY KEY (game, build_number)
    )
"""


def git_source(root: Path) -> tuple[str | None, bool | None]:
    try:
        commit = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=root, stderr=subprocess.DEVNULL,
            text=True).strip()
        changes = subprocess.check_output(
            ['git', 'status', '--porcelain'], cwd=root, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        return None, None
    return commit, bool(changes)


def record_build(history: Path, output: Path, report: dict, metadata: dict) -> None:
    with closing(sqlite3.connect(history, timeout=30)) as connection, connection:
        connection.execute(SCHEMA)
        # Lock allocation and recording together so different output dirs share
        # the same sequence. Roll back the insert if the report cannot be written.
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute(
            'SELECT COALESCE(MAX(build_number), ?) + 1 FROM builds',
            (HISTORICAL_BASELINE,)).fetchone()
        entry = {'build_number': row[0],
                 'completed_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                 'output_sha256': report['output_sha256'], **metadata}
        connection.execute("""
            INSERT INTO builds VALUES (
                :build_number, :completed_utc, :output_dir, :output_sha256,
                :bps_sha256, :audio, :waldo_portal, :git_commit, :git_dirty, :release
            )
        """, entry)
        report.update(entry, historical_baseline=HISTORICAL_BASELINE)
        report_path = output / 'build-report.json'
        report_path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')


def next_build_number(history: Path) -> int:
    """Return the next Zelda II build number without recording a build."""
    if not history.is_file():
        return HISTORICAL_BASELINE + 1
    with closing(sqlite3.connect(history, timeout=30)) as connection:
        connection.execute(SCHEMA)
        row = connection.execute(
            'SELECT COALESCE(MAX(build_number), ?) + 1 FROM builds',
            (HISTORICAL_BASELINE,),
        ).fetchone()
    return row[0]


def get_subgame_build_number(history: Path, game: str) -> int:
    """Return the current build number for a subgame, or its baseline if unrecorded."""
    baseline = SUBGAME_BASELINES.get(game, 0)
    if not history.is_file():
        return baseline
    with closing(sqlite3.connect(history, timeout=30)) as connection:
        connection.execute(SUBGAME_SCHEMA)
        row = connection.execute(
            'SELECT MAX(build_number) FROM subgame_builds WHERE game = ?',
            (game,),
        ).fetchone()
    return row[0] if row and row[0] is not None else baseline


def get_all_subgame_build_numbers(history: Path) -> dict[str, int]:
    """Return {game: current_build_number} for every known subgame."""
    return {game: get_subgame_build_number(history, game) for game in SUBGAME_BASELINES}


def next_subgame_build_number(history: Path, game: str) -> int:
    """Return the next build number to embed in a subgame ROM before recording it."""
    return get_subgame_build_number(history, game) + 1


def record_subgame_build(
    history: Path,
    game: str,
    build_number: int,
    mapper: str,
    output_path: Path,
    output_sha256: str,
) -> int:
    """Record a completed subgame build in subgame_builds."""
    commit, dirty = git_source(ROOT)
    rel_out = output_path.resolve()
    if rel_out.is_relative_to(ROOT):
        rel_out = rel_out.relative_to(ROOT)
    with closing(sqlite3.connect(history, timeout=30)) as connection, connection:
        connection.execute(SUBGAME_SCHEMA)
        connection.execute('BEGIN IMMEDIATE')
        connection.execute(
            """
            INSERT INTO subgame_builds VALUES (
                :game, :build_number, :completed_utc, :mapper,
                :output_path, :output_sha256, :git_commit, :git_dirty
            )
            """,
            {
                'game': game,
                'build_number': build_number,
                'completed_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                'mapper': mapper,
                'output_path': rel_out.as_posix(),
                'output_sha256': output_sha256,
                'git_commit': commit,
                'git_dirty': int(dirty) if dirty is not None else None,
            },
        )
    return build_number


def export_csv(history: Path) -> None:
    if not history.is_file():
        raise SystemExit(f'No build history at {history}. Run tools/build.py first.')
    with closing(sqlite3.connect(history)) as connection:
        rows = connection.execute('SELECT * FROM builds ORDER BY build_number')
        writer = csv.writer(sys.stdout, lineterminator='\n')
        writer.writerow(column[0] for column in rows.description)
        writer.writerows(rows)


if __name__ == '__main__':
    export_csv(HISTORY_FILE)
