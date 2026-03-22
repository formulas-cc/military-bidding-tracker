"""
TEST-04: tests/test_query_projects.py — 6 cases

Uses direct DB inserts for test data to reduce dependency on register_project.

Validates:
- Director sees all projects
- Manager sees only own projects
- --keyword matches project_no exactly
- --keyword matches project_name with LIKE
- --active-only filters terminal states
- --user-id with nonexistent user → exit 1
"""

import json
import sqlite3
from conftest import run_script


def _seed_users_and_projects(db_conn, db_path):
    """Insert test users and projects directly into the database."""
    # Insert users
    db_conn.execute(
        "INSERT INTO users (wecom_userid, name, role) VALUES (?, ?, ?)",
        ("director1", "王总监", "director"),
    )
    db_conn.execute(
        "INSERT INTO users (wecom_userid, name, role) VALUES (?, ?, ?)",
        ("manager1", "张经理", "manager"),
    )
    db_conn.execute(
        "INSERT INTO users (wecom_userid, name, role) VALUES (?, ?, ?)",
        ("manager2", "李经理", "manager"),
    )
    # Insert projects
    db_conn.execute(
        "INSERT INTO projects (project_no, project_name, status, project_manager, bid_opening_time) "
        "VALUES (?, ?, ?, ?, ?)",
        ("2026-001", "网络安全设备采购", "registered", "张经理", "2026-04-10T14:00:00"),
    )
    db_conn.execute(
        "INSERT INTO projects (project_no, project_name, status, project_manager, bid_opening_time) "
        "VALUES (?, ?, ?, ?, ?)",
        ("2026-002", "服务器集群采购", "preparing", "李经理", "2026-04-15T14:00:00"),
    )
    db_conn.execute(
        "INSERT INTO projects (project_no, project_name, status, project_manager, bid_opening_time) "
        "VALUES (?, ?, ?, ?, ?)",
        ("2026-003", "旧项目已中标", "won", "张经理", "2026-01-10T14:00:00"),
    )
    db_conn.commit()


def test_director_sees_all(db_path, db_conn):
    """Director with --active-only should see all active projects (not terminal)."""
    _seed_users_and_projects(db_conn, db_path)
    r = run_script(
        "query_projects.py",
        ["--user-id", "director1", "--active-only"],
        db_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert isinstance(data, list)
    # Should see 2 active projects (registered + preparing), not the won one
    assert len(data) == 2


def test_manager_sees_own_projects(db_path, db_conn):
    """Manager should only see their own projects."""
    _seed_users_and_projects(db_conn, db_path)
    r = run_script(
        "query_projects.py",
        ["--user-id", "manager1", "--active-only"],
        db_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    # manager1 = 张经理, has 1 active project (2026-001, registered)
    assert len(data) == 1
    assert data[0]["project_manager"] == "张经理"


def test_keyword_matches_project_no(db_path, db_conn):
    """--keyword with exact project_no should return that project."""
    _seed_users_and_projects(db_conn, db_path)
    r = run_script(
        "query_projects.py",
        ["--user-id", "director1", "--keyword", "2026-002"],
        db_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert len(data) == 1
    assert data[0]["project_no"] == "2026-002"


def test_keyword_fuzzy_matches_project_name(db_path, db_conn):
    """--keyword with partial project name should match via LIKE."""
    _seed_users_and_projects(db_conn, db_path)
    r = run_script(
        "query_projects.py",
        ["--user-id", "director1", "--keyword", "网络安全"],
        db_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert len(data) >= 1
    assert "网络安全" in data[0]["project_name"]


def test_active_only_excludes_terminal(db_path, db_conn):
    """--active-only should exclude won/lost/cancelled projects."""
    _seed_users_and_projects(db_conn, db_path)
    r = run_script(
        "query_projects.py",
        ["--user-id", "director1", "--active-only"],
        db_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    statuses = {p["status"] for p in data}
    assert "won" not in statuses
    assert "lost" not in statuses
    assert "cancelled" not in statuses


def test_nonexistent_user_exits_1(db_path, db_conn):
    """--user-id with unknown wecom_userid should exit 1."""
    _seed_users_and_projects(db_conn, db_path)
    r = run_script(
        "query_projects.py",
        ["--user-id", "ghost_user"],
        db_path,
    )
    assert r.returncode == 1


def test_no_user_id_returns_all_active(db_path, db_conn):
    """Without --user-id, query_projects should return all active projects (no error).

    Per architect clarification: --user-id=None returns all active projects without error.
    """
    _seed_users_and_projects(db_conn, db_path)
    r = run_script("query_projects.py", [], db_path)
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    # Same as director: 2 active projects (registered + preparing), not the won one
    assert isinstance(data, list)
    assert len(data) == 2
