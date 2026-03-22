# API 接口契约文档

> 版本：v1.0 | 日期：2026-03-22 | 关联：[technical-design.md](./technical-design.md) §5

## 全局规范

所有脚本遵循以下约定：

| 项目 | 规范 |
|------|------|
| 数据库路径 | `DB_PATH = os.environ.get('DB_PATH', os.path.join(os.path.dirname(__file__), '..', 'data', 'bids.db'))` |
| SQLite 连接 | `PRAGMA journal_mode=WAL` + `PRAGMA foreign_keys=ON`，timeout=10.0 |
| 成功退出 | exit code `0`，stdout 输出 JSON（除 init_db.py 外） |
| 失败退出 | exit code `1`，stderr 输出 `{"error": "<消息>", "code": 1}` |
| 时间格式 | ISO8601：`YYYY-MM-DDTHH:MM:SS` |

---

## 1. init_db.py

### 用途
初始化 SQLite 数据库，创建 4 张表（projects、bid_results、reminders、users），创建 `data/attachments/` 目录。幂等运行。

### 参数表

无参数。

### 调用示例

```bash
python3 scripts/init_db.py
```

### 成功输出（exit 0）

纯文本（非 JSON）：
```
数据库初始化完成：/abs/path/to/data/bids.db
```

### 失败输出（exit 1）

```json
{"error": "数据库初始化失败: <原因>", "code": 1}
```

### 副作用

- 创建 `data/bids.db`（含 4 张表）
- 创建 `data/attachments/` 目录
- 多次执行安全，不重建已有表，不丢失数据

### 修复点

`projects` 表增加列：
```sql
project_no      TEXT NOT NULL UNIQUE,   -- 人工友好编号 YYYY-NNN
travel_days     INTEGER DEFAULT 0,      -- 路途天数
```

`users` 表增加列：
```sql
wecom_userid    TEXT NOT NULL UNIQUE,   -- 企业微信 userid
created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
```

### 修复后完整 DDL

```sql
CREATE TABLE IF NOT EXISTS projects (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    project_no              TEXT NOT NULL UNIQUE,
    project_name            TEXT NOT NULL,
    budget                  REAL,
    procurer                TEXT,
    bid_agency              TEXT,
    project_manager         TEXT,
    manager_contact         TEXT,
    registration_deadline   TEXT,
    registration_location   TEXT,
    doc_purchase_location   TEXT,
    doc_purchase_price      REAL,
    doc_purchase_deadline   TEXT,
    doc_required_materials  TEXT,
    doc_purchased_at        TEXT,
    doc_attachment_path     TEXT,
    bid_opening_time        TEXT,
    bid_opening_location    TEXT,
    travel_days             INTEGER DEFAULT 0,
    suggested_seal_time     TEXT,
    actual_seal_time        TEXT,
    announcement_path       TEXT,
    status                  TEXT NOT NULL DEFAULT 'registered',
    created_at              TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS bid_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    our_bid_price   REAL,
    winning_price   REAL,
    winner          TEXT,
    is_winner       INTEGER NOT NULL DEFAULT 0,
    notes           TEXT,
    recorded_at     TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS reminders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    reminder_type   TEXT NOT NULL,
    sent_at         TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    recipient_role  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    wecom_userid    TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    role            TEXT NOT NULL,
    contact         TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
```

---

## 2. manage_users.py（新建）

### 用途
用户管理：Bootstrap 注册总监、添加项目负责人、列出用户。

### 参数表

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--bootstrap` | flag | 与 --add/--list 互斥 | - | Bootstrap 模式：注册首位总监 |
| `--add` | flag | 与 --bootstrap/--list 互斥 | - | 添加负责人模式 |
| `--list` | flag | 与 --bootstrap/--add 互斥 | - | 列出用户模式 |
| `--user-id` | TEXT | bootstrap/add 必填 | - | 企业微信 userid |
| `--name` | TEXT | bootstrap/add 必填 | - | 用户显示名称 |
| `--caller-id` | TEXT | add 必填 | - | 调用者的 wecom_userid（用于权限验证，须为总监） |
| `--contact` | TEXT | 可选 | None | 联系方式 |
| `--role` | TEXT | list 可选 | None | 按角色过滤（director/manager） |

### 调用示例

```bash
# Bootstrap 注册总监（幂等：同 userid 再次执行返回 ok）
python3 scripts/manage_users.py --bootstrap --user-id WangDirector --name "王总监"

