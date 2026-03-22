"""
TEST-02: tests/test_manage_users.py — 7 cases

Validates:
- Bootstrap first user as director (success + JSON output)
- Bootstrap idempotent (same userid twice returns ok)
- Bootstrap conflict (different userid when director exists → exit 1)
- Add manager by director (success)
- Add rejected if caller is not director (exit 1)
- List all users
- List users filtered by role
"""

import json
from conftest import run_script


def test_bootstrap_first_user(db_path):
    """First bootstrap should register a director and return ok."""
    r = run_script(
        "manage_users.py",
        ["--bootstrap", "--user-id", "u001", "--name", "王总监"],
        db_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert data["status"] == "ok"


def test_bootstrap_idempotent(db_path):
    """Same userid bootstrapped twice should both return ok."""
    for _ in range(2):
        r = run_script(
            "manage_users.py",
            ["--bootstrap", "--user-id", "u001", "--name", "王总监"],
            db_path,
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"


def test_bootstrap_fails_different_director(db_path):
    """A different userid trying to bootstrap when director exists should fail."""
    run_script(
        "manage_users.py",
        ["--bootstrap", "--user-id", "u001", "--name", "王总监"],
        db_path,
    )
    r = run_script(
        "manage_users.py",
        ["--bootstrap", "--user-id", "u999", "--name", "另一人"],
        db_path,
    )
    assert r.returncode == 1


def test_add_manager_by_director(db_path):
    """Director should be able to add a manager."""
    run_script(
        "manage_users.py",
        ["--bootstrap", "--user-id", "u001", "--name", "王总监"],
        db_path,
    )
    r = run_script(
        "manage_users.py",
        ["--add", "--caller-id", "u001", "--user-id", "u002", "--name", "张经理"],
        db_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert data["status"] == "ok"


def test_add_rejected_if_not_director(db_path):
    """A manager should not be able to add other users."""
    run_script(
        "manage_users.py",
        ["--bootstrap", "--user-id", "u001", "--name", "王总监"],
        db_path,
    )
    run_script(
        "manage_users.py",
        ["--add", "--caller-id", "u001", "--user-id", "u002", "--name", "张经理"],
        db_path,
    )
    # manager u002 tries to add u003 — should be rejected
    r = run_script(
        "manage_users.py",
        ["--add", "--caller-id", "u002", "--user-id", "u003", "--name", "李经理"],
        db_path,
    )
    assert r.returncode == 1


def test_list_all(db_path):
    """--list should return a JSON array with at least one user."""
    run_script(
        "manage_users.py",
        ["--bootstrap", "--user-id", "u001", "--name", "王总监"],
        db_path,
    )
    r = run_script("manage_users.py", ["--list"], db_path)
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert isinstance(data, list)
    assert len(data) >= 1


def test_list_by_role(db_path):
    """--list --role manager should only return managers."""
    run_script(
        "manage_users.py",
        ["--bootstrap", "--user-id", "u001", "--name", "王总监"],
        db_path,
    )
    run_script(
        "manage_users.py",
        ["--add", "--caller-id", "u001", "--user-id", "u002", "--name", "张经理"],
        db_path,
    )
    r = run_script("manage_users.py", ["--list", "--role", "manager"], db_path)
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert len(data) >= 1
    assert all(u["role"] == "manager" for u in data)
