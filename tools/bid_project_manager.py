"""
OpenClaw Tool 函数 - 招投标项目权限网关。

从 __context__ 获取真实用户身份，鉴权后路由到 scripts/ 下的各脚本。
所有 /bidding * 命令通过此函数入口执行。
"""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

DB_PATH = os.environ.get(
    'DB_PATH',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'bids.db')
)

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts')

DIRECTOR_ONLY = {'register', 'adduser', 'users', 'stats'}


def get_conn():
    conn = sqlite3.connect(os.path.abspath(DB_PATH), timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def get_user(conn, wecom_userid: str) -> dict | None:
    """查询用户身份，返回 dict 或 None。"""
    row = conn.execute(
        "SELECT role, name FROM users WHERE wecom_userid = ?",
        (wecom_userid,)).fetchone()
    return dict(row) if row else None


def _dispatch(action_type: str, project_data: dict, user_id: str, role: str, name: str) -> dict:
    """
    路由到业务脚本，返回子进程执行结果的 dict。
    """
    kw = project_data.get('keyword', '')
    project_id_val = project_data.get('project_id')

    cmd = None

    if action_type == 'status':
        cmd = ['python3', os.path.join(SCRIPTS_DIR, 'query_projects.py'),
               '--user-id', user_id]
        if kw:
            cmd += ['--keyword', kw]
        if project_data.get('active_only'):
            cmd.append('--active-only')

    elif action_type == 'register':
        fields = project_data.get('fields', {})
        cmd = ['python3', os.path.join(SCRIPTS_DIR, 'register_project.py'),
               '--json', json.dumps(fields, ensure_ascii=False),
               '--manager-name', project_data.get('manager_name', ''),
               '--travel-days', str(project_data.get('travel_days', 2))]
        if project_data.get('_attachment_path'):
            cmd += ['--announcement-file', project_data['_attachment_path']]

    elif action_type == 'init':
        cmd = ['python3', os.path.join(SCRIPTS_DIR, 'manage_users.py'),
               '--bootstrap',
               '--user-id', user_id,
               '--name', name]

    elif action_type == 'adduser':
        new_uid = project_data.get('user_id', '')
        new_name = project_data.get('name', '')
        new_contact = project_data.get('contact') or ''
        cmd = ['python3', os.path.join(SCRIPTS_DIR, 'manage_users.py'),
               '--add',
               '--caller-id', user_id,
               '--user-id', new_uid,
               '--name', new_name]
        if new_contact:
            cmd += ['--contact', new_contact]

    elif action_type == 'users':
        role_filter = project_data.get('role')
        cmd = ['python3', os.path.join(SCRIPTS_DIR, 'manage_users.py'), '--list']
        if role_filter:
            cmd += ['--role', role_filter]

    elif action_type in ('purchased', 'seal', 'cancel'):
        if not project_id_val:
            return {"status": "error", "message": "缺少 project_id 参数"}
        field_val = 'doc_purchased' if action_type == 'purchased' else \
                    'sealed' if action_type == 'seal' else 'cancelled'
        cmd = ['python3', os.path.join(SCRIPTS_DIR, 'update_project.py'),
               '--id', str(project_id_val),
               '--field', 'status',
               '--value', field_val]

    elif action_type == 'result':
        if not project_id_val:
            return {"status": "error", "message": "缺少 project_id 参数"}
        cmd = ['python3', os.path.join(SCRIPTS_DIR, 'record_result.py'),
               '--project-id', str(project_id_val),
               '--won', 'true' if project_data.get('is_won') else 'false']
        if project_data.get('our_price') is not None:
            cmd += ['--our-price', str(project_data['our_price'])]
        if project_data.get('winning_price') is not None:
            cmd += ['--winning-price', str(project_data['winning_price'])]
        if project_data.get('winner'):
            cmd += ['--winner', project_data['winner']]
        if project_data.get('notes'):
            cmd += ['--notes', project_data['notes']]

    elif action_type == 'stats':
        # 校验 by_manager 和 by_month 互斥
        has_by_manager = project_data.get('by_manager')
        has_by_month = project_data.get('by_month')
        if has_by_manager and has_by_month:
            return {"status": "error", "message": "by_manager 和 by_month 参数不能同时使用"}
        if not has_by_manager and not has_by_month:
            return {"status": "error", "message": "必须指定 by_manager 或 by_month 参数"}
        cmd = ['python3', os.path.join(SCRIPTS_DIR, 'stats.py')]
        if has_by_manager:
            cmd.append('--by-manager')
        if has_by_month:
            cmd.append('--by-month')
        if project_data.get('period'):
            cmd += ['--period', project_data['period']]
        if project_data.get('manager'):
            cmd += ['--manager', project_data['manager']]

    else:
        return {"status": "error", "message": f"未知操作类型：{action_type}"}

    env = os.environ.copy()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)

    if result.returncode == 0:
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            data = result.stdout.strip()
        return {"status": "ok", "message": "操作成功", "data": data}
    else:
        try:
            err = json.loads(result.stderr)
        except json.JSONDecodeError:
            err = {"error": result.stderr.strip(), "code": 1}
        return {"status": "error", "message": err.get("error", "未知错误")}