# 添加负责人（仅总监可调用，caller-id 用于权限验证）
python3 scripts/manage_users.py --add --caller-id WangDirector --user-id ZhangManager --name "张经理" --contact "13800138000"

# 列出所有用户
python3 scripts/manage_users.py --list

# 列出指定角色
python3 scripts/manage_users.py --list --role manager
```

### 成功输出（exit 0）

**--bootstrap / --add 模式：**
```json
{"status": "ok", "message": "总监注册成功：王总监"}
```
```json
{"status": "ok", "message": "用户添加成功：张经理 (manager)"}
```

**--list 模式：**
```json
[
  {"id": 1, "wecom_userid": "WangDirector", "name": "王总监", "role": "director", "contact": null, "created_at": "2026-03-22T10:00:00"},
  {"id": 2, "wecom_userid": "ZhangManager", "name": "张经理", "role": "manager", "contact": "13800138000", "created_at": "2026-03-22T10:05:00"}
]
```

### 失败输出（exit 1）

```json
{"error": "系统已初始化，总监已存在且非当前用户", "code": 1}
```
```json
{"error": "权限不足：仅总监可添加用户", "code": 1}
```

### 副作用

- **--bootstrap**：向 `users` 表插入 role='director' 的记录
  - 幂等：同 userid 再次执行返回 `{"status": "ok", "message": "总监已存在：王总监"}`
  - 不同 userid 且已有 director 时报错 exit 1
- **--add**：向 `users` 表插入 role='manager' 的记录
  - 验证 `--caller-id` 在 users 表中 role='director'
  - userid 已存在时报错 exit 1

### Bootstrap 逻辑

```python
# 检查是否已有总监
existing = SELECT * FROM users WHERE role = 'director'
if existing:
    if existing.wecom_userid == args.user_id:
        # 幂等：返回成功
        print(json.dumps({"status": "ok", "message": f"总监已存在：{existing.name}"}))
        sys.exit(0)
    else:
        # 冲突：不同用户试图注册为总监
        print(json.dumps({"error": "系统已初始化，总监已存在且非当前用户", "code": 1}), file=sys.stderr)
        sys.exit(1)
# 无总监，注册新总监
INSERT INTO users(wecom_userid, name, role) VALUES(?, ?, 'director')
```

---

## 3. register_project.py（修复）

### 用途
注册新招投标项目，自动生成 project_no，推算建议封标时间，归档公告文件。

### 参数表

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--json` | TEXT | 是 | - | 项目信息 JSON 字符串 |
| `--manager-name` | TEXT | 是 | - | 指派的项目负责人姓名（**新增**） |
| `--travel-days` | INT | 否 | 2 | 路途天数（用于推算封标时间） |
| `--announcement-file` | TEXT | 否 | None | 公告原件文件路径 |

### 调用示例

```bash
python3 scripts/register_project.py \
  --json '{"project_name": "XXX系统采购", "budget": 1500000, "bid_opening_time": "2026-04-10T14:00:00"}' \
  --manager-name "张经理" \
  --travel-days 1 \
  --announcement-file /tmp/announcement.pdf
```

### 成功输出（exit 0）

```json
{
  "project_id": 42,
  "project_no": "2026-003",
  "project_name": "XXX系统采购",
  "suggested_seal_time": "2026-04-08T14:00:00",
  "attachment_dir": "data/attachments/42"
}
```

### 失败输出（exit 1）

```json
{"error": "JSON 解析失败：Expecting value: line 1 column 1 (char 0)", "code": 1}
```
```json
{"error": "--manager-name 为必填参数", "code": 1}
```

### 副作用

