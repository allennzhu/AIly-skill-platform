# Aily Skill：项目管理平台 API 对接设计

日期：2026-08-06  
状态：已确认（待实现）  
仓库：`e:\AIly-skill-platform` → `https://github.com/allennzhu/AIly-skill-platform.git`

## 1. 目标与范围

通过 Aily 自定义 Skill 将 51PM 项目管理平台 API 接入智能助手，实现「用户意图识别 → API 调用 → 数据分析」链路。

### 首版范围（MVP）

- 工时查询 + 生成工作总结
- 对接真实接口：`GET /manage_api/data_export/get_daily_estimate_list`
- 支持按日期、部门、人员筛选；人名/部门名在客户端内自动解析为 ID
- 结构可扩展，后续可新增项目进度等场景

### 明确不做（首版）

- 项目进度 / 延期任务 / 里程碑 / 人员分配等场景的真实接口对接
- 在脚本内生成本地工作总结文案（分析交给 Aily）
- 动态 OAuth / 飞书登录
- 改动现有 `AI-Skill-Platform` 或 `51PM` 代码

## 2. 架构

```text
用户自然语言
  → Aily 读 SKILL.md 匹配意图
  → 执行 api_client.py get_work_hours
  → （内部）人名/部门名 → ID → 工时接口
  → stdout 原始 JSON
  → Aily 按 SKILL.md 分析要点生成工作总结
```

| 组件 | 职责 | 不做 |
|------|------|------|
| `SKILL.md` | 意图触发、编排规则、分析框架 | 不执行 HTTP |
| `scripts/api_client.py` | 认证、OPERATIONS 注册、名字解析、CLI | 不写总结文案 |
| `references/api_docs.md` | 真实接口参数与字段说明 | — |
| Aily 运行时 | 触发 Skill、执行脚本、基于数据出结论 | — |

### 仓库结构

```text
AIly-skill-platform/
├── SKILL.md
├── scripts/
│   ├── api_client.py
│   └── package_skill.py
├── references/
│   └── api_docs.md
├── docs/superpowers/specs/
├── .env.example
├── .gitignore
└── README.md
```

## 3. 认证

环境变量注入，不硬编码 Token：

| 变量 | 说明 |
|------|------|
| `PM_PLATFORM_BASE_URL` | 平台 API 根地址 |
| `PM_PLATFORM_AUTH_TYPE` | 固定 `api_key` |
| `PM_PLATFORM_API_KEY` | Bearer Token |

请求头：`Authorization: Bearer {token}`。

## 4. 操作设计

### 4.1 对外操作（首版仅 1 个）

#### `get_work_hours`

| 项 | 值 |
|----|-----|
| method | GET |
| path | `/manage_api/data_export/get_daily_estimate_list` |
| 必填 | `start_date`, `end_date`（`YYYY-MM-DD`） |
| 可选 | `user_id` 或 `user_name`；`dept_id` 或 `dept_name` |
| 分页 | `page`（默认 1）、`page_size`（默认 500） |

### 4.2 名字自动解析（对 Aily 透明）

1. 传 `user_name` 且无 `user_id` →  
   `GET /manage_api/user/get_user_info_by_nick_name?nick_name=...` → 取用户 ID  
2. 传 `dept_name` 且无 `dept_id` →  
   `GET /manage_api/department/get_dept_info_by_dept_name?dept_name=...` → 取部门 ID  
3. 再调用工时接口  
4. 解析失败 → 返回 error JSON，不继续请求工时  
5. ID 与名字同时存在时，以 ID 为准  

首版不单独对外暴露 `resolve_user` / `resolve_dept` 操作。

### 4.3 CLI

```bash
python3 scripts/api_client.py --list-ops

python3 scripts/api_client.py get_work_hours \
  --param start_date 2026-08-03 \
  --param end_date 2026-08-06 \
  --param user_name 张三
```

成功：stdout 输出平台原始 JSON。  
失败：stdout 输出含 `error` 字段的 JSON，进程非 0 退出。

### 4.4 关键响应字段（供分析）

工时列表项主要字段：`date`、`task_name`、`consumed`、`user_name`、`name`（项目）、`sj_num`、`remark`、`task_process`、`confirm_status` / `confirm_status_name`、`dept_name`、`demand_name` 等。

## 5. SKILL.md 设计

### 5.1 Frontmatter

```yaml
---
name: pm-platform-api
label: 项目管理平台API
description: "对接项目管理平台 API。当用户提到工时统计、工作日报、生成工作总结、本周/今日工作汇总，或按人员/部门查询工时时触发。"
---
```

### 5.2 意图映射

| 用户意图 | 操作 | 编排 | 分析方向 |
|---------|------|------|---------|
| 生成工作总结 / 日报 | `get_work_hours` | 单步；日期默认本周一～今天或用户指定；可带人名/部门名 | 按项目汇总、按日排列、提炼重点 |
| 查某人/某部门工时 | `get_work_hours` | 单步；带人或部门 | 按日/项目列表，合计总工时 |

### 5.3 编排规则

1. 抽取起止日期、人名、部门名；缺日期默认本周一～今天（用户说「今日」则用当天）。
2. 优先传 `user_name` / `dept_name`，不猜测 ID。
3. 返回含 `error` 时向用户说明原因，不编造数据。
4. 成功则只基于返回 JSON 分析，数字可追溯。

### 5.4 工作总结输出结构

1. 概览：时间范围、人员/部门、总工时、项目数  
2. 按项目：工时合计 + 主要任务  
3. 按日期：每日要点  
4. 备注与风险：未确认工时、进度偏低项（若有）

## 6. 错误处理

| 场景 | error 码 |
|------|----------|
| 缺环境变量 | `config_error` |
| 人名/部门解析失败 | `resolve_failed` |
| HTTP 4xx/5xx | `http_error`（含 status） |
| 超时/网络 | `request_failed` |
| 未知操作 | `unknown_operation` |

请求超时默认 30 秒。

## 7. 扩展约定

新增接口时同步更新三处：

1. `OPERATIONS` 注册表  
2. `references/api_docs.md`  
3. `SKILL.md` 意图映射与 description  

无需改动请求主干逻辑。

## 8. 测试与交付

### 测试

- `--list-ops` 列出 `get_work_hours`
- 真实 Token 拉取本周工时有数据
- `user_name` 解析成功；错误名字返回 `resolve_failed`
- （可选）`package_skill.py` 生成 `.skill`

### 交付物

- 完整 Skill 目录与 README
- 本地 git 仓库关联远程 `AIly-skill-platform`
- 本设计文档
