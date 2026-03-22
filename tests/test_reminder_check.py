"""
TEST-07: tests/test_reminder_check.py — 7 cases

Validates:
- Empty database returns []
- doc_purchase reminder fires for projects near deadline
- seal_warning reminder fires for projects near seal time
- bid_opening reminder fires for projects near opening (both manager + director)
- Dedup: same-day second run returns [] (reminders table dedup logic)
- Boundary: exactly 3 days remaining → fires
- Expired project (past deadline) → no reminder
"""

import json
import sqlite3
from datetime import datetime, timedelta
from conftest import run_script


def _insert_project(db_conn, project_name, status, project_manager,
                    doc_purchase_deadline=None, suggested_seal_time=None,
                    bid_opening_time=None, project_no="2026-001"):
    """Insert a project with given deadlines and return its id."""
    cur = db_conn.execute(
        "INSERT INTO projects (project_no, project_name, status, project_manager,"
        " doc_purchase_deadline, suggested_seal_time, bid_opening_time) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (project_no, project_name, status, project_manager,
         doc_purchase_deadline, suggested_seal_time, bid_opening_time),
    )
    db_conn.commit()
    return cur.lastrowid


def test_empty_db_returns_empty_list(db_path):
    """With no projects, reminder_check should return [] with exit 0."""
    r = run_script("reminder_check.py", [], db_path)
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert data == []


def test_doc_purchase_reminder(db_path, db_conn):
    """A registered project with doc_purchase_deadline <= 3 days away fires doc_purchase reminder."""
    deadline = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT17:00:00")
    pid = _insert_project(
        db_conn,
        project_name="测试购买提醒",
        status="registered",
        project_manager="张经理",
        doc_purchase_deadline=deadline,
        bid_opening_time="2099-12-31T14:00:00",
    )
    r = run_script("reminder_check.py", [], db_path)
    assert r.returncode == 0, f"stderr: {r.stderr}"
    reminders = json.loads(r.stdout)
    matching = [m for m in reminders if m["project_id"] == pid and m["reminder_type"] == "doc_purchase"]
    assert len(matching) >= 1, f"Expected doc_purchase reminder, got: {reminders}"


def test_seal_warning_reminder(db_path, db_conn):
    """A project with suggested_seal_time <= 2 days away fires seal_warning reminder."""
    seal_time = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT14:00:00")
    pid = _insert_project(
        db_conn,
        project_name="测试封标提醒",
        status="doc_purchased",
        project_manager="张经理",
        bid_opening_time="2099-12-31T14:00:00",
        suggested_seal_time=seal_time,
    )
    r = run_script("reminder_check.py", [], db_path)
    assert r.returncode == 0, f"stderr: {r.stderr}"
    reminders = json.loads(r.stdout)
    matching = [m for m in reminders if m["project_id"] == pid and m["reminder_type"] == "seal_warning"]
    assert len(matching) >= 1, f"Expected seal_warning reminder, got: {reminders}"


def test_bid_opening_reminder_both_roles(db_path, db_conn):
    """A project with bid_opening_time <= 1 day away fires bid_opening for both manager and director."""
    opening = (datetime.now() + timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%S")
    pid = _insert_project(
        db_conn,
        project_name="测试开标提醒",
        status="sealed",
        project_manager="张经理",
        bid_opening_time=opening,
    )
    r = run_script("reminder_check.py", [], db_path)
    assert r.returncode == 0, f"stderr: {r.stderr}"
    reminders = json.loads(r.stdout)
    matching = [m for m in reminders if m["project_id"] == pid and m["reminder_type"] == "bid_opening"]
    roles = {m["recipient_role"] for m in matching}
    assert "manager" in roles, f"Expected manager in roles, got: {roles}"
    assert "director" in roles, f"Expected director in roles, got: {roles}"


def test_dedup_same_day(db_path, db_conn):
    """Running reminder_check twice on the same day should return [] on the second run.

    Dedup key is (project_id, reminder_type, DATE). Once a reminder is written to
    the reminders table, the same-day second run should suppress it.
    """
    deadline = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT17:00:00")
    pid = _insert_project(
        db_conn,
        project_name="测试去重",
        status="registered",
        project_manager="张经理",
        doc_purchase_deadline=deadline,
        bid_opening_time="2099-12-31T14:00:00",
        project_no="2026-901",
    )

    r1 = run_script("reminder_check.py", [], db_path)
    reminders1 = json.loads(r1.stdout)
    assert len(reminders1) > 0, "First run should produce reminders"

    r2 = run_script("reminder_check.py", [], db_path)
    reminders2 = json.loads(r2.stdout)
    assert len(reminders2) == 0, (
        f"Second same-day run should return [] due to dedup, got: {reminders2}"
    )


def test_boundary_exactly_3_days(db_path, db_conn):
    """Exactly 3 days remaining should still fire a reminder (inclusive boundary)."""
    deadline = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%dT17:00:00")
    pid = _insert_project(
        db_conn,
        project_name="测试边界3天",
        status="registered",
        project_manager="张经理",
        doc_purchase_deadline=deadline,
        bid_opening_time="2099-12-31T14:00:00",
        project_no="2026-902",
    )
    r = run_script("reminder_check.py", [], db_path)
    assert r.returncode == 0, f"stderr: {r.stderr}"
    reminders = json.loads(r.stdout)
    matching = [m for m in reminders if m["project_id"] == pid and m["reminder_type"] == "doc_purchase"]
    assert len(matching) >= 1, f"Exactly 3 days remaining should fire reminder, got: {reminders}"


def test_expired_project_no_reminder(db_path, db_conn):
    """A project with past doc_purchase_deadline should not fire a reminder."""
    deadline = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT17:00:00")
    pid = _insert_project(
        db_conn,
        project_name="已过期项目",
        status="registered",
        project_manager="张经理",
        doc_purchase_deadline=deadline,
        bid_opening_time="2099-12-31T14:00:00",
        project_no="2026-903",
    )
    r = run_script("reminder_check.py", [], db_path)
    assert r.returncode == 0, f"stderr: {r.stderr}"
    reminders = json.loads(r.stdout)
    matching = [m for m in reminders if m["project_id"] == pid]
    assert len(matching) == 0, f"Expired project should not get reminders, got: {matching}"
