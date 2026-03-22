# 斜杠命令路由规划文档

> 版本：v1.0 | 日期：2026-03-22 | 关联：[SKILL.md](../SKILL.md)、[api-interfaces.md](./api-interfaces.md)、[technical-design.md](./technical-design.md)

---

## 1. 命令树

```
/bidding
├── [空]                     → help
├── help                    → help
├── init                    → init
├── register                → register
├── status                  → status
├── purchased               → purchased
├── seal                    → seal
├── result                  → result
├── cancel                  → cancel
├── users                   → users
├── adduser                 → adduser
└── stats                   → stats
```

### 1.1 命令 → action_type 映射表

| 斜杠命令   | action_type  | 对应脚本                | 路由条件                                |
|-----------|-------------|-----------------------|---------------------------------------|
| `/bidding`（空）| `help`      | 无（直接输出）           | 用户发送 `/bidding` 或意图不明确时询问        |
| `/bidding help` | `help`      | 无（直接输出）           | 显式触发帮助                            |
| `/bidding init` | `init`      | manage_users.py       | 首次使用、注册总监                         |
| `/bidding register` | `register`  | register_project.py   | 上传公告文件、注册新项目                    |
| `/bidding status` | `status`    | query_projects.py     | 查询项目列表/详情                         |
| `/bidding purchased` | `purchased` | update_project.py      | 确认标书已购买（状态 → doc_purchased）        |
| `/bidding seal` | `seal`       | update_project.py      | 确认已封标（状态 → sealed）                 |
| `/bidding result` | `result`   | record_result.py      | 录入开标结果（状态 → won/lost）            |
| `/bidding cancel` | `cancel`    | update_project.py      | 取消项目（状态 → cancelled）               |
| `/bidding users` | `users`      | manage_users.py        | 列出团队成员                             |
| `/bidding adduser` | `adduser`   | manage_users.py        | 添加项目负责人                            |
| `/bidding stats` | `stats`      | stats.py              | 统计分析                                |

### 1.2 LLM 参数提取规则

| action_type | LLM 提取参数                                    | 注入方式                    |
|------------|----------------------------------------------|---------------------------|
| `init`     | `name`（显示名称）                               | `project_data['name']`          |
| `register` | `fields{}`、`manager_name`、`travel_days`        | `project_data['fields']` 等     |
| `status`   | `keyword`、`active_only`                         | `project_data['keyword']` 等    |
| `purchased`| `keyword`                                        | `project_data['keyword']`       |
| `seal`     | `keyword`                                        | `project_data['keyword']`       |
| `result`   | `keyword`、`is_won`、`our_price`、`winning_price`、`winner`、`notes` | 全部在 `project_data` 中 |
| `cancel`   | `keyword`                                        | `project_data['keyword']`       |
| `users`    | `role`（可选过滤）                                 | `project_data['role']`          |
| `adduser`  | `user_id`、`name`、`contact`                       | 全部在 `project_data` 中       |
| `stats`    | `by_manager`、`by_month`、`period`、`manager`        | 全部在 `project_data` 中       |

> **注意**：`userid` 永不从 LLM 参数中获取，由 Tool 层从 `__context__` 自动注入。

---

## 2. 权限矩阵

### 2.1 角色定义

| 角色      | 英文标识   | 说明                         |
|---------|---------|----------------------------|
| 总监     | `director` | 系统管理员，可操作所有项目，可管理用户     |
| 负责人   | `manager`  | 项目负责人，仅可操作本人负责的项目       |

### 2.2 命令权限表

| action_type  | director | manager | 系统未初始化 |
|-------------|----------|---------|-----------|
| `help`      | ✓        | ✓       | ✓         |
| `init`      | ✓（幂等）  | ✓（幂等）  | ✓（唯一注册入口） |
| `status`    | ✓（全部）  | ✓（本人）  | ✗         |
| `register`  | ✓        | ✗       | ✗         |
| `purchased` | ✓（任意）  | ✓（本人）  | ✗         |
| `seal`      | ✓（任意）  | ✓（本人）  | ✗         |
| `result`    | ✓（任意）  | ✓（本人）  | ✗         |
| `cancel`    | ✓（任意）  | ✓（本人）  | ✗         |
| `users`     | ✓        | ✗       | ✗         |
| `adduser`   | ✓        | ✗       | ✗         |
| `stats`     | ✓        | ✗       | ✗         |

