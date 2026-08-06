# 51PM 平台 API 参考

供 Aily 查阅。认证：环境变量 `PM_PLATFORM_BASE_URL`、`PM_PLATFORM_AUTH_TYPE=api_key`、`PM_PLATFORM_API_KEY`；请求头 `Authorization: Bearer {token}`。

## 操作：get_work_hours

获取每日工时/日报数据。脚本支持 `user_name` / `dept_name` 自动解析为 ID。

| 项 | 值 |
|----|-----|
| CLI 操作名 | `get_work_hours` |
| HTTP | `GET` |
| 路径 | `/manage_api/data_export/get_daily_estimate_list` |

### 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `start_date` | 是 | 开始日期 `YYYY-MM-DD` |
| `end_date` | 是 | 结束日期 `YYYY-MM-DD` |
| `user_id` | 否 | 用户 ID；与 `user_name` 同时存在时以 ID 为准 |
| `user_name` | 否 | 用户昵称，脚本内解析为 `user_id` |
| `dept_id` | 否 | 部门 ID；与 `dept_name` 同时存在时以 ID 为准 |
| `dept_name` | 否 | 部门名称，脚本内解析为 `dept_id` |
| `page` | 否 | 默认 `1` |
| `page_size` | 否 | 默认 `500` |

### 内部解析接口（脚本自动调用，一般无需直接编排）

| 用途 | 方法 | 路径 | 查询参数 |
|------|------|------|----------|
| 人名 → 用户 ID | GET | `/manage_api/user/get_user_info_by_nick_name` | `nick_name` |
| 部门名 → 部门 ID | GET | `/manage_api/department/get_dept_info_by_dept_name` | `dept_name` |

解析成功后从响应 `data.id` 取值。`data` 为空则返回 `resolve_failed`。

### 成功响应关键字段

列表在 `data` 数组中，单条常见字段：

| 字段 | 说明 |
|------|------|
| `date` | 日期 |
| `task_name` | 任务名称 |
| `consumed` | 消耗工时 |
| `user_name` | 用户名称 |
| `user_id` | 用户 ID |
| `name` | 项目名称 |
| `sj_num` | 商机号 |
| `remark` | 备注 |
| `task_process` | 任务进度 |
| `confirm_status` | 确认状态 |
| `confirm_status_name` | 确认状态名称 |
| `dept_name` | 部门名称 |
| `demand_name` | 需求名称 |

### CLI 示例

```bash
python3 scripts/api_client.py get_work_hours \
  --param start_date 2026-08-03 \
  --param end_date 2026-08-06 \
  --param user_name 张三
```

## 错误 JSON

失败时 stdout 输出，进程退出码非 0：

```json
{"error": "resolve_failed", "detail": "user: 张三 not found"}
```

| error | 含义 |
|-------|------|
| `config_error` | 环境变量缺失或非法 |
| `validation_error` | 缺少必填参数等 |
| `resolve_failed` | 人名/部门名解析失败 |
| `http_error` | HTTP 4xx/5xx（可能含 `status`） |
| `request_failed` | 网络/超时/非 JSON 响应 |
| `unknown_operation` | 未知操作名 |
