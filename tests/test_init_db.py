"""
TEST-01: tests/test_init_db.py — 6 cases

Validates:
- All 4 tables exist (projects, bid_results, reminders, users)
- projects.project_no column exists (fix verification)
- users.wecom_userid column exists (fix verification)
- Idempotent execution (run twice without error)
- WAL journal mode enabled
- attachments/ directory created adjacent to DB_PATH
"""

import os
import sys
import subprocess
import sqlite3
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).parent.parent.resolve())


def test_all_tables_exist(db_path, db_conn):
    """All 4 required tables must be present after init."""
    tables = db_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = {t[0] for t in tables}
    assert {"projects", "bid_results", "reminders", "users"}.issubset(names)


def test_projects_has_project_no_column(db_path, db_conn):
    """Verify fix: project_no column exists in projects table."""
    db_conn.execute("SELECT project_no FROM projects LIMIT 0")


def test_users_has_wecom_userid(db_path, db_conn):
    """Verify fix: wecom_userid column exists in users table."""
    db_conn.execute("SELECT wecom_userid FROM users LIMIT 0")


def test_idempotent(tmp_path):
    """Running init_db.py twice should succeed both times."""
    p = str(tmp_path / "test_idempotent.db")
    env = os.environ.copy()
    env["DB_PATH"] = p
    for i in range(2):
        r = subprocess.run(
            [sys.executable, "-m", "milb_tracker.scripts.init_db"],
            env=env,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, f"Run {i+1} failed: {r.stderr}"


def test_wal_mode(db_path, db_conn):
    """Database should use WAL journal mode."""
    mode = db_conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"


def test_attachments_dir_created(db_path):
    """attachments/ directory should be created adjacent to DB_PATH (not hardcoded)."""
    db_dir = os.path.dirname(db_path)
    assert os.path.isdir(os.path.join(db_dir, "attachments"))