### 2.3 Tool 层权限校验点（bid_project_manager.py）

```
校验顺序（按代码执行顺序）：
  1. [init 专属] users 表无 director → 允许注册
  2. [init 专属] users 表有 director → 拒绝
  3. [非 init] users 表无 director → 拒绝"系统尚未初始化"
  4. [非 init] 用户不在 users 表 → 拒绝"您尚未被添加为系统用户"
  5. action_type in DIRECTOR_ONLY {'register','adduser','users','stats'} && role != director → 拒绝"仅总监可执行此操作"
  6. [purchased/seal/result/cancel] 用户为 manager 且非本人项目 → 拒绝"该项目不在您的负责范围内"
```

---

## 3. 状态机校验规则

### 3.1 状态定义

| 状态标识       | 中文含义   | 性质    |
|-------------|---------|--------|
| `registered` | 已登记    | 非终态   |
| `doc_pending` | 提醒已发   | 非终态   |
| `doc_purchased` | 标书已购  | 非终态   |
| `preparing` | 制作标书中  | 非终态   |
| `sealed`    | 已封标    | 非终态   |
| `opened`    | 已开标    | 非终态   |
| `won`       | 中标     | 终态    |
| `lost`      | 未中标    | 终态    |
| `cancelled` | 已取消    | 终态    |

### 3.2 合法状态流转

```
registered ──→ doc_pending ──→ doc_purchased ──→ preparing ──→ sealed ──→ opened ──→ won
    │               │                 │                │              │            │
    └──→ cancelled ─┴──────→ cancelled ─┴──────→ cancelled ─┘            ↓         → lost
                                                           └──→ cancelled
```

### 3.3 命令与状态转换对照

| 命令       | action_type  | 目标状态     | 必需前置状态                          | 说明                    |
|---------|-------------|-----------|-----------------------------------|-----------------------|
| `/bidding register` | `register`  | `registered` | 无（新建项目）                          | 初始状态由脚本自动设为 registered |
| `/bidding purchased` | `purchased` | `doc_purchased` | `registered` / `doc_pending`          | 标书购买确认                |
| `/bidding seal` | `seal`      | `sealed`   | `preparing` / `doc_purchased`           | 封标确认（SKILL.md 说 preparing，api-interfaces.md 增加 doc_purchased 直达 sealed） |
| `/bidding result` | `result`    | `won`/`lost` | `sealed` / `opened`                    | 开标结果录入              |
| `/bidding cancel` | `cancel`    | `cancelled` | 任意非终态（`registered`/`doc_pending`/`doc_purchased`/`preparing`/`sealed`/`opened`） | 取消项目（opened 之后仍可取消）    |

### 3.4 状态校验执行位置

```
update_project.py（update_project.py:57-59）
  └── validate_status_transition(current, new)
        └── VALID_TRANSITIONS[current] 中是否包含 new

record_result.py（record_result.py）
  └── 检查 status 必须为 'opened' 或 'sealed'
```

### 3.5 VALID_TRANSITIONS 完整定义

```python
VALID_TRANSITIONS = {
    'registered':    {'doc_pending', 'doc_purchased', 'cancelled'},
    'doc_pending':   {'doc_purchased', 'cancelled'},
    'doc_purchased': {'preparing', 'sealed', 'cancelled'},   # 可直达 sealed（跳过 preparing）
    'preparing':     {'sealed', 'cancelled'},
    'sealed':        {'opened', 'cancelled'},
    'opened':        {'won', 'lost'},
    'won':           set(),      # 终态
    'lost':          set(),      # 终态
    'cancelled':     set(),      # 终态
}
```

---

## 4. 错误码对照表

### 4.1 Tool 层错误（bid_project_manager.py 返回）

