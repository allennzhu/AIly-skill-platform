# 51PM 填工时 API 参考

供 Aily 查阅。认证：环境变量 `PM_PLATFORM_BASE_URL`、`PM_PLATFORM_AUTH_TYPE=api_key`、`PM_PLATFORM_API_KEY`；或 `scripts/config.json`（Aily 市场无环境变量入口时）。请求头 `Authorization: Bearer {token}`。

## 操作：fill_hours_step

多轮填工时的唯一 CLI 入口：解析飞书用户、列出进行中任务、校验参数并提交工时。

| 项 | 值 |
|----|-----|
| CLI 操作名 | `fill_hours_step` |
| HTTP | 无（脚本内部编排多条 51PM 接口） |

### 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `feishu_open_id` | 是 | 飞书 open_id，标识当前会话用户 |
| `task_id` | 否 | 任务 ID（整数）；缺则返回 `task_options` |
| `task_kind` | 否 | `project` 或 `not_project`；影响任务列表过滤与提交路径 |
| `date` | 否 | 填报日期 `YYYY-MM-DD`；缺省为当天 |
| `consumed` | 否 | 工时（正数） |
| `remark` | 否 | 工时备注 |

### 成功响应（多轮）

stdout 输出 JSON，退出码 `0`：

```json
{
  "status": "need_input",
  "user": {"user_id": 474, "nick_name": "张三"},
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
      "project_name": "51PM",
      "task_kind": "project"
    }
  ],
  "result": null
}
```

| `status` | 含义 | Aily 动作 |
|----------|------|-----------|
| `need_input` | 缺参或待选任务 | 展示 `next_question`；有 `task_options` 时列序号供用户选择，再带 `--param` 重调 |
| `submitted` | 已提交 | 确认成功；`result` 为平台原始响应 |

`missing_fields` 可能含：`task_id`、`task_kind`、`consumed`、`remark`。

### CLI 示例

```bash
python3 scripts/api_client.py fill_hours_step \
  --param feishu_open_id ou_xxxxxxxx \
  --param consumed 2 \
  --param remark 联调
```

## 脚本调用的 51PM 路径

| 用途 | 方法 | 路径 | 说明 |
|------|------|------|------|
| open_id → 用户 | GET | `/manage_api/qiye_user/get_user_by_feishu_open_id` | 查询参数 `feishu_open_id`；超管 Token |
| 模拟登录 | POST | `/manage_api/user/impersonate_user` | Body `{"target_user_id": <id>}`；超管 Token；取 `data.token_info.access_token` |
| 进行中项目任务 | GET | `/manage_api/main_panel/get_task_list` | `status=doing`；用户 Token |
| 进行中非项目任务 | GET | `/manage_api/main_panel/get_not_task_list` | `status=doing`；用户 Token |
| 提交项目工时 | POST | `/manage_api/project_task_estimate/add` | Body：`task_id`, `date`, `consumed`, `remark`；用户 Token |
| 提交非项目工时 | POST | `/manage_api/project_not_task_estimate/add` | 同上；用户 Token |

平台响应为 GoFrame 包装：`{code, msg, data}`。`code != 0` 时脚本抛出 `business_error`。

## 错误 JSON

失败时 stdout 输出，进程退出码非 0：

```json
{"error": "validation_error", "detail": "missing required param: feishu_open_id"}
```

| error | 含义 |
|-------|------|
| `config_error` | 环境变量或 `config.json` 缺失/非法 |
| `validation_error` | 缺少必填参数、类型非法（如 `task_id` 非整数、`consumed` 非正数） |
| `business_error` | 平台业务错误（用户未绑定、impersonate 失败等） |
| `http_error` | HTTP 4xx/5xx（可能含 `status`） |
| `request_failed` | 网络/超时/非 JSON 响应 |
| `unknown_operation` | 未知操作名 |
