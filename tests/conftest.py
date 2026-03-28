"""
Shared fixtures and helpers for all test modules.

All scripts are tested via subprocess (CLI contract testing).
Each test gets an isolated temporary database via the DB_PATH env var.
"""

import pytest
import os
import sys
import subprocess
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = str(Path(__file__).parent.parent.resolve())


@pytest.fixture
def db_path(tmp_path):
    """Create a fresh database using init_db.py and return its path."""
    p = str(tmp_path / "test_bids.db")
    env = os.environ.copy()
    env["DB_PATH"] = p
    result = subprocess.run(
        [sys.executable, "-m", "milb_tracker.scripts.init_db"],
        env=env,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"init_db failed: {result.stderr}"
    return p


@pytest.fixture
def db_conn(db_path):
    """Return an open sqlite3 connection to the test database."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    yield conn
    conn.close()


def run_script(script, args, db_path, input_text=None):
    """Run a script under milb_tracker/scripts/ with DB_PATH pointing to the test database."""
    env = os.environ.copy()
    env["DB_PATH"] = db_path
    return subprocess.run(
        [sys.executable, "-m", f"milb_tracker.scripts.{script.replace('.py', '')}"] + args,
        capture_output=True,
        text=True,
        env=env,
        cwd=PROJECT_ROOT,
        input=input_text,
    )
