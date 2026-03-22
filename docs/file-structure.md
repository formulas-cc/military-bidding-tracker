# 项目文件结构

> 版本：v1.0 | 日期：2026-03-22 | 关联文档：[api-interfaces.md](./api-interfaces.md)、[technical-design.md](./technical-design.md)

```
military-bidding-tracker/
├── SKILL.md                        # REWRITE  — 重写为 9 个斜杠命令架构（/bidding *）
├── README.md                       # DEFERRED — 后续迭代补充（项目说明与快速上手指南）
├── docs/
│   ├── requirements.md             # 原有 PRD，无需修改
│   ├── technical-design.md         # 原有 TDD v1.3，无需修改
│   ├── api-interfaces.md           # CREATED  — 脚本接口契约文档（本次新增）
│   └── file-structure.md           # CREATED  — 本文档
├── scripts/
│   ├── init_db.py                  # FIXED    — 补充 project_no、travel_days、wecom_userid 列
│   ├── manage_users.py             # CREATED  — 用户管理（bootstrap / add / list）
│   ├── register_project.py         # FIXED    — 增加 --manager-name；自动生成 project_no（YYYY-NNN）；输出改为 JSON
│   ├── query_projects.py           # FIXED    — --role/--name 替换为 --user-id/--keyword/--active-only
│   ├── update_project.py           # FIXED    — VALID_TRANSITIONS 增加 sealed→opened；输出改为 JSON
│   ├── record_result.py            # VERIFIED — 接口已正确，接受 sealed/opened 作为来源状态，输出改为 JSON
│   ├── reminder_check.py           # FIXED    — 增加 reminders 表去重写入逻辑
│   └── stats.py                    # IMPLEMENTED — 实现三个 stub 函数的 SQL 查询
├── tools/
│   └── bid_project_manager.py      # CREATED  — OpenClaw Tool 函数 + 权限网关
├── tests/
│   ├── conftest.py                 #          — pytest fixtures（临时 DB、通用 helper）
│   ├── test_init_db.py             #          — 6 cases：幂等、4 表存在、列完整性、WAL、外键、目录创建
│   ├── test_manage_users.py        #          — 7 cases：bootstrap 首次/幂等/冲突、add 权限、add 正常、list 全部、list 按 role
│   ├── test_register_project.py    #          — 6 cases：正常注册含 project_no、JSON 错误、travel_days=0、周末回避、公告文件归档、manager-name 必填
│   ├── test_query_projects.py      #          — 6 cases：director 全部、manager 本人、project_no 精确、project_name 模糊、active-only、user-id 不存在
│   ├── test_update_project.py      #          — 6 cases：合法迁移、非法迁移、sealed→opened、字段白名单、项目不存在、updated_at 更新
│   ├── test_record_result.py       #          — 4 cases：中标、未中标、非法来源状态、项目不存在
│   ├── test_reminder_check.py      #          — 7 cases：无到期→空数组、购买提醒、封标提醒、开标提醒、防重发、边界值（恰好3天）、过期项目不提醒
│   └── test_stats.py              #          — 5 cases：空数据库、全局统计、按 manager、按月、period 过滤
└── data/
    ├── bids.db                     #          — SQLite 数据库（.gitignore 排除）
    └── attachments/                #          — 项目附件归档目录
        └── {project_id}/           #          — 按项目 ID 分目录
            ├── announcement.{ext}  #          — 招标公告原件
            └── bid_docs.{ext}      #          — 标书文件
```

## 各文件修改说明

### SKILL.md — REWRITE

**原因**：当前 SKILL.md 采用角色询问 + 直接调用脚本的方式，与 TDD §2.2 设计的 9 个斜杠命令架构不符。需重写为 `/bidding *` 命令驱动，LLM 仅提取业务参数、调用 `bid_project_manager` Tool 函数，不参与身份判断。

### scripts/init_db.py — FIXED

**原因**：`projects` 表缺少 `project_no TEXT NOT NULL UNIQUE` 和 `travel_days INTEGER DEFAULT 0` 列；`users` 表缺少 `wecom_userid TEXT NOT NULL UNIQUE` 和 `created_at` 列。需按 TDD §3.1 补齐。

### scripts/manage_users.py — CREATED

**原因**：文件不存在。TDD §5.8 定义了三种模式（`--bootstrap`、`--add`、`--list`），是权限体系的基础依赖。

### scripts/register_project.py — FIXED

**原因**：
1. 缺少 `--manager-name` 必填参数（TDD §5.2）
2. 缺少 `project_no` 自动生成逻辑（`YYYY-NNN` 格式）
3. 输出为纯文本而非 JSON（应输出含 project_id、project_no、suggested_seal_time 的 JSON）

### scripts/query_projects.py — FIXED

**原因**：当前接口使用 `--role`/`--name` 参数，但 TDD §5.3 要求改为 `--user-id`（从 users 表查角色和姓名）、`--keyword`（先精确匹配 project_no 再模糊匹配 project_name）、`--active-only` flag。

### scripts/update_project.py — FIXED

**原因**：
1. `VALID_TRANSITIONS` 中 `sealed` 缺少到 `opened` 的转换（TDD §3.3 合法迁移矩阵明确包含 `sealed → opened`）
2. 输出应改为 JSON 格式
3. `doc_purchased` 应可直接到 `sealed`（跳过 preparing）

### scripts/record_result.py — VERIFIED

**原因**：接口已基本正确。确认接受 `sealed` 或 `opened` 作为合法来源状态。输出需改为 JSON 格式以符合全局规范。

### scripts/reminder_check.py — FIXED

**原因**：当前实现未向 `reminders` 表写入记录，缺少去重功能。TDD §6.3 要求在发送提醒前检查同日是否已发送，发送后写入 `reminders` 表。

### scripts/stats.py — IMPLEMENTED

**原因**：三个核心函数 `stats_global()`、`stats_by_manager()`、`stats_by_month()` 均为 `pass` stub。需实现 SQL 查询，基于 `projects LEFT JOIN bid_results`，支持 `--period` 过滤。

### tools/bid_project_manager.py — CREATED

**原因**：文件不存在。TDD §7.2 定义了 Tool 函数层鉴权逻辑，是双轨制鉴权的核心组件。所有 `/bidding *` 命令通过此函数入口执行。
