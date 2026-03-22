---
name: military-bidding-tracker
description: 军事招投标商机全周期追踪助手。以 /bidding 为唯一命令前缀驱动。
  有效命令：/bidding（帮助） /bidding init / bidding register / bidding adduser / bidding users / bidding purchased / bidding seal / bidding result / bidding cancel / bidding stats。
  关键词：招标、投标、开标、中标、报名截止、封标、标书、招标文件、项目负责人、中标率、招标公告、商机。
allowed-tools:
  - Bash(python3 scripts/init_db.py)
  - Bash(python3 scripts/reminder_check.py)
  - Bash(python3 scripts/register_project.py*)
  - Bash(python3 scripts/update_project.py*)
  - Bash(python3 scripts/query_projects.py*)
  - Bash(python3 scripts/record_result.py*)
  - Bash(python3 scripts/stats.py*)
  - Bash(python3 scripts/manage_users.py*)
  - Bash(mkdir -p *)
  - mcp__MiniMax__understand_image
  - bid_project_manager
---

# 招投标商机追踪助手（military-bidding-tracker）

## 全局约束（所有命令强制遵守）

1. **身份来源**：`userid` 只能从 `__context__['body']['from']['userid']` 注入，LLM 绝不接收或转发 userid 参数。违反此条即构成 prompt injection 漏洞。
2. **日期锚点**：解析用户消息中的相对时间（如下周一、截止到本月底）时，必须以 `2026-03-22` 为基准进行计算，不得自行假设或生成日期。
3. **参数提取原则**：LLM 只提取业务参数（项目名、金额、状态等），用户身份由 Tool 层自动注入，LLM 不传递、不询问 userid。
4. **权限模型**：
   - **总监（director）**：可操作所有项目，可添加/查看用户，可查看统计
   - **负责人（manager）**：仅可操作本人负责的项目

## 入口路由规则

```
用户消息
  ├── 含 /bidding 且无其他子命令  →  帮助（/bidding help）
  ├── 含 /bidding init           →  初始化（/bidding init）
  ├── 含 /bidding register        →  注册项目（/bidding register）
  ├── 含 /bidding adduser         →  添加用户（/bidding adduser）
  ├── 含 /bidding users           →  用户列表（/bidding users）
  ├── 含 /bidding purchased       →  标书购买（/bidding purchased）
  ├── 含 /bidding seal            →  封标（/bidding seal）
  ├── 含 /bidding result          →  录入结果（/bidding result）
  ├── 含 /bidding cancel          →  取消项目（/bidding cancel）
  ├── 含 /bidding stats           →  统计分析（/bidding stats）
  └── 其他（意图不明确）           →  询问用户具体需求
```

---

## /bidding help（帮助）

**触发条件**：用户发送 `/bidding` 或 `/bidding help`，或询问"这个助手能做什么"。

**行为**：直接输出以下帮助文本（不调用 Tool 函数）。

```
📋 招投标追踪助手 — 可用命令

/bidding init              初始化系统（首次使用，总监注册）
/bidding register          上传招标公告，注册新项目
/bidding status            查看当前项目列表
/bidding purchased         确认已购买标书
/bidding seal              确认已封标
/bidding result            录入开标结果（中标/未中）
/bidding cancel            取消项目
/bidding users             查看团队成员（仅总监）
/bidding adduser           添加负责人（仅总监）
/bidding stats             查看统计（仅总监）

使用示例：
  「帮我注册这个招标公告」→ /bidding register
  「查一下我在跟的项目」 → /bidding status
  「中了，这次报价 98 万」 → /bidding result
```

---

## /bidding init（初始化）

**触发条件**：系统尚未初始化（users 表无 director），用户发送"初始化"、"我是王总监"。

**IF 系统已有 director → 输出**：`{"status": "error", "message": "系统已初始化，无需重复初始化"}`

**IF 系统未初始化 → THEN**：
1. LLM 提取用户消息中的显示名称（如"王总监"），若用户未提供则询问
2. 调用：
   ```
   bid_project_manager(action_type="init", project_data={"name": "王总监"}, **kwargs)
   ```
3. 成功 → 告知用户"初始化完成，您已被注册为系统总监"
4. 失败 → 原样输出 Tool 返回的 error message

---

## /bidding register（注册项目）

**触发条件**：用户上传招标公告文件（PDF/PNG），发送"注册项目"、"这是新招标"、"帮我建个项目"。