- 向 `projects` 表插入一条记录（含自动生成的 `project_no`）
- `project_manager` 字段设为 `--manager-name` 的值
- `travel_days` 字段设为 `--travel-days` 的值
- 若提供 `--announcement-file`：创建 `data/attachments/{project_id}/` 目录，移动文件

### project_no 生成算法

```python
import datetime

year = datetime.datetime.now().year  # 当前年份

# 查询当年已有的最大序号
cur = conn.execute(
    "SELECT MAX(CAST(SUBSTR(project_no, 6) AS INTEGER)) FROM projects WHERE project_no LIKE ?",
    (f"{year}-%",)
)
max_seq = cur.fetchone()[0]

if max_seq is None:
    seq = 1          # 当年第一个项目
else:
    seq = max_seq + 1

project_no = f"{year}-{seq:03d}"  # 如 "2026-001"
```

### 修复清单

1. 增加 `--manager-name` 必填参数
2. 将 `--manager-name` 写入 `project_manager` 字段
3. 增加 `project_no` 自动生成逻辑
4. 将 `travel_days` 写入 `projects.travel_days` 列
5. 输出改为 JSON 格式（含 project_id、project_no、project_name、suggested_seal_time、attachment_dir）

---

## 4. query_projects.py（修复接口）

### 用途
查询项目列表或详情，按用户角色自动过滤，支持关键词搜索。

### 参数表

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--user-id` | TEXT | 否 | None | 当前用户 wecom_userid（从 users 表查角色，**替换原 --role/--name**） |
| `--keyword` | TEXT | 否 | None | 搜索关键词：先精确匹配 project_no，再 LIKE 匹配 project_name（**新增**） |
| `--id` | INT | 否 | None | 查询指定项目详情（保留） |
| `--status` | TEXT | 否 | None | 按状态过滤（保留） |
| `--active-only` | flag | 否 | False | 仅返回活跃项目（**新增**） |
| `--upcoming-days` | INT | 否 | None | 返回 N 天内有关键节点的项目（保留） |

### 调用示例

```bash
# 总监查看所有活跃项目
python3 scripts/query_projects.py --user-id WangDirector --active-only

# 负责人查看本人项目
python3 scripts/query_projects.py --user-id ZhangManager --active-only

# 按 project_no 精确查询
python3 scripts/query_projects.py --user-id WangDirector --keyword "2026-001"

# 按项目名模糊搜索
python3 scripts/query_projects.py --user-id ZhangManager --keyword "网安"

# 按 ID 查详情
python3 scripts/query_projects.py --id 1

# 7 天内有关键节点的项目
python3 scripts/query_projects.py --user-id WangDirector --upcoming-days 7
```

### 成功输出（exit 0）

```json
[
  {
    "id": 1,
    "project_no": "2026-001",
    "project_name": "XXX系统采购项目",
    "budget": 1500000,
    "status": "registered",
    "project_manager": "张经理",
    "bid_opening_time": "2026-04-10T14:00:00",
    ...
  }
]
```

`--id` 模式返回单个 dict 或 null。

### 失败输出（exit 1）

```json
{"error": "用户不存在", "code": 1}
```

### 副作用

无（只读操作）。

### 参数优先级

1. `--id` 存在时：直接按 ID 查单个项目，忽略其他参数
2. `--user-id` 存在时：从 users 表解析角色，按角色过滤项目
3. `--user-id` 为 None（未传）时：**不报错，不做角色过滤**，返回全部项目（等同 director 视角），向后兼容

### --user-id 解析逻辑

```python
# 1. 根据 wecom_userid 查询用户角色和姓名
row = conn.execute(
    "SELECT role, name FROM users WHERE wecom_userid = ?",
    (user_id,)
).fetchone()

if row is None:
    # 用户不存在
    print(json.dumps({"error": "用户不存在", "code": 1}), file=sys.stderr)
    sys.exit(1)

role, name = row

# 2. 角色过滤
if role == 'manager':
    # manager 仅看本人项目：追加 WHERE project_manager = name
    sql += " AND project_manager = ?"
    params.append(name)
elif role == 'director':
    # director 无过滤，查看全部
    pass
