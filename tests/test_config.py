"""
TEST-09: tests/test_config.py — .env 配置加载优先级验证

验证点：
- TC-01: CWD/.env 中的值被正确加载
- TC-02: ~/.config/milb-tracker/.env 中的值被正确加载
- TC-03: CWD/.env 优先于 ~/.config/milb-tracker/.env（相同键时 CWD 胜出）
- TC-04: 进程环境变量优先于所有 .env 文件（最高优先级）
- TC-05: 无任何 .env 时返回内置默认值
- TC-06: .env 文件中的注释行和空行被正确忽略
- TC-07: ATTACHMENTS_DIR 默认为 DB_PATH 同级的 attachments/ 目录
- TC-08: ATTACHMENTS_DIR 可通过 .env 独立覆盖
"""

import os
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).parent.parent.resolve())

# 用于通过子进程测试 config 模块的辅助脚本片段
_PRINT_DB_PATH = (
    "import sys; sys.path.insert(0, '.'); "
    "from milb_tracker.config import get_db_path; "
    "print(get_db_path())"
)

_PRINT_ATTACHMENTS_DIR = (
    "import sys; sys.path.insert(0, '.'); "
    "from milb_tracker.config import get_attachments_dir; "
    "print(get_attachments_dir())"
)


def _run(code: str, *, cwd: str, home: str | None = None, extra_env: dict | None = None) -> str:
    """在干净的子进程中运行 Python 代码片段，返回 stdout（去除空白）。"""
    env = {k: v for k, v in os.environ.items() if k not in ("DB_PATH", "ATTACHMENTS_DIR")}
    # 将项目根目录加入 PYTHONPATH，确保 milb_tracker 可被导入
    env["PYTHONPATH"] = PROJECT_ROOT
    # 用 home 参数隔离 ~，使 ~/.config/milb-tracker/.env 指向临时目录
    env["HOME"] = home or cwd
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
    )
    assert result.returncode == 0, f"子进程失败:\n{result.stderr}"
    return result.stdout.strip()


def test_cwd_env_loaded(tmp_path):
    """TC-01: CWD/.env 中的 DB_PATH 被正确加载。"""
    db = str(tmp_path / "from_cwd.db")
    (tmp_path / ".env").write_text(f"DB_PATH={db}\n")

    value = _run(_PRINT_DB_PATH, cwd=str(tmp_path))
    assert value == db


def test_user_config_env_loaded(tmp_path):
    """TC-02: ~/.config/milb-tracker/.env 中的 DB_PATH 被正确加载（无 CWD .env）。"""
    db = str(tmp_path / "from_user.db")
    config_dir = tmp_path / ".config" / "milb-tracker"
    config_dir.mkdir(parents=True)
    (config_dir / ".env").write_text(f"DB_PATH={db}\n")

    # cwd 中不放 .env，HOME 指向 tmp_path 以加载用户级配置
    cwd = str(tmp_path / "workspace")
    Path(cwd).mkdir()
    value = _run(_PRINT_DB_PATH, cwd=cwd, home=str(tmp_path))
    assert value == db


def test_cwd_overrides_user_config(tmp_path):
    """TC-03: 同一键存在时，CWD/.env 优先于 ~/.config/milb-tracker/.env。"""
    user_db = str(tmp_path / "user.db")
    cwd_db = str(tmp_path / "cwd.db")

    # 用户级配置
    config_dir = tmp_path / ".config" / "milb-tracker"
    config_dir.mkdir(parents=True)
    (config_dir / ".env").write_text(f"DB_PATH={user_db}\n")

    # 项目级配置（应胜出）
    cwd = str(tmp_path / "workspace")
    Path(cwd).mkdir()
    (Path(cwd) / ".env").write_text(f"DB_PATH={cwd_db}\n")

    value = _run(_PRINT_DB_PATH, cwd=cwd, home=str(tmp_path))
    assert value == cwd_db, f"期望 CWD 值 {cwd_db}，实际得到 {value}"


def test_process_env_overrides_dotenv(tmp_path):
    """TC-04: 进程环境变量优先于任何 .env 文件（最高优先级）。"""
    env_db = str(tmp_path / "env_var.db")
    dotenv_db = str(tmp_path / "dotenv.db")

    cwd = str(tmp_path / "workspace")
    Path(cwd).mkdir()
    (Path(cwd) / ".env").write_text(f"DB_PATH={dotenv_db}\n")

    # 通过 extra_env 注入进程级环境变量（不应被 .env 覆盖）
    value = _run(_PRINT_DB_PATH, cwd=cwd, extra_env={"DB_PATH": env_db})
    assert value == env_db, f"期望进程变量值 {env_db}，实际得到 {value}"


def test_default_db_path_when_no_env(tmp_path):
    """TC-05: 无任何 .env 时，DB_PATH 默认为 {CWD}/data/bids.db。"""
    cwd = str(tmp_path / "workspace")
    Path(cwd).mkdir()
    expected = str(Path(cwd) / "data" / "bids.db")

    value = _run(_PRINT_DB_PATH, cwd=cwd)
    assert value == expected


def test_comments_and_blank_lines_ignored(tmp_path):
    """TC-06: .env 文件中的注释行与空行不影响加载。"""
    db = str(tmp_path / "clean.db")
    (tmp_path / ".env").write_text(
        "# 这是注释\n"
        "\n"
        f"DB_PATH={db}\n"
        "# 另一条注释\n"
        "\n"
    )
    value = _run(_PRINT_DB_PATH, cwd=str(tmp_path))
    assert value == db


def test_attachments_dir_defaults_to_db_sibling(tmp_path):
    """TC-07: ATTACHMENTS_DIR 默认与 DB_PATH 同级，名为 attachments。"""
    db = str(tmp_path / "data" / "bids.db")
    (tmp_path / ".env").write_text(f"DB_PATH={db}\n")

    expected = str(tmp_path / "data" / "attachments")
    value = _run(_PRINT_ATTACHMENTS_DIR, cwd=str(tmp_path))
    assert value == expected


def test_attachments_dir_overridable(tmp_path):
    """TC-08: ATTACHMENTS_DIR 可通过 .env 独立配置，不依赖 DB_PATH。"""
    db = str(tmp_path / "data" / "bids.db")
    attachments = str(tmp_path / "custom_attachments")
    (tmp_path / ".env").write_text(
        f"DB_PATH={db}\n"
        f"ATTACHMENTS_DIR={attachments}\n"
    )
    value = _run(_PRINT_ATTACHMENTS_DIR, cwd=str(tmp_path))
    assert value == attachments