| 错误消息（原文）                                   | 错误类型    | 触发场景                                      |
|---------------------------------------------|---------|-------------------------------------------|
| `无法识别您的企业微信身份`                          | 身份识别错误  | `__context__` 中无 `body.from.userid`          |
| `系统已初始化`                                  | 初始化冲突   | init 时 users 表已有 director                    |
| `系统尚未初始化，请先执行 /bidding init`              | 前置条件不满足 | 非 init 命令执行但无 director                    |
| `您尚未被添加为系统用户`                            | 身份未注册   | 用户不在 users 表                                |
| `仅总监可执行此操作`                               | 权限不足    | manager 执行 director_only 命令                 |
| `缺少 project_id 参数`                          | 参数缺失    | purchased/seal/cancel 缺少 project_id 且无 keyword |
| `缺少项目标识（keyword 或 project_id）`               | 参数缺失    | purchased/seal/result/cancel 缺少 project_id 且无 keyword |
| `项目 {id} 不存在`                              | 数据不存在   | 指定 project_id 在 projects 表无记录              |
| `该项目不在您的负责范围内`                           | 权限不足    | manager 用 keyword 查非本人项目                    |
| `执行出错：{e}`                                 | 内部错误    | 任意未捕获异常                                   |

### 4.2 脚本层错误（子进程 stderr 输出）

| 错误消息模式                                    | 错误来源脚本        | 错误代码 | 说明                            |
|---------------------------------------------|----------------|------|-------------------------------|
| `系统已初始化，总监已存在且非当前用户`                   | manage_users.py  | 1    | init 时已有其他 director                  |
| `权限不足：仅总监可添加用户`                           | manage_users.py  | 1    | adduser 时调用者非 director              |
| `JSON 解析失败：...`                            | register_project.py | 1    | --json 参数格式错误                    |
| `--manager-name 为必填参数`                      | register_project.py | 1    | 缺少 manager-name                     |
| `非法状态流转：{from} → {to}`                    | update_project.py | 1    | 状态机校验失败                         |
| `不支持更新字段：{field}`                        | update_project.py | 1    | 字段不在 UPDATABLE_FIELDS 白名单         |
| `项目不存在：{id}`                              | update_project.py | 1    | 项目 ID 不存在                         |
| `项目当前状态 '{s}' 不允许录入结果，需先将状态更新为 opened` | record_result.py | 1    | result 前置状态不满足                    |
| `项目不存在：{id}`                              | record_result.py | 1    | result 项目 ID 不存在                   |
| `无效的 period 格式，支持 YYYY-MM 或 YYYY-QN`      | stats.py         | 1    | period 参数格式错误                     |
| `用户不存在`                                    | query_projects.py | 1    | --user-id 不在 users 表                |
| `未知错误`                                      | 任意脚本          | 1    | 子进程返回非零且无法解析 stderr 时兜底            |

### 4.3 HTTP 状态码约定（API 层参考）

| HTTP 状态码 | 含义              | 使用场景                        |
|-----------|-----------------|-------------------------------|
| 200       | OK              | 正常执行成功                        |
| 400       | Bad Request     | 参数缺失、格式错误                      |
| 401       | Unauthorized    | 无法识别身份 / 用户未注册                 |
| 403       | Forbidden       | 权限不足（总监专属 / 非本人项目）             |
| 404       | Not Found       | 项目不存在 / 命令不存在                 |
| 409       | Conflict        | 状态流转冲突 / 系统已初始化                |
| 500       | Internal Error  | 子进程异常 / 数据库错误                  |

---

## 5. 鉴权流程全图

```
用户消息
  │
  ▼
┌─────────────────────────────┐
│ bid_project_manager 入口      │
│ 提取 wecom_userid ← __context__ │
└──────────────┬──────────────┘
               │
    ┌──────────┴──────────┐
    │ action_type == 'init'? │
    ├────Yes────┬────No────┤
    │检查users表  │检查users表  │
    │有director? │有director? │
    ├─Yes→拒绝  ├─No→拒绝   │
    │          │          │
    │          │查询用户角色  │
    │          │不在表→拒绝  │
    │          │          │
    │          │DIRECTOR_ONLY?│
    │          ├─Yes→role!=dir?→拒绝│
    │          │          │
    │          │keyword查找项目?  │
    │          │manager查本人?  │
    │          │非本人→拒绝      │
    │          │          │
    │          │_dispatch()   │
    └──────────┴──────────────┘
```

---

## 6. 定时任务（Cron）路由

| 脚本              | 调度时间             | 路由 action | 接收人   | 说明         |
|-----------------|------------------|-----------|--------|------------|
| reminder_check.py | 工作日 08:47 / 17:53 | 无（独立脚本） | manager / director | 自动扫描并推送提醒 |