```

### --keyword 搜索逻辑

```python
if keyword:
    # 先精确匹配 project_no
    row = conn.execute("SELECT * FROM projects WHERE project_no = ?", (keyword,)).fetchone()
    if row:
        return [dict(zip(cols, row))]
    # 再模糊匹配 project_name
    sql += " AND project_name LIKE ?"
    params.append(f"%{keyword}%")
```

### 修复清单

1. 删除 `--role` 和 `--name` 参数
2. 增加 `--user-id` 参数（从 users 表解析角色和姓名）
3. 增加 `--keyword` 参数（先精确 project_no 再模糊 project_name）
4. 增加 `--active-only` flag
5. 输出包含 `project_no` 字段

---

## 5. update_project.py（修复）

### 用途
更新项目字段，含状态机合法性验证。

### 参数表

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--id` | INT | 是 | - | 项目 ID |
| `--field` | TEXT | 是 | - | 要更新的字段名 |
| `--value` | TEXT | 是 | - | 新值 |

### 调用示例

```bash
python3 scripts/update_project.py --id 1 --field status --value doc_purchased
python3 scripts/update_project.py --id 1 --field actual_seal_time --value "2026-04-08T15:00:00"
```

### 成功输出（exit 0）

```json
{"status": "ok", "message": "项目 1 的 status 已更新为：doc_purchased"}
```

### 失败输出（exit 1）

```json
{"error": "非法状态流转：registered → sealed", "code": 1}
```
```json
{"error": "项目不存在：999", "code": 1}
```
```json
{"error": "不支持更新字段：id", "code": 1}
```

### 副作用

- 更新 `projects` 表指定字段
- 自动更新 `updated_at` 为当前时间

### 修复点

**VALID_TRANSITIONS 增加 `sealed → opened`：**

```python
VALID_TRANSITIONS = {
    'registered':    {'doc_pending', 'doc_purchased', 'cancelled'},
    'doc_pending':   {'doc_purchased', 'cancelled'},
    'doc_purchased': {'preparing', 'sealed', 'cancelled'},
    'preparing':     {'sealed', 'cancelled'},
    'sealed':        {'opened', 'cancelled'},        # 修复：增加 opened
    'opened':        {'won', 'lost'},
    'won':           set(),
    'lost':          set(),
    'cancelled':     set(),
}
```

注意变更点：
- `registered` 增加直接到 `doc_purchased`（跳过 doc_pending）
- `doc_purchased` 增加直接到 `sealed`（跳过 preparing）
- `sealed` 增加到 `opened`（**原缺失**）
- 所有非终态增加到 `cancelled`

**UPDATABLE_FIELDS 白名单确认完整：**

```python
UPDATABLE_FIELDS = {
    'status', 'doc_purchased_at', 'doc_attachment_path',
    'actual_seal_time', 'project_manager', 'manager_contact',
    'bid_opening_time', 'bid_opening_location', 'suggested_seal_time',
    'announcement_path',
}
```

### 修复清单

1. `VALID_TRANSITIONS['sealed']` 增加 `'opened'`
2. `VALID_TRANSITIONS['registered']` 增加 `'doc_purchased'`
3. `VALID_TRANSITIONS['doc_purchased']` 增加 `'sealed'`
4. 输出改为 JSON 格式
5. 错误输出改为 JSON 格式到 stderr

---

## 6. record_result.py（验证通过）

### 用途
录入开标结果，同步更新项目状态为 won 或 lost。

### 参数表

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--project-id` | INT | 是 | - | 项目 ID |
| `--our-price` | FLOAT | 否 | None | 我方报价（元） |
| `--winning-price` | FLOAT | 否 | None | 中标价格（元） |
| `--winner` | TEXT | 否 | None | 中标单位名称 |
| `--won` | TEXT | 是 | - | 是否中标（true/false） |
| `--notes` | TEXT | 否 | None | 备注 |

### 调用示例

```bash
python3 scripts/record_result.py \
  --project-id 1 \
  --our-price 980000 \
  --winning-price 950000 \
  --winner "某某公司" \
  --won false \
  --notes "排名第二，差距3万"
