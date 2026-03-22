"""
TEST-08: tests/test_stats.py — 5 cases

Validates:
- Empty database does not crash (returns correct empty output)
- Global win_rate = won / (won + lost)
- stats_by_manager groups correctly by project_manager
- stats_by_month groups by month
- --period 2026-Q1 filters to Q1 date range
"""

import json
from conftest import run_script


def _seed_stats_data(db_conn):
    """Insert test data for stats tests: managers, projects, and bid_results."""
    # Insert users
    db_conn.execute(
        "INSERT INTO users (wecom_userid, name, role) VALUES (?, ?, ?)",
        ("m1", "王经理", "manager"),
    )
    db_conn.execute(
        "INSERT INTO users (wecom_userid, name, role) VALUES (?, ?, ?)",
        ("m2", "张经理", "manager"),
    )
    db_conn.execute(
        "INSERT INTO users (wecom_userid, name, role) VALUES (?, ?, ?)",
        ("d1", "总监", "director"),
    )

    def insert_project(no, name, manager, status, opened_at):
        db_conn.execute(
            "INSERT INTO projects (project_no, project_name, status, project_manager,"
            " bid_opening_time, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (no, name, status, manager, opened_at, opened_at),
        )
        return db_conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def insert_result(project_id, our_price, winning_price, is_winner):
        db_conn.execute(
            "INSERT INTO bid_results (project_id, our_bid_price, winning_price, is_winner)"
            " VALUES (?, ?, ?, ?)",
            (project_id, our_price, winning_price, is_winner),
        )

    # Won projects
    p1 = insert_project("2026-001", "项目A", "王经理", "won", "2026-01-15T14:00:00")
    insert_result(p1, 980000, 980000, 1)

    p2 = insert_project("2026-002", "项目B", "王经理", "won", "2026-02-10T14:00:00")
    insert_result(p2, 1200000, 1150000, 1)

    p3 = insert_project("2026-003", "项目C", "张经理", "won", "2026-02-20T14:00:00")
    insert_result(p3, 500000, 490000, 1)

    # Lost projects
    p4 = insert_project("2026-004", "项目D", "王经理", "lost", "2026-03-01T14:00:00")
    insert_result(p4, 800000, 750000, 0)

    p5 = insert_project("2026-005", "项目E", "张经理", "lost", "2026-03-10T14:00:00")
    insert_result(p5, 600000, 580000, 0)

    # Active project (no result yet)
    insert_project("2026-006", "项目F", "王经理", "preparing", "2026-04-01T14:00:00")

    db_conn.commit()


def test_empty_db_no_crash(db_path):
    """stats.py with empty database should exit 0 and return valid empty output."""
    r = run_script("stats.py", [], db_path)
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    # Per architect clarification: empty DB → {"total": 0, "won": 0, "lost": 0, "active": 0,
    # "win_rate": 0, "avg_budget": null, "avg_price_diff": null}
    assert data["total"] == 0
    assert data["won"] == 0
    assert data["lost"] == 0
    assert data["active"] == 0
    assert data["win_rate"] == 0


def test_global_win_rate(db_path, db_conn):
    """Global stats: total = COUNT(projects with bid_results) = 5; win_rate = won/(won+lost) = 3/5 = 0.6."""
    _seed_stats_data(db_conn)
    r = run_script("stats.py", [], db_path)
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert data["total"] == 5   # only projects with bid_results are counted in total
    assert data["won"] == 3
    assert data["lost"] == 2
    assert data["active"] == 0  # active = projects with bid_results that are not in terminal state; all seed projects with results are won/lost
    assert abs(data["win_rate"] - 0.6) < 0.01


def test_by_manager(db_path, db_conn):
    """stats_by_manager should return per-manager breakdown with correct win_rates."""
    _seed_stats_data(db_conn)
    r = run_script("stats.py", ["--by-manager"], db_path)
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert isinstance(data, list)
    # Build a lookup by manager name
    by_name = {row["manager"]: row for row in data}

    # 王经理: won=2, lost=1 → win_rate=2/3≈0.667
    assert "王经理" in by_name
    wang = by_name["王经理"]
    assert wang["won"] == 2
    assert wang["lost"] == 1
    assert abs(wang["win_rate"] - 2/3) < 0.01

    # 张经理: won=1, lost=1 → win_rate=0.5
    assert "张经理" in by_name
    zhang = by_name["张经理"]
    assert zhang["won"] == 1
    assert zhang["lost"] == 1
    assert abs(zhang["win_rate"] - 0.5) < 0.01


def test_by_month(db_path, db_conn):
    """stats_by_month should group results by calendar month."""
    _seed_stats_data(db_conn)
    r = run_script("stats.py", ["--by-month"], db_path)
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert isinstance(data, list)
    by_month = {row["month"]: row for row in data}

    # Jan 2026: 1 won (项目A)
    assert "2026-01" in by_month
    jan = by_month["2026-01"]
    assert jan["won"] == 1
    assert jan["lost"] == 0
    assert abs(jan["win_rate"] - 1.0) < 0.01

    # Feb 2026: 1 won (项目B) + 1 won (项目C)
    assert "2026-02" in by_month
    feb = by_month["2026-02"]
    assert feb["won"] == 2
    assert feb["lost"] == 0

    # Mar 2026: 1 lost (项目D) + 1 lost (项目E)
    assert "2026-03" in by_month
    mar = by_month["2026-03"]
    assert mar["won"] == 0
    assert mar["lost"] == 2
    assert abs(mar["win_rate"] - 0.0) < 0.01


def test_period_filter_quarter(db_path, db_conn):
    """--period 2026-Q1 should filter to Jan 1 – Mar 31, 2026."""
    _seed_stats_data(db_conn)
    r = run_script("stats.py", ["--period", "2026-Q1"], db_path)
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    # Q1 = Jan + Feb + Mar = won:3, lost:2 → win_rate = 3/5 = 0.6
    assert data["total"] == 5
    assert data["won"] == 3
    assert data["lost"] == 2
    assert abs(data["win_rate"] - 0.6) < 0.01