def bid_project_manager(action_type: str, project_data: dict = None, **kwargs) -> dict:
    """
    OpenClaw Tool 函数入口。

    Args:
        action_type: 操作类型，有效值见 api-interfaces.md §9
        project_data: 业务参数 dict（由 LLM 提取），不含用户身份
        **kwargs: OpenClaw 引擎隐式注入，含 __context__

    Returns:
        {"status": "ok"|"error", "message": "...", "data": {...}}
    """
    project_data = project_data or {}

    # 1. 从上下文提取 wecom_userid（防 prompt injection）
    try:
        caller_id = kwargs['__context__']['body']['from']['userid']
    except (KeyError, TypeError):
        return {"status": "error", "message": "无法识别您的企业微信身份"}

    # 2. 附件路径拦截（register 命令）
    if action_type == 'register':
        try:
            attachments = kwargs['__context__']['body'].get('attachments', [])
            if attachments:
                project_data['_attachment_path'] = attachments[0].get('local_path')
        except (KeyError, TypeError, IndexError):
            pass

    conn = get_conn()
    try:
        # 3. init 专属分支：无需检查是否已初始化
        if action_type == 'init':
            row = conn.execute(
                "SELECT role, name FROM users WHERE wecom_userid = ?",
                (caller_id,)).fetchone()
            if row:
                return {"status": "error", "message": "系统已初始化"}
            conn.close()
            return _dispatch('init', project_data, caller_id, 'director', project_data.get('name', caller_id))

        # 4. 非 init：检查系统是否已初始化（users 表有 director）
        director_row = conn.execute(
            "SELECT wecom_userid FROM users WHERE role = 'director'").fetchone()
        if not director_row:
            conn.close()
            return {"status": "error", "message": "系统尚未初始化，请先执行 /bidding init"}

        # 5. 查询当前用户角色
        user = get_user(conn, caller_id)
        conn.close()

        if not user:
            return {"status": "error", "message": "您尚未被添加为系统用户"}

        role, name = user['role'], user['name']

        # 6. 命令级权限校验
        if action_type in DIRECTOR_ONLY and role != 'director':
            return {"status": "error", "message": "仅总监可执行此操作"}

        # 7. 项目归属校验（purchased / seal / result / cancel）
        if action_type in ('purchased', 'seal', 'result', 'cancel'):
            keyword = project_data.get('keyword', '')
            project_id_val = project_data.get('project_id')
            if not project_id_val and not keyword:
                return {"status": "error", "message": "缺少项目标识（keyword 或 project_id）"}

            conn2 = get_conn()
            try:
                if project_id_val:
                    row = conn2.execute(
                        "SELECT id FROM projects WHERE id = ?", (project_id_val,)).fetchone()
                    if not row:
                        return {"status": "error", "message": f"项目 {project_id_val} 不存在"}
                elif keyword:
                    # 总监：按 keyword 查找任意项目；非总监：仅查找本人项目
                    if role == 'director':
                        row = conn2.execute(
                            "SELECT id FROM projects WHERE project_no = ? OR project_name LIKE ?",
                            (keyword, f"%{keyword}%")).fetchone()
                    else:
                        row = conn2.execute(
                            "SELECT p.id FROM projects p "
                            "JOIN users u ON u.name = p.project_manager "
                            "WHERE u.wecom_userid = ? "
                            "AND (p.project_no = ? OR p.project_name LIKE ?)",
                            (caller_id, keyword, f"%{keyword}%")).fetchone()
                    if not row:
                        return {"status": "error", "message": "项目不存在" if role == 'director' else "该项目不在您的负责范围内"}
                    project_data['project_id'] = row['id']
            finally:
                conn2.close()

        # 8. 路由到对应脚本
        return _dispatch(action_type, project_data, caller_id, role, name)

    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return {"status": "error", "message": f"执行出错：{e}"}