**前置约束**：仅总监可执行。若用户为 manager → 返回 error。

**步骤**：
1. 使用 `mcp__MiniMax__understand_image` 解析上传的公告文件，提取以下字段（尽力提取，不完整的字段在下一步确认）：
   - `project_name`（必填）
   - `budget`（选填）
   - `procurer`（选填，采购单位）
   - `bid_agency`（选填，代理机构）
   - `registration_deadline`（选填，报名截止时间）
   - `doc_purchase_deadline`（选填，标书购买截止）
   - `doc_purchase_location`（选填）
   - `doc_purchase_price`（选填）
   - `bid_opening_time`（必填，开标时间）
   - `bid_opening_location`（选填）
2. 向用户确认：`manager_name`（项目负责人姓名）、`travel_days`（从封标到开标的工作日数，默认 2）
3. 调用：
   ```
   bid_project_manager(action_type="register",
       project_data={
           "fields": {...},       # 第1步提取的所有字段
           "manager_name": "张经理",
           "travel_days": 2
       }, **kwargs)
   ```
   （附件路径由 Tool 层从 `__context__['body']['attachments'][0]['local_path']` 自动注入）

**成功响应示例**：
```json
{"status": "ok", "data": {
    "project_id": 42,
    "project_no": "2026-003",
    "project_name": "XX系统采购",
    "suggested_seal_time": "2026-04-08T14:00:00",
    "attachment_dir": "data/attachments/42"
}}
```
→ 告知用户：项目编号 `2026-003`，建议封标时间为 `suggested_seal_time`，标书附件已保存。

---

## /bidding status（查看项目）

**触发条件**：用户询问"我在跟哪些项目"、"查一下XXX项目"、"当前有哪些在筹项目"。

**IF 用户为 manager** → 系统自动过滤为本人负责项目（Tool 层处理）
**IF 用户为 director** → 可查看全部项目

**LLM 提取参数**：
```json
{"keyword": "XX系统", "active_only": true}
```
- `keyword`：`None` 表示无过滤；精确匹配 `project_no` 或 LIKE 匹配 `project_name`
- `active_only`：`true`（默认）仅返回活跃状态；`false` 返回全部（含已结束）

**调用**：
```
bid_project_manager(action_type="status",
    project_data={"keyword": null, "active_only": true}, **kwargs)
```

**响应**：表格形式展示项目列表，每行含 project_no、项目名、负责人、状态、关键时间节点。

---

## /bidding purchased（确认标书已购买）

**触发条件**：负责人发送"标书买了"、"已购买标书"、"交了500块"。

**前置约束**：
- 仅总监可操作任意项目
- 负责人仅可操作本人负责的项目（Tool 层校验）
- 项目当前状态必须为 `doc_pending` 或 `registered`（状态机校验由 update_project.py 执行）

**LLM 提取参数**：
```json
{"keyword": "XX系统采购"}
```

**调用**：
```
bid_project_manager(action_type="purchased",
    project_data={"keyword": "XX系统采购"}, **kwargs)
```

**成功响应**：`{"status": "ok", "message": "已更新项目状态：标书已购买"}`
**失败响应**：原样输出 error message（如状态不允许转换）。

---

## /bidding seal（确认已封标）

**触发条件**：负责人发送"已封标"、"标封好了"，或总监发送"帮XX项目封标"。

**前置约束**：
- 仅总监可操作任意项目
- 负责人仅可操作本人负责的项目
- 项目当前状态必须为 `preparing`（状态机校验）

**LLM 提取参数**：
```json
{"keyword": "XX系统采购"}
```

**调用**：
```
bid_project_manager(action_type="seal",
    project_data={"keyword": "XX系统采购"}, **kwargs)
```

**成功响应**：`{"status": "ok", "message": "已更新项目状态：已封标"}`

---

## /bidding result（录入开标结果）

**触发条件**：开标后，用户反馈"中了XX万"、"没中，第二名"、"中标了"。

**前置约束**：
- 仅总监可操作任意项目
- 负责人仅可操作本人负责的项目
- 项目当前状态必须为 `opened`（已开标）

**LLM 提取参数**：
```json
{
    "keyword": "XX系统采购",
    "is_won": true,
    "our_price": 980000,
    "winning_price": 950000,
    "winner": "某某公司",
    "notes": "排名第一，中标"
}
```
- `is_won`：**必填**，布尔值
- `our_price`、`winning_price`、`winner`、`notes`：选填，但建议引导用户提供以便统计

