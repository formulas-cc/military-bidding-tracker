"""
TEST-06: tests/test_record_result.py — 4 cases

Validates:
- Record a win (status → won, is_winner=1)
- Record a loss (status → lost, is_winner=0)
- Wrong source status rejected (e.g. preparing → exit 1)
- Non-existent project → exit 1
"""

import json
import sqlite3
from conftest import run_script


def _insert_project(db_conn, status="opened", project_id=None):
    """Insert a project with the given status and return its id."""
    cur = db_conn.execute(
        "INSERT INTO projects (project_no, project_name, status, project_manager, bid_opening_time) "
        "VALUES (?, ?, ?, ?, ?)",
        (f"2026-{(project_id or 1):03d}", "测试项目", status, "张经理", "2026-04-10T14:00:00"),
    )
    db_conn.commit()
    return cur.lastrowid


def test_record_won(db_path, db_conn):
    """Recording a win should set status to 'won' and is_winner=1."""
    pid = _insert_project(db_conn, status="opened", project_id=1)
    r = run_script(
        "record_result.py",
        [
            "--project-id", str(pid),
            "--our-price", "980000",
            "--winning-price", "980000",
            "--winner", "我方公司",
            "--won", "true",
            "--notes", "顺利中标",
        ],
        db_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"

    # Verify project status
    conn2 = sqlite3.connect(db_path)
    row = conn2.execute("SELECT status FROM projects WHERE id=?", (pid,)).fetchone()
    assert row[0] == "won"
    # Verify bid_results
    br = conn2.execute(
        "SELECT is_winner FROM bid_results WHERE project_id=?", (pid,)
    ).fetchone()
    assert br[0] == 1
    conn2.close()


def test_record_lost(db_path, db_conn):
    """Recording a loss should set status to 'lost' and is_winner=0."""
    pid = _insert_project(db_conn, status="opened", project_id=2)
    r = run_script(
        "record_result.py",
        [
            "--project-id", str(pid),
            "--our-price", "980000",
            "--winning-price", "950000",
            "--winner", "某某公司",
            "--won", "false",
            "--notes", "排名第二",
        ],
        db_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"

    conn2 = sqlite3.connect(db_path)
    row = conn2.execute("SELECT status FROM projects WHERE id=?", (pid,)).fetchone()
    assert row[0] == "lost"
    br = conn2.execute(
        "SELECT is_winner FROM bid_results WHERE project_id=?", (pid,)
    ).fetchone()
    assert br[0] == 0
    conn2.close()


def test_wrong_status_rejected(db_path, db_conn):
    """Recording result on a project in 'preparing' status should exit 1."""
    pid = _insert_project(db_conn, status="preparing", project_id=3)
    r = run_script(
        "record_result.py",
        ["--project-id", str(pid), "--won", "false"],
        db_path,
    )
    assert r.returncode == 1


def test_nonexistent_project(db_path):
    """Recording result on a non-existent project should exit 1."""
    r = run_script(
        "record_result.py",
        ["--project-id", "9999", "--won", "false"],
        db_path,
    )
    assert r.returncode == 1