```

### 成功输出（exit 0）

```json
{"status": "ok", "message": "项目 1 开标结果已录入：未中标", "new_status": "lost"}
```

### 失败输出（exit 1）

```json
{"error": "项目当前状态 'registered' 不允许录入结果，需先将状态更新为 opened", "code": 1}
```
```json
{"error": "项目不存在：999", "code": 1}
```

### 副作用

- 向 `bid_results` 表插入一条记录
- 更新 `projects.status` 为 `won` 或 `lost`
- 更新 `projects.updated_at`

### 验证确认

- 合法来源状态：`sealed` 或 `opened`（当前代码已正确实现 `row[0] not in ('opened', 'sealed')`）
- `is_winner` 正确存储为 0/1

### 修复清单

1. 输出改为 JSON 格式
2. 错误输出改为 JSON 格式到 stderr

---

## 7. reminder_check.py（修复去重）

### 用途
扫描所有活跃项目，判断是否需要发送提醒，输出 JSON 数组。由 Cron 每日调用两次。

### 参数表

无参数。

### 调用示例

```bash
python3 scripts/reminder_check.py
```

### 成功输出（exit 0）

```json
[
  {
    "project_id": 5,
    "project_name": "XXX系统采购项目",
    "reminder_type": "doc_purchase",
    "recipient_role": "manager",
    "project_manager": "张经理",
    "message": "【标书购买提醒】XXX系统采购项目 购买截止 2026-04-01，请尽快办理"
  }
]
```

空数组表示无需提醒：
```json
[]
```

### 失败输出（exit 1）

```json
{"error": "数据库连接失败: <原因>", "code": 1}
```

### 副作用

- 读取 `projects` 表中活跃项目
- 读取 `reminders` 表检查今日是否已发送（**新增**）
- 写入 `reminders` 表记录已发送提醒（**新增**）

### 提醒规则

| 提醒类型 | 触发条件 | 接收角色 |
|---------|---------|---------|
| `doc_purchase` | 状态为 registered/doc_pending，距购买截止 <= 3 天 | manager |
| `seal_warning` | 状态为 registered/doc_pending/doc_purchased/preparing，距建议封标 <= 2 天 | manager |
| `bid_opening` | 距开标 <= 1 天 | manager + director |

### 去重逻辑（修复点）

**去重键：`(project_id, reminder_type, DATE)`** — recipient_role 不参与去重判断，仅用于记录。

```python
def is_already_sent(conn, project_id: int, reminder_type: str) -> bool:
    """检查今日是否已发送同类型提醒。去重键为 (project_id, reminder_type, DATE)。"""
    cur = conn.execute(
        "SELECT COUNT(*) FROM reminders "
        "WHERE project_id = ? AND reminder_type = ? "
        "AND DATE(sent_at) = DATE('now', 'localtime')",
        (project_id, reminder_type)
    )
    return cur.fetchone()[0] > 0


def record_sent(conn, project_id: int, reminder_type: str, recipient_role: str):
    """记录已发送的提醒。recipient_role 仅记录用途，不参与去重。"""
    conn.execute(
        "INSERT INTO reminders (project_id, reminder_type, recipient_role) "
        "VALUES (?, ?, ?)",
        (project_id, reminder_type, recipient_role)
    )
```

**在 check_reminders() 中的使用流程：**

```python
conn = get_conn()
# ... 查询活跃项目 ...

for p in projects:
    # 规则 1: 标书购买
    if should_remind_purchase(p):
        if not is_already_sent(conn, pid, 'doc_purchase'):
            reminders.append({...})
            record_sent(conn, pid, 'doc_purchase', 'manager')

    # 规则 2: 封标
    if should_remind_seal(p):
        if not is_already_sent(conn, pid, 'seal_warning'):
            reminders.append({...})
            record_sent(conn, pid, 'seal_warning', 'manager')

    # 规则 3: 开标
    if should_remind_opening(p):
        if not is_already_sent(conn, pid, 'bid_opening'):
            for role in ('manager', 'director'):
                reminders.append({...})
            record_sent(conn, pid, 'bid_opening', 'manager')
            # 注意：只写入一条 reminders 记录，第二次运行时 manager 和 director 都不再收到