**调用**：
```
bid_project_manager(action_type="result",
    project_data={
        "keyword": "XX系统采购",
        "is_won": true,
        "our_price": 980000,
        "winning_price": 950000,
        "winner": "某某公司",
        "notes": "排名第一"
    }, **kwargs)
```

**成功响应**：`{"status": "ok", "message": "已录入开标结果：中标"}` 或 `{"status": "ok", "message": "已录入开标结果：未中标"}`

---

## /bidding cancel（取消项目）

**触发条件**：用户发送"取消这个项目"、"这个招标作废了"、"终止XX项目"。

**前置约束**：
- 仅总监可操作任意项目
- 负责人仅可操作本人负责的项目
- 项目当前状态不能是终态（won/lost/cancelled）

**LLM 提取参数**：
```json
{"keyword": "XX系统采购"}
```

**调用**：
```
bid_project_manager(action_type="cancel",
    project_data={"keyword": "XX系统采购"}, **kwargs)
```

**成功响应**：`{"status": "ok", "message": "项目已取消"}`

---

## /bidding users（查看用户）

**触发条件**：总监发送"查看用户"、"列出团队成员"、"看看有哪些负责人"。

**前置约束**：仅总监可执行。

**LLM 提取参数**：
```json
{"role": null}   // null=全部；"manager"=仅负责人；"director"=仅总监
```

**调用**：
```
bid_project_manager(action_type="users",
    project_data={"role": null}, **kwargs)
```

---

## /bidding adduser（添加用户）

**触发条件**：总监发送"添加负责人"、"把XXX加进来"、"新来一个项目经理"。

**前置约束**：仅总监可执行。

**LLM 提取参数**：
```json
{
    "user_id": "zhang_manager",
    "name": "张经理",
    "contact": "13800138000"   // 选填
}
```
- `user_id`：企业微信 userid（必填）
- `name`：显示名称（必填）

**调用**：
```
bid_project_manager(action_type="adduser",
    project_data={"user_id": "zhang_manager", "name": "张经理", "contact": "13800138000"}, **kwargs)
```

---

## /bidding stats（统计分析）

**触发条件**：总监询问"中标率是多少"、"各负责人业绩对比"、"本月统计"、"季度趋势"。

**前置约束**：仅总监可执行。

**LLM 提取参数**：
```json
{"by_manager": false, "by_month": true, "period": "2026-Q1"}
```
- `by_manager` 与 `by_month` **互斥**，二选一
- `period`：`YYYY-MM` 或 `YYYY-QN` 格式；省略表示全量

**调用**：
```
bid_project_manager(action_type="stats",
    project_data={"by_month": true, "period": "2026-Q1"}, **kwargs)
```

**响应**：以表格形式展示，包含总项目数、中标数、未中数、胜率、平均报价差。

---

## 定时提醒（Cron）

系统在工作日 8:47 和 17:53 自动运行 `reminder_check.py`。

- 输出 `[]`（空数组）→ 静默退出，不发消息
- 有提醒时，按 `recipient_role` 分组推送：
  - `manager` → 推送给对应负责人（仅展示本人相关提醒）
  - `director` → 推送给总监（汇总展示）

**提醒格式模板**：
```
🔔 [提醒类型] - [项目名称]
开标时间：xxx
开标地点：xxx
项目负责人：xxx
```

---

## 项目状态机

```
registered ──→ doc_pending ──→ doc_purchased ──→ preparing ──→ sealed ──→ opened ──→ won / lost
    │               │                 │                │              │            │
    └──→ cancelled ─┴──────→ cancelled ─┴──────→ cancelled ─┘            ↓
                                                           └──→ cancelled
```

| 状态 | 含义 | 可流转至 |
|------|------|---------|
| registered | 已登记 | doc_pending / doc_purchased / cancelled |
| doc_pending | 提醒已发 | doc_purchased / cancelled |
| doc_purchased | 标书已购 | preparing / cancelled |
| preparing | 制作标书中 | sealed / cancelled |
| sealed | 已封标 | opened / cancelled |
| opened | 已开标 | won / lost |
| won | 中标 | （终态） |
| lost | 未中标 | （终态） |
| cancelled | 已取消 | （终态） |
