"""
TEST-03: tests/test_register_project.py — 6 cases

Validates:
- Normal registration with project_no in JSON output
- project_no auto-increments (YYYY-NNN)
- suggested_seal_time returned in output
- suggested_seal_time skips weekends
- Bad JSON input → exit 1
- Missing --manager-name → exit != 0
"""

import json
from datetime import datetime
from conftest import run_script

SAMPLE_PROJECT = {
    "project_name": "网络安全设备采购",
    "budget": 500000,
    "procurer": "某军区后勤部",
    "bid_agency": "军采中心",
    "manager_contact": "13800138000",
    "registration_deadline": "2026-03-25T17:00:00",
    "doc_purchase_deadline": "2026-04-01T17:00:00",
    "bid_opening_time": "2026-04-10T14:00:00",
    "doc_purchase_location": "网上下载",
    "doc_purchase_price": 0,
    "doc_required_materials": "营业执照",
}


def test_normal_registration(db_path):
    """Normal registration should return JSON with project_id, project_no, etc."""
    r = run_script(
        "register_project.py",
        [
            "--json", json.dumps(SAMPLE_PROJECT),
            "--manager-name", "张经理",
            "--travel-days", "1",
        ],
        db_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert "project_id" in data
    assert "project_no" in data
    assert data["project_no"].startswith(str(datetime.now().year))


def test_project_no_increments(db_path):
    """Registering two projects should produce sequential project_no values."""
    r1 = run_script(
        "register_project.py",
        ["--json", json.dumps(SAMPLE_PROJECT), "--manager-name", "张经理"],
        db_path,
    )
    project2 = {**SAMPLE_PROJECT, "project_name": "第二个项目"}
    r2 = run_script(
        "register_project.py",
        ["--json", json.dumps(project2), "--manager-name", "张经理"],
        db_path,
    )
    assert r1.returncode == 0 and r2.returncode == 0
    no1 = json.loads(r1.stdout)["project_no"]
    no2 = json.loads(r2.stdout)["project_no"]
    seq1 = int(no1.split("-")[1])
    seq2 = int(no2.split("-")[1])
    assert seq2 == seq1 + 1


def test_suggested_seal_time_returned(db_path):
    """Output JSON should include suggested_seal_time."""
    r = run_script(
        "register_project.py",
        [
            "--json", json.dumps(SAMPLE_PROJECT),
            "--manager-name", "张经理",
            "--travel-days", "2",
        ],
        db_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert "suggested_seal_time" in data
    assert data["suggested_seal_time"] is not None


def test_suggested_seal_skips_weekend(db_path):
    """Suggested seal time should not fall on Saturday or Sunday.

    2026-04-13 is a Monday. With travel_days=2, raw seal = Apr 11 (Sat).
    Should be adjusted to Friday Apr 10.
    """
    project = {**SAMPLE_PROJECT, "bid_opening_time": "2026-04-13T14:00:00"}
    r = run_script(
        "register_project.py",
        [
            "--json", json.dumps(project),
            "--manager-name", "张经理",
            "--travel-days", "2",
        ],
        db_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    seal = datetime.fromisoformat(data["suggested_seal_time"])
    assert seal.weekday() not in (5, 6), f"Seal time {seal} falls on weekend"


def test_bad_json_exits_1(db_path):
    """Invalid JSON should cause exit code 1."""
    r = run_script(
        "register_project.py",
        ["--json", "not-valid-json", "--manager-name", "张经理"],
        db_path,
    )
    assert r.returncode == 1


def test_missing_manager_name_exits_nonzero(db_path):
    """Missing --manager-name should cause a non-zero exit."""
    r = run_script(
        "register_project.py",
        ["--json", json.dumps(SAMPLE_PROJECT)],
        db_path,
    )
    assert r.returncode != 0