conn.commit()
conn.close()
```

### 修复清单

1. 在生成每条提醒前检查 `reminders` 表：同日同项目同类型是否已发送
2. 输出提醒后写入 `reminders` 表
3. 确保 conn 在函数内保持打开直到 commit（用于读写 reminders 表）

---

## 8. stats.py（实现 stub）

### 用途
统计招投标项目表现，支持全局/按负责人/按月度三种模式。

### 参数表

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--by-manager` | flag | 否 | False | 按负责人分组统计 |
| `--by-month` | flag | 否 | False | 按月度趋势统计 |
| `--period` | TEXT | 否 | None | 时间过滤：`YYYY-MM` 或 `YYYY-QN`（如 2026-Q1） |
| `--manager` | TEXT | 否 | None | 指定负责人姓名过滤 |

### 调用示例

```bash
# 全局统计
python3 scripts/stats.py

# 指定季度
python3 scripts/stats.py --period 2026-Q1

# 按负责人分组
python3 scripts/stats.py --by-manager

# 按月度趋势
python3 scripts/stats.py --by-month

# 指定负责人 + 月份
python3 scripts/stats.py --period 2026-03 --manager 张经理
```

### 成功输出（exit 0）

**全局统计（默认模式）：**
```json
{
  "total": 25,
  "won": 10,
  "lost": 12,
  "active": 3,
  "win_rate": 0.45,
  "avg_budget": 1200000,
  "avg_price_diff": -30000
}
```

- `win_rate` = won / (won + lost)，仅计算已有结果的项目；**分母为 0 时 win_rate = 0**（不是 null）
- `avg_budget` 和 `avg_price_diff`：SQL AVG 在无行时返回 NULL，JSON 中输出为 `null`
- `avg_price_diff` = AVG(our_bid_price - winning_price)，反映报价偏差

**空数据库时 stats_global 返回：**
```json
{"total": 0, "won": 0, "lost": 0, "active": 0, "win_rate": 0, "avg_budget": null, "avg_price_diff": null}
```

**空数据库时 --by-manager / --by-month 返回：** `[]`（空数组）

**按负责人分组（--by-manager）：**
```json
[
  {
    "manager": "王经理",
    "total": 10,
    "won": 5,
    "lost": 4,
    "active": 1,
    "win_rate": 0.56
  },
  {
    "manager": "张经理",
    "total": 8,
    "won": 3,
    "lost": 5,
    "active": 0,
    "win_rate": 0.38
  }
]
```

**按月度趋势（--by-month）：**
```json
[
  {"month": "2026-01", "total": 5, "won": 2, "lost": 3, "win_rate": 0.40},
  {"month": "2026-02", "total": 8, "won": 4, "lost": 3, "win_rate": 0.57},
  {"month": "2026-03", "total": 12, "won": 4, "lost": 6, "win_rate": 0.40}
]
```

### 失败输出（exit 1）

```json
{"error": "无效的 period 格式，支持 YYYY-MM 或 YYYY-QN", "code": 1}
```

### 副作用

无（只读操作）。

### 核心 SQL

**所有查询的基础 JOIN：**
```sql
FROM projects p LEFT JOIN bid_results r ON r.project_id = p.id
```

**period 过滤逻辑：**
```python
def parse_period(period: str) -> tuple[str, str]:
    """将 period 转为日期范围。"""
    if re.match(r'^\d{4}-Q[1-4]$', period):
        year = int(period[:4])
        quarter = int(period[-1])
        start_month = (quarter - 1) * 3 + 1
        start = f"{year}-{start_month:02d}-01"
        end_month = start_month + 2
        # 季度末日
        if end_month in (1, 3, 5, 7, 8, 10, 12):
            end = f"{year}-{end_month:02d}-31"
        elif end_month in (4, 6, 9, 11):
            end = f"{year}-{end_month:02d}-30"
        else:  # 2月
            end = f"{year}-{end_month:02d}-28"  # 简化处理
        return start, end
    elif re.match(r'^\d{4}-\d{2}$', period):
        start = f"{period}-01"
        # 月末：下月1日
        year, month = int(period[:4]), int(period[5:7])
        if month == 12:
            end = f"{year+1}-01-01"
        else:
            end = f"{year}-{month+1:02d}-01"
        return start, end
    else:
        raise ValueError("无效的 period 格式")

# 在 SQL 中使用：
# WHERE p.bid_opening_time >= ? AND p.bid_opening_time < ?
```

