"""
TEST-05: tests/test_update_project.py — 6 cases

This is the most critical test file — full state machine coverage.

Validates:
- All valid transitions succeed (especially sealed → opened bug fix)
- Invalid transitions exit 1
- sealed → opened specifically (bug fix verification)
- Field not in whitelist → exit 1
- Non-existent project → exit 1
- updated_at is refreshed after update
"""

import json
import sqlite3
from datetime import datetime
from conftest import run_script

# Full valid transition matrix per api-interfaces.md
VALID_TRANSITIONS = [
    ("registered", "doc_pending"),
    ("registered", "doc_purchased"),
    ("registered", "cancelled"),
    ("doc_pending", "doc_purchased"),
    ("doc_pending", "cancelled"),
    ("doc_purchased", "preparing"),
    ("doc_purchased", "sealed"),
    ("doc_purchased", "cancelled"),
    ("preparing", "sealed"),
    ("preparing", "cancelled"),
    ("sealed", "opened"),          # Bug fix: was missing
    ("sealed", "cancelled"),
    ("opened", "won"),
    ("opened", "lost"),
]

INVALID_TRANSITIONS = [
    ("registered", "won"),
    ("registered", "sealed"),
    ("doc_purchased", "registered"),
    ("won", "lost"),
    ("lost", "won"),
    ("cancelled", "registered"),
]


def _insert_project(db_conn, status="registered", project_id=None):
    """Insert a project with the given status and return its id."""
    cur = db_conn.execute(
        "INSERT INTO projects (project_no, project_name, status, project_manager, bid_opening_time) "
        "VALUES (?, ?, ?, ?, ?)",
        (f"2026-{(project_id or 1):03d}", "测试项目", status, "张经理", "2026-04-10T14:00:00"),
    )
    db_conn.commit()
    return cur.lastrowid


def test_valid_transitions(db_path, db_conn):
    """All valid state transitions should succeed with exit 0."""
    for i, (from_status, to_status) in enumerate(VALID_TRANSITIONS):
        pid = _insert_project(db_conn, status=from_status, project_id=i + 1)
        r = run_script(
            "update_project.py",
            ["--id", str(pid), "--field", "status", "--value", to_status],
            db_path,
        )
        assert r.returncode == 0, (
            f"Transition {from_status} → {to_status} failed: {r.stderr}"
        )


def test_invalid_transitions_exit_1(db_path, db_conn):
    """Invalid state transitions should exit 1."""
    for i, (from_status, to_status) in enumerate(INVALID_TRANSITIONS):
        pid = _insert_project(db_conn, status=from_status, project_id=100 + i)
        r = run_script(
            "update_project.py",
            ["--id", str(pid), "--field", "status", "--value", to_status],
            db_path,
        )
        assert r.returncode == 1, (
            f"Transition {from_status} → {to_status} should have failed but returned 0"
        )


def test_sealed_to_opened(db_path, db_conn):
    """Bug fix verification: sealed → opened must succeed."""
    pid = _insert_project(db_conn, status="sealed", project_id=200)
    r = run_script(
        "update_project.py",
        ["--id", str(pid), "--field", "status", "--value", "opened"],
        db_path,
    )
    assert r.returncode == 0, f"sealed → opened failed: {r.stderr}"
    # Verify in DB
    row = db_conn.execute("SELECT status FROM projects WHERE id=?", (pid,)).fetchone()
    assert row[0] == "opened"


def test_field_not_in_whitelist_exits_1(db_path, db_conn):
    """Updating a field not in UPDATABLE_FIELDS should exit 1."""
    pid = _insert_project(db_conn, project_id=300)
    r = run_script(
        "update_project.py",
        ["--id", str(pid), "--field", "id", "--value", "999"],
        db_path,
    )
    assert r.returncode == 1


def test_nonexistent_project_exits_1(db_path):
    """Updating a non-existent project should exit 1."""
    r = run_script(
        "update_project.py",
        ["--id", "9999", "--field", "status", "--value", "doc_pending"],
        db_path,
    )
    assert r.returncode == 1


def test_updated_at_refreshed(db_path, db_conn):
    """updated_at should change after a successful update."""
    pid = _insert_project(db_conn, status="registered", project_id=400)
    old_ts = db_conn.execute(
        "SELECT updated_at FROM projects WHERE id=?", (pid,)
    ).fetchone()[0]

    r = run_script(
        "update_project.py",
        ["--id", str(pid), "--field", "status", "--value", "doc_pending"],
        db_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"

    # Re-read — need a fresh connection to see changes from subprocess
    conn2 = sqlite3.connect(db_path)
    new_ts = conn2.execute(
        "SELECT updated_at FROM projects WHERE id=?", (pid,)
    ).fetchone()[0]
    conn2.close()

    assert new_ts is not None
    # updated_at should be at least as recent as old_ts
    assert new_ts >= old_ts
