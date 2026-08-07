# 51PM 填工时 Aily Skill 设计

日期：2026-08-07  
状态：已确认（待实现）  
仓库：`e:\AIly-skill-platform`（Skill）+ `e:\51PM`（解析接口）

## 1. 目标与范围

新建独立 Aily Skill **`pm-fill-hours`**：根据飞书当前会话用户，为对应 51PM 账号填写工时；支持项目任务与非项目任务；支持多轮对话补齐必填参数与任务选择。

### 已确认决策

| 项 | 选择 |
|----|------|
| 放置 | 独立 Skill（不并入查工时 Skill） |
| 工时类型 | 项目 + 非项目 |
| 用户识别 | Aily 会话 `feishu_open_id` → 51PM `user_id` |
| 鉴权 | 超级用户 Token → `impersonate_user` 换目标用户 Token |
| 多轮 | 混合：Aily 追问；脚本返回 `missing_fields` / `task_options` / `next_question` |

### 不做（首版）

- 修改/删除已填工时
- 附件、关联人、任务选项明细拆分提交
- 脚本侧持久化会话 DB
- 与 `pm-platform-api`（查工时）合并

## 2. 架构

```text
飞书用户对话
  → Aily 触发 pm-fill-hours
  → 取会话 feishu_open_id
  → 超管 Token：open_id → user_id → impersonate → 用户 Token
  → fill_hours_step（缺参则返回 need_input + 选项/追问）
  → 参数齐：project 或 not_project 的 estimate/add
  → 成功确认
```

### 仓库结构（建议）

```text
AIly-skill-platform/
└── skills/pm-fill-hours/     # 或首版扁平 pm-fill-hours/
    ├── SKILL.md
    ├── scripts/
    │   ├── api_client.py
    │   ├── config.example.json
    │   └── config.json          # gitignore，含超管 Token
    └── references/
        └── api_docs.md
```

与现有查工时 Skill 分别打包为独立 `.skill` 上传 Aily。

| 组件 | 职责 |
|------|------|
| `api_client.py` | 解析用户、换 Token、列任务、提交、结构化缺参 |
| `SKILL.md` | 触发、多轮追问、展示任务选项 |
| 51PM | `open_id` 解析；复用 impersonate / 任务列表 / 填工时 |

## 3. 51PM 接口

### 3.1 复用

| 用途 | 方法 | 路径 |
|------|------|------|
| 模拟登录 | POST | `/manage_api/user/impersonate_user`（`target_user_id`；需超管） |
| 进行中项目任务 | GET | `/manage_api/main_panel/get_task_list`（`status=doing`） |
| 进行中非项目任务 | GET | `/manage_api/main_panel/get_not_task_list`（`status=doing`） |
| 提交项目工时 | POST | `/manage_api/project_task_estimate/add` |
| 提交非项目工时 | POST | `/manage_api/project_not_task_estimate/add` |

提交必填：`task_id`、`date`、`consumed`、`remark`。

### 3.2 新增

**`GET /manage_api/qiye_user/get_user_by_feishu_open_id`**

- 入参：`feishu_open_id`（必填）
- 查表：`dev_qiye_user`（`feishu_open_id` → `yunwei_id`）
- 返回：`user_id`（yunwei_id）、`nick_name`；未绑定明确错误

### 3.3 鉴权约定

1. Skill `config.json`：超级用户 Bearer（仅用于解析 + impersonate）
2. 每次填报：`open_id` → `user_id` → impersonate → 用户 Token（可短缓存）
3. 列任务、提交一律使用用户 Token

## 4. Skill 操作设计

| 操作 | 作用 |
|------|------|
| `resolve_session_user` | open_id → 用户信息 |
| `list_doing_tasks` | 进行中任务（可按 task_kind 过滤或合并） |
| `submit_estimate` | 按 task_kind 提交 |
| `fill_hours_step` | **主入口**：收参 / 提示缺失 / 或提交 |

### `fill_hours_step` 响应形状

```json
{
  "status": "need_input | ready | submitted | error",
  "user": {"user_id": 474, "nick_name": "朱晓辉"},
  "collected": {
    "task_id": null,
    "task_kind": null,
    "date": "2026-08-07",
    "consumed": null,
    "remark": null
  },
  "missing_fields": ["task_id", "consumed", "remark"],
  "next_question": "请选择要填工时的任务（回复序号或任务名）",
  "task_options": [
    {
      "index": 1,
      "task_id": 123,
      "name": "后端开发",
      "task_kind": "project",
      "project_name": "51PM"
    }
  ],
  "result": null
}
```

- `task_kind`：`project` | `not_project`
- 缺 `task_id` 时自动填充 `task_options`（两类合并，选项带 `task_kind`）
- 字段齐且校验通过后提交，`status=submitted`

### 字段规则

| 字段 | 规则 |
|------|------|
| `date` | 未提供默认今天 `YYYY-MM-DD` |
| `consumed` | 必填，正数 |
| `remark` | 必填，非空 |
| `task_id` / `task_kind` | 必填；来自选项或用户明确合法 ID |

无服务端会话表：Aily 对话中累积字段，每轮调用带上已收集参数。

## 5. SKILL.md 多轮编排

1. 取会话 `feishu_open_id`；取不到则说明无法识别用户
2. 调用 `fill_hours_step`，传入本轮已收集字段
3. `need_input`：按 `next_question` 追问；有 `task_options` 则展示列表
4. 用户选择后传入 `task_id` + `task_kind` 再调
5. `submitted`：确认任务名、日期、工时
6. `error`：说明原因，不编造成功

触发 description 覆盖：填工时、报工、写日报工时、登记工时等。

## 6. 错误处理

| 类型 | 场景 |
|------|------|
| `config_error` | 缺 base_url / 超管 Token |
| `resolve_failed` | open_id 未绑定 |
| `auth_error` | impersonate 失败 |
| `need_input` / `validation_error` | 缺必填 |
| `empty_tasks` | 无进行中任务 |
| `http_error` / `business_error` | HTTP 或业务 `code != 0` |

凭证：优先环境变量，否则 `scripts/config.json`（与查工时 Skill 一致；Aily 无环境变量 UI）。

## 7. 实施顺序

1. 51PM：新增 open_id 解析接口；超管 Token 冒烟 impersonate
2. Skill：`api_client` + `fill_hours_step` + 单测
3. `SKILL.md` / `api_docs.md` + 打包
4. Aily 多轮联调（项目 + 非项目各一条）

## 8. 验收

- [ ] open_id 能解析到用户；未绑定有明确错误
- [ ] 缺参返回 `need_input` 与 `missing_fields` / `task_options`
- [ ] 选定任务并补齐后提交成功
- [ ] 项目与非项目路径均跑通
- [ ] Aily 对话端到端可用