**stats_global 实现：**
```sql
SELECT
    COUNT(DISTINCT p.id) AS total,
    COUNT(DISTINCT CASE WHEN r.is_winner = 1 THEN p.id END) AS won,
    COUNT(DISTINCT CASE WHEN r.is_winner = 0 THEN p.id END) AS lost,
    COUNT(DISTINCT CASE WHEN p.status NOT IN ('won', 'lost', 'cancelled') THEN p.id END) AS active,
    AVG(p.budget) AS avg_budget,
    AVG(r.our_bid_price - r.winning_price) AS avg_price_diff
FROM projects p
LEFT JOIN bid_results r ON r.project_id = p.id
[WHERE p.bid_opening_time BETWEEN ? AND ?]  -- 若指定 period
```

**stats_by_manager 实现：**
```sql
SELECT
    p.project_manager AS manager,
    COUNT(DISTINCT p.id) AS total,
    COUNT(DISTINCT CASE WHEN r.is_winner = 1 THEN p.id END) AS won,
    COUNT(DISTINCT CASE WHEN r.is_winner = 0 THEN p.id END) AS lost,
    COUNT(DISTINCT CASE WHEN p.status NOT IN ('won', 'lost', 'cancelled') THEN p.id END) AS active
FROM projects p
LEFT JOIN bid_results r ON r.project_id = p.id
[WHERE p.bid_opening_time BETWEEN ? AND ?]
GROUP BY p.project_manager
ORDER BY won DESC
```

**stats_by_month 实现：**
```sql
SELECT
    STRFTIME('%Y-%m', p.bid_opening_time) AS month,
    COUNT(DISTINCT p.id) AS total,
    COUNT(DISTINCT CASE WHEN r.is_winner = 1 THEN p.id END) AS won,
    COUNT(DISTINCT CASE WHEN r.is_winner = 0 THEN p.id END) AS lost
FROM projects p
LEFT JOIN bid_results r ON r.project_id = p.id
WHERE p.bid_opening_time IS NOT NULL
[AND p.bid_opening_time >= ? AND p.bid_opening_time < ?]  -- 若指定 period
GROUP BY month
ORDER BY month ASC
```

### 实现清单

1. 实现 `stats_global(period)` — 返回 dict
2. 实现 `stats_by_manager(period)` — 返回 list[dict]
3. 实现 `stats_by_month(period)` — 返回 list[dict]（**函数签名增加 period 参数**）
4. 实现 `parse_period(period)` — 解析 YYYY-MM / YYYY-QN 为日期范围
5. win_rate 计算：`won / (won + lost)` 若分母为 0 则 win_rate = 0
6. 增加 `get_conn()` 函数
7. main() 中将 `args.period` 传给 `stats_by_month(args.period)`

---

## 9. tools/bid_project_manager.py（新建）

### 用途
OpenClaw Tool 函数入口。接收 LLM 提取的业务参数，从 `__context__` 获取真实 WeCom userid 完成鉴权，路由到对应脚本。

### 函数签名

```python
def bid_project_manager(action_type: str, project_data: dict, **kwargs) -> dict:
    """
    OpenClaw Tool 函数入口。

    Args:
        action_type: 操作类型，有效值见下表
        project_data: 业务参数 dict（由 LLM 提取）
        **kwargs: OpenClaw 引擎隐式注入，含 __context__

    Returns:
        {"status": "ok"|"error", "message": "...", "data": {...}}
    """
```

### 有效 action_type

