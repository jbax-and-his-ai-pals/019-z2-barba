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
# Minimum recoverable count as of 2026-11-20. See docs/BUILD.md.
HISTORICAL_BASELINE = 59

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