| action_type | 对应脚本 | 权限要求 |
|-------------|---------|---------|
| `init` | manage_users.py --bootstrap | 未初始化时任何人 |
| `status` | query_projects.py | 所有已注册用户 |
| `register` | register_project.py | 仅总监 |
| `adduser` | manage_users.py --add | 仅总监 |
| `users` | manage_users.py --list | 仅总监 |
| `purchased` | update_project.py (status=doc_purchased) | 项目负责人（本人项目） |
| `seal` | update_project.py (status=sealed) | 项目负责人（本人项目） |
| `result` | record_result.py | 负责人/总监 |
| `cancel` | update_project.py (status=cancelled) | 负责人/总监 |
| `stats` | stats.py | 仅总监 |

### 返回格式

**成功：**
```json
{"status": "ok", "message": "项目注册成功", "data": {"project_id": 42, "project_no": "2026-003"}}
```

**失败：**
```json
{"status": "error", "message": "仅总监可执行此操作"}
```

### 鉴权流程

```
1. 从 kwargs['__context__']['body']['from']['userid'] 提取 wecom_userid
   → 无法提取：返回 error "无法识别您的企业微信身份"

2. 附件路径拦截（register / purchased 命令）
   file_path = context['body']['attachments'][0]['local_path']
   → 注入到 project_data['_attachment_path']

3. action_type == 'init' 时的专属分支
   → users 表无 director：注册为总监，返回 ok
   → users 表有 director：返回 error "系统已初始化"

4. 非 init 命令：检查系统是否已初始化
   → users 表无 director：返回 error "系统尚未初始化，请先执行 /bidding init"

5. 查询当前用户角色
   SELECT role, name FROM users WHERE wecom_userid = ?
   → 不存在：返回 error "您尚未被添加为系统用户"

6. 命令级权限校验
   director_only = {'register', 'adduser', 'users', 'stats'}
   → role != 'director' 且 action_type in director_only：返回 error "仅总监可执行此操作"

7. 项目归属校验（purchased / seal / result / cancel）
   SELECT p.* FROM projects p
   JOIN users u ON u.name = p.project_manager
   WHERE u.wecom_userid = :wecom_userid
     AND (p.project_no = :keyword OR p.project_name LIKE '%' || :keyword || '%')
   → 无匹配：返回 error "该项目不在您的负责范围内"
   → 总监跳过此检查（可操作任何项目）

8. 路由到 _dispatch()，通过 subprocess 调用对应脚本
```

### 内部实现要点

```python
import subprocess, json, os

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'scripts')

def _dispatch(action_type, project_data, user_id, role, name):
    """路由到业务脚本。"""
    if action_type == 'status':
        cmd = ['python3', os.path.join(SCRIPTS_DIR, 'query_projects.py'),
               '--user-id', user_id]
        keyword = project_data.get('keyword')
        if keyword:
            cmd += ['--keyword', keyword]
        if project_data.get('active_only'):
            cmd.append('--active-only')

    elif action_type == 'register':
        cmd = ['python3', os.path.join(SCRIPTS_DIR, 'register_project.py'),
               '--json', json.dumps(project_data.get('fields', {}), ensure_ascii=False),
               '--manager-name', project_data.get('manager_name', ''),
               '--travel-days', str(project_data.get('travel_days', 2))]
        if project_data.get('_attachment_path'):
            cmd += ['--announcement-file', project_data['_attachment_path']]

    # ... 其他 action_type 类似路由 ...

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
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
```

### 副作用

- 通过 subprocess 调用 scripts/ 下的脚本，间接产生 DB 写入、文件操作等副作用
- 本身不直接操作数据库（鉴权查询除外）

---

## 附录：DB_PATH 环境变量

所有脚本和 Tool 函数统一使用以下方式获取数据库路径：

```python
DB_PATH = os.environ.get('DB_PATH', os.path.join(os.path.dirname(__file__), '..', 'data', 'bids.db'))
```

测试时可通过环境变量指定测试数据库：
```bash
DB_PATH=/tmp/test.db python3 scripts/init_db.py
DB_PATH=/tmp/test.db python3 -m pytest tests/
```
