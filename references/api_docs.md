# 51PM 平台 API 参考

供 Aily 查阅。

## 鉴权架构

| 步骤 | 说明 |
|------|------|
| 1 | 飞书智能体：`user_access_token` → 飞书 API → `union_id` / 邮箱 |
| 2 | `auth --param action save-identity` → 写入 `.feishu_identity.json` |
| 3 | `GET /manage_api/skill_auth/token?feishu_union_id=...`（免鉴权）取 Bearer Token |
| 4 | 无 token → `auth_required`，用户登录 :771 后重试 |

请求头：`Authorization: Bearer {access_token}`。

本地 IDE 请使用 **51PM_CLI**，见 `references/auth_flow_design.md`。

## 操作：export_estimate_hour_by_project

按项目/部门/日期导出全量工时明细 Excel（项目任务 + 非项目任务）。

| 项 | 值 |
|----|-----|
| CLI 操作名 | `export_estimate_hour_by_project` |
| HTTP | `GET` |
| 路径 | `/manage_api/data_export/export_estimate_hour_for_cd` |
| 权限 | **服务端鉴权**（需 Bearer Token；与网页「全量工时导出」同一接口） |
| 输出 | 保存到 `scripts/exports/*.xls`，JSON 返回 `file_path` |

### 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `start_date` | 是 | 开始日期 YYYY-MM-DD |
| `end_date` | 是 | 结束日期 YYYY-MM-DD |
| `project_id` / `project_name` / `sj_num` | 否 | 按项目筛选（可多项目） |
| `dept_id` / `dept_name` | 否 | 按部门筛选 |
| `output_name` | 否 | 自定义导出文件名 |

### CLI 示例

```bash
python3 scripts/api_client.py export_estimate_hour_by_project \
  --param start_date 2026-08-01 --param end_date 2026-08-31 \
  --param project_name 某某展厅
```

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
| `limit` | 否 | 每页条数，默认 `500`（对应平台 `PaginationReq.limit`） |
| `page_size` | 否 | `limit` 的别名，脚本会转成 `limit` |

### 内部解析接口（脚本自动调用，一般无需直接编排）

| 用途 | 方法 | 路径 | 查询参数 |
|------|------|------|----------|
| 人名 → 用户 ID | GET | `/manage_api/user/get_user_info_by_nick_name` | `nick_name` |
| 部门名 → 部门 ID | GET | `/manage_api/menu_department/get_dept_info_by_dept_name` | `dept_name` |

平台响应为 GoFrame 包装：`{code, msg, data}`，实体常在 `data.data`。解析成功后取 `id`；`code != 0` 或无 id 则返回 `resolve_failed`。

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
| `resolve_failed` | 人名/部门名/项目名解析失败 |
| `http_error` | HTTP 4xx/5xx（可能含 `status`） |
| `request_failed` | 网络/超时/非 JSON 响应 |
| `unknown_operation` | 未知操作名 |

## 操作：get_project_list

查询项目列表（管理端全量筛选）。对应平台 `SearchProjectCondition`，脚本支持友好参数自动解析。

| 项 | 值 |
|----|-----|
| CLI 操作名 | `get_project_list` |
| HTTP | `GET` |
| 路径 | `/manage_api/project/get_project_list` |

### 平台字段（可直接传，或与友好别名二选一）

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | string | 项目名称（模糊） |
| `sj_num` | string | 商机号（精确） |
| `kaigong_date_start` | string | 开工日期起 `YYYY-MM-DD` |
| `kaigong_date_end` | string | 开工日期止 `YYYY-MM-DD` |
| `ecp_kaigong_ling_shi_jian` | string | ECP 开工令时间 |
| `income_date` | string | 营收时间 |
| `is_income` | int | 营收状态（平台默认 `-2` 表示不过滤） |
| `ecp_stage` | string | ECP 阶段/开工状态 |
| `project_process` | string | 项目进度 |
| `risk_level` | string | 风险等级 |
| `ecp_shi_ye_bu` | string | ECP 事业部 |
| `ecp_shang_ji_hang_ye_lei_xing` | string | ECP 商机行业类型 |
| `project_scene` | string | 项目场景/制作组 |
| `project_dta` | string | DTA 资产 |
| `ecp_qu_yu_tuan_dui` | string | ECP 区域团队 |
| `only_lizhi` | int | `1` = 仅含离职人员的项目 |
| `project_pm` | int | 项目经理用户 ID |
| `project_scene_duty` | int | 美术负责人用户 ID |
| `project_develop` | int | 开发用户 ID |
| `project_tester` | int | 测试用户 ID |
| `project_bd_tb` | int | BD/TB/BG 用户 ID |
| `web_developer` | int | Web 开发用户 ID |
| `project_tech` | int | 技术用户 ID |
| `project_ui` | int | UI 设计用户 ID |
| `page` | int | 页码，默认 `1` |
| `limit` / `page_size` | int | 每页条数，默认 `500` |

### 友好别名（自动映射到上表平台字段）

| 用户可说 / CLI 别名 | 映射为 |
|--------------------|--------|
| `project_name` | `name` |
| `opportunity_no` / `business_no` | `sj_num` |
| `group_name` / `team_name` / `region_team` / `qu_yu_tuan_dui` / `ecp_group` / `make_team` | `ecp_qu_yu_tuan_dui` |
| `kaigong_start` / `start_kaigong_date` | `kaigong_date_start` |
| `kaigong_end` / `end_kaigong_date` | `kaigong_date_end` |
| `ecp_kaigong_date` / `kaigong_ling_date` / `kaigong_ling_shi_jian` | `ecp_kaigong_ling_shi_jian` |
| `revenue_date` / `yinshou_date` | `income_date` |
| `income_status` / `revenue_status` / `yinshou_status` | `is_income`（转 int） |
| `business_unit` / `shi_ye_bu` / `ecp_business_unit` | `ecp_shi_ye_bu` |
| `industry_type` / `hang_ye_lei_xing` / `ecp_industry` / `shang_ji_hang_ye` | `ecp_shang_ji_hang_ye_lei_xing` |
| `scene` / `make_group` / `project_scene_name` / `scene_name` | `project_scene` |
| `dta` / `dta_asset` | `project_dta` |
| `stage` / `project_stage` / `project_status` / `status` | `ecp_stage` |
| `process` / `progress` / `project_progress` | `project_process` |
| `risk` / `risk_level_name` | `risk_level` |
| `only_resigned` / `resigned_only` | `only_lizhi`（转 int） |
| `pm_name` | `project_pm`（昵称 → ID） |
| `develop_name` | `project_develop` |
| `tester_name` | `project_tester` |
| `bd_name` | `project_bd_tb` |
| `ui_name` | `project_ui` |
| `scene_duty_name` | `project_scene_duty` |
| `tech_name` | `project_tech` |
| `web_dev_name` | `web_developer` |

ID 与 `*_name` 同时存在时，以 ID 为准。

### 成功响应关键字段

列表在 `data` 数组中，单条常见字段：`id`、`name`、`sj_num`、`project_pm`、`ecp_stage`、`project_process`、`consumed_hour`、`standard_hour`、`project_scene`、`risk_level`、`ecp_qu_yu_tuan_dui` 等。

### CLI 示例

```bash
python3 scripts/api_client.py get_project_list --param pm_name 张三 --param group_name 华东组
python3 scripts/api_client.py get_project_list --param stage 制作中 --param business_unit 数字娱乐
python3 scripts/api_client.py get_project_list --param kaigong_start 2026-01-01 --param kaigong_end 2026-12-31
```

## 操作：get_my_projects

查询「我参与的项目」（我的地盘）。不传 `user_name` 时使用 API Key 对应账号；传 `user_name` 时脚本先模拟登录该用户。

| 项 | 值 |
|----|-----|
| CLI 操作名 | `get_my_projects` |
| HTTP | `GET` |
| 路径 | `/manage_api/main_panel/get_project_list` |

### 平台字段

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | string | 项目名称 |
| `sj_num` | string | 商机号 |
| `ecp_stage` | string | 项目状态 |
| `kaigong_date_start` | string | 开工日期起 |
| `kaigong_date_end` | string | 开工日期止 |
| `page` / `limit` / `page_size` | int | 分页 |
| `user_name` | string | 指定用户昵称（内部模拟登录，不传给平台） |

### 友好别名

| 用户可说 / CLI 别名 | 映射为 |
|--------------------|--------|
| `project_name` | `name` |
| `opportunity_no` / `business_no` | `sj_num` |
| `stage` / `project_stage` / `project_status` / `status` | `ecp_stage` |
| `kaigong_start` / `start_kaigong_date` | `kaigong_date_start` |
| `kaigong_end` / `end_kaigong_date` | `kaigong_date_end` |

### 内部解析接口

| 用途 | 方法 | 路径 | Body/参数 |
|------|------|------|-----------|
| 人名 → 用户 ID | GET | `/manage_api/user/get_user_info_by_nick_name` | `nick_name` |

### CLI 示例

```bash
python3 scripts/api_client.py get_my_projects
python3 scripts/api_client.py get_my_projects --param project_name 展厅 --param stage 制作中
```

## 操作：get_project_info

查询单个项目详情。支持名称/商机号自动解析为 ID。

| 项 | 值 |
|----|-----|
| CLI 操作名 | `get_project_info` |
| HTTP | `GET` |
| 路径 | `/manage_api/project/get_project_info` |

### 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `id` / `project_id` | 三选一 | 项目 ID |
| `project_name` / `name` | 三选一 | 项目名称（脚本先调 `get_project_list` 解析） |
| `sj_num` / `opportunity_no` / `business_no` | 三选一 | 商机号 |

### CLI 示例

```bash
python3 scripts/api_client.py get_project_info --param sj_num SJ20240001
python3 scripts/api_client.py get_project_info --param project_name 某某展厅项目
python3 scripts/api_client.py get_project_info --param id 123
```

## 操作：get_project_work_hours

查询某个项目下的工时花费列表（项目任务维度）。

| 项 | 值 |
|----|-----|
| CLI 操作名 | `get_project_work_hours` |
| HTTP | `GET` |
| 路径 | `/manage_api/project_task_estimate/get_estimate_list_by_project_id` |

### 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `project_id` | 与下三项四选一 | 项目 ID |
| `project_name` / `name` | 四选一 | 项目名称（自动解析为 `project_id`） |
| `sj_num` / `opportunity_no` / `business_no` | 四选一 | 商机号 |
| `start_date` / `date_start` / `from_date` | 否 | 开始日期 |
| `end_date` / `date_end` / `to_date` | 否 | 结束日期 |
| `page` / `limit` / `page_size` | 否 | 分页，默认 page=1、limit=500 |

### 成功响应关键字段

`data` 数组常见字段：`id`、`task_id`、`date`、`consumed`、`user_name`、`remark`、`demand_name`、`department_name`、`confirm_status` 等。

### CLI 示例

```bash
python3 scripts/api_client.py get_project_work_hours \
  --param project_name 某某展厅 \
  --param start_date 2026-08-01 \
  --param end_date 2026-08-31
```

## 操作：get_work_hour_statistics

工时数据总览，支持按项目/人员/部门筛选。

| 项 | 值 |
|----|-----|
| CLI 操作名 | `get_work_hour_statistics` |
| HTTP | `GET` |
| 路径 | `/manage_api/data_export/get_work_hour_statistics` |

### 平台字段

| 参数 | 必填 | 说明 |
|------|------|------|
| `start_date` | 是 | 开始日期 |
| `end_date` | 是 | 结束日期 |
| `user_ids` | 否 | 花费人 ID 列表（可逗号分隔） |
| `dept_id` | 否 | 部门 ID |
| `confirm_status` | 否 | `-1` 全部 / `0` 待确认 / `1` 已确认，默认 `-1` |
| `project_type` | 否 | `all` / `project` / `not_project`，默认 `all` |
| `project_ids` | 否 | 项目或非项目 ID 列表（可逗号分隔） |

### 友好别名

| 用户可说 / CLI 别名 | 映射为 |
|--------------------|--------|
| `date_start` / `from_date` | `start_date` |
| `date_end` / `to_date` | `end_date` |
| `user_name` | `user_ids`（昵称 → ID） |
| `dept_name` | `dept_id` |
| `project_name` / `name` / `sj_num` / `opportunity_no` | `project_ids` |
| `project_id` | `project_ids` |
| `type` / `kind` / `hour_type` | `project_type` |
| `待确认` / `已确认` / `全部` | `confirm_status` |
| `项目` / `非项目` / `全部` | `project_type` |

### 成功响应关键字段

`summary`（`total_hour`、`project_hour`、`not_project_hour` 等）、`project_top5`、`not_project_top5`、`task_option_distribution` 等。

### CLI 示例

```bash
python3 scripts/api_client.py get_work_hour_statistics \
  --param start_date 2026-08-01 \
  --param end_date 2026-08-31 \
  --param project_name 某某展厅
```

## 操作：get_work_hour_detail_list

工时下钻明细列表，支持按项目/人员/部门/产出类型筛选。

| 项 | 值 |
|----|-----|
| CLI 操作名 | `get_work_hour_detail_list` |
| HTTP | `GET` |
| 路径 | `/manage_api/data_export/get_work_hour_detail_list` |

### 平台字段

在 `get_work_hour_statistics` 基础上增加：

| 参数 | 说明 |
|------|------|
| `output_type` | `all` / `output` / `non_output`，默认 `all` |
| `option_id` | 任务选项 ID |
| `estimate_type` | 请假类型编码 |
| `category_keyword` | 非项目分类/名称关键字 |
| `page` / `limit` | 分页，默认 page=1、limit=20 |

### 额外友好别名

| 用户可说 / CLI 别名 | 映射为 |
|--------------------|--------|
| `output` / `output_kind` | `output_type` |
| `产出` / `非产出` / `全部` | `output_type` |
| `leave_type` | `estimate_type` |
| `category` / `not_project_keyword` | `category_keyword` |

### 成功响应关键字段

`data` 数组常见字段：`project_name`、`sj_num`、`task_name`、`demand_name`、`date`、`consumed`、`user_name`、`dept_name`、`confirm_status_name`、`output_type_name`、`remark` 等。

### CLI 示例

```bash
python3 scripts/api_client.py get_work_hour_detail_list \
  --param start_date 2026-08-01 \
  --param end_date 2026-08-31 \
  --param sj_num SJ20240001 \
  --param user_name 张三 \
  --param output_type 产出
```

## 扩展操作一览

以下操作定义在 `scripts/operations_extended.py`，参数解析规则与上文一致（`project_name`→`project_id`/`sj_num`，`pm_name`→`pm_id`，`period_type` 支持中英文等）。

### 项目健康度 `get_project_overview_*`

路径前缀：`/manage_api/project_overview/`。均需 `project_id`（可由 `project_name`/`sj_num` 解析）。

| 操作 | 路径后缀 | 额外必填 |
|------|---------|---------|
| `get_project_overview_header` | `get_header` | — |
| `get_project_overview_req_cost` | `get_req_cost` | — |
| `get_project_overview_quality` | `get_quality` | — |
| `get_project_overview_deliver` | `get_deliver` | — |
| `get_project_overview_people` | `get_people` | — |
| `get_project_overview_risk` | `get_risk` | — |
| `get_project_overview_value` | `get_value` | — |
| `get_project_overview_req_detail` | `get_req_detail` | `chart_key` |
| `get_project_overview_quality_detail` | `get_quality_detail` | `chart_key`, `option` |

### 项目动态 `get_project_moment_*`

| 操作 | 路径 | 必填 |
|------|------|------|
| `get_project_moment_list` | `/manage_api/project_moment/get_list` | — |
| `get_project_moment_info` | `/manage_api/project_moment/get_info` | `id`/`moment_id` |
| `get_project_moment_stat` | `/manage_api/data_export/get_project_moment_stat` | `period_type`, `period_key` |
| `get_project_moment_stat_list` | `.../get_project_moment_stat_list` | 周期 |
| `get_project_moment_stat_detail` | `.../get_project_moment_stat_detail` | 周期 + `module` |

`module` 别名：`会议`→`meet`，`风险`→`risk`，`问题`→`problem`。

### BUG

| 操作 | 路径 | 说明 |
|------|------|------|
| `get_bug_list` | `/manage_api/bug/get_list` | `project_name`→`sj_num`；`tester_name`/`assignee_name` |
| `get_bug_info` | `/manage_api/bug/get_info` | `id`/`bug_id` |
| `get_bug_total` | `/manage_api/bug/get_bug_total` | 全局 BUG 计数 |

### QA / 递交

| 操作 | 路径 |
|------|------|
| `get_qa_stat_kpi` | `/manage_api/data_export/get_qa_stat_kpi` |
| `get_qa_stat_bug` | `.../get_qa_stat_bug` |
| `get_qa_stat_publish` | `.../get_qa_stat_publish` |
| `get_qa_stat_summary` | `.../get_qa_stat_summary` |
| `get_qa_stat_detail_list` | `.../get_qa_stat_detail_list`（需 `chart_key`） |

公共筛选：`period_type`、`period_key`、`dept_name`、`pm_name`、`tester_name`、`assignee_name`。

### 项目成本

| 操作 | 路径 | 说明 |
|------|------|------|
| `get_project_cost_stat` | `.../get_project_cost_stat` | `project_id` 字段实为商机号 `sj_num` |
| `get_project_cost_stat_list` | `.../get_project_cost_stat_list` | 必填项目 |
| `get_project_cost_list` | `.../get_project_cost_list` | 同 `get_project_list` 筛选参数 |
| `get_project_cost_by_id` | `/manage_api/project/get_cost_list_by_project_id` | 单项目成本明细 |

### 部门产能

| 操作 | 路径 | 说明 |
|------|------|------|
| `get_dept_capacity_panel` | `.../get_dept_capacity_panel` | `dept_name`、日期范围 |
| `get_dept_left_hour_panel` | `.../get_dept_left_hour_panel` | 无参 |
| `get_dept_left_hour_demand_list` | `.../get_dept_left_hour_demand_list` | `dept_key` + `status`（doing/pause/wait） |

### 递交台账 / 申请

| 操作 | 路径 | 说明 |
|------|------|------|
| `get_publish_list` | `/manage_api/project_publish/get_list` | `pm_name`→`project_pm`；`start_date`/`end_date`→`begin`/`end` |
| `get_publish_info` | `/manage_api/project_publish/publish_info` | `publish_id`→`id` |
| `get_apply_publish_list` | `/manage_api/produce_demand/get_publish_list` | 可选 `project_name`→`project_id` |

### 项目任务

| 操作 | 路径 | 说明 |
|------|------|------|
| `get_task_list` | `/manage_api/task/get_task_list` | **任务**列表；`assignee_name`/`user_name`→`assigned_to[]`；支持日期/部门/项目筛选 |
| `get_project_demand_list` | `/manage_api/project_task/get_task_list` | **需求**列表（含需求树）；必填项目 |
| `get_task_info` | `/manage_api/project_task/get_task_info` | `task_id`→`id` |

### 风险 / 复盘 / ECP / 交付形态

| 操作 | 路径 | 说明 |
|------|------|------|
| `get_project_risk_panel` | `.../get_project_risk_panel` | 全局风险；`pm_name`/`bd_name` 自动解析 |
| `get_project_review_panel` | `.../get_project_review_panel` | 复盘得分、待办、经验沉淀 |
| `get_project_change_info` | `.../get_project_change_info` | ECP 每日动态；`project_name`→`sj_num` |
| `get_project_delivery_type_panel` | `.../get_project_delivery_type_panel` | `start_year`/`end_year`/`is_wdp` |

### 人力排期 / 工时矩阵

| 操作 | 路径 | 说明 |
|------|------|------|
| `get_total_schedule_list` | `.../get_total_paiqi_list` | 排期总览，无参 |
| `get_employee_project_list` | `.../get_employee_project_list` | `dept_name`/`user_name`；`filter_type` 支持中英文 |
| `get_employee_project_charts` | `.../get_employee_project_charts` | 甘特图数据 |
| `get_all_times_list` | `.../get_all_times_list` | 工时填报矩阵 |
| `get_qa_stat_period_target` | `.../get_qa_stat_period_target` | QA 周期目标（准时率、BUG 降幅） |

### 报价单

| 操作 | 路径 | 说明 |
|------|------|------|
| `get_project_quotation_list` | `/manage_api/project_quotation/get_quotation_list` | 必填商机号；`project_name`→`sj_num`；返回成本/标准价汇总 |
| `get_ecp_baojia_list` | `.../get_ecp_baojia_list` | ECP 报价项目录；`business_unit`→`ywx` |
| `get_ecp_baojia_const` | `.../get_ecp_baojia_const` | 模块/版本字典，无参 |
| `get_outsource_quotation_list` | `/manage_api/outsource_quotation/get_quotation_list` | 模型外包报价；`package_id`→`outsource_package_id` |

### 非项目工时

| 操作 | 路径 | 说明 |
|------|------|------|
| `get_not_project_list` | `/manage_api/not_project/get_list` | 非项目列表 |
| `get_not_project_info` | `/manage_api/not_project/get_info` | `not_project_name`→`id` |
| `get_not_project_select_list` | `/manage_api/not_project/get_select_list` | 下拉列表 |
| `get_not_project_display_tree` | `/manage_api/not_project/get_display_tree` | 分类树 |
| `get_not_project_category_list` | `/manage_api/not_project_category/get_list` | 分类列表 |
| `get_not_project_demand_list` | `/manage_api/project_not_task/get_demand_list` | 必填非项目 |
| `get_not_project_demand_info` | `.../get_demand_info` | `demand_id`→`id` |
| `get_not_project_task_list` | `.../get_task_list` | 需 `demand_id`→`pid` |
| `get_not_project_task_info` | `.../get_task_info` | 任务详情 |
| `get_not_project_work_hours` | `/manage_api/project_not_task_estimate/get_estimate_list_by_project_id` | 非项目工时列表 |
| `get_not_project_task_estimate_list` | `.../get_task_estimate_list` | 单任务工时明细 |

### 外包 / 供应商

| 操作 | 路径 | 说明 |
|------|------|------|
| `get_outsource_package_list` | `/manage_api/outsource/get_package_list` | 模型外包发包列表 |
| `get_outsource_package_detail` | `/manage_api/outsource/get_package_detail` | `package_id`→`id` |
| `get_outsource_data_overview` | `/manage_api/outsource/get_data_overview` | 数据总览 |
| `get_outsource_data_overview_package_list` | `.../get_data_overview_package_list` | 总览下钻发包 |
| `get_outsource_settlement_list` | `/manage_api/outsource_settlement/get_settlement_list` | 结算列表 |
| `get_outsource_settlement_detail` | `.../get_settlement_detail` | 结算详情 |
| `get_supplier_outsource_overview` | `/manage_api/supplier_outsource/get_overview` | 制作概览 |
| `get_supplier_outsource_work_ledger` | `.../get_work_ledger` | 发包台账 |
| `get_supplier_outsource_package_list` | `.../get_package_list` | 供应商侧发包列表 |
| `get_supplier_outsource_package_detail` | `.../get_package_detail` | `package_id`→`no` |
| `get_supplier_outsource_board` | `.../get_supplier_board` | 供应商看板 |
| `get_supplier_outsource_profile` | `.../get_supplier_profile` | 供应商画像 |
| `get_supplier_outsource_capability_matrix` | `.../get_capability_matrix` | 能力矩阵 |
| `get_supplier_outsource_filter_options` | `.../get_filter_options` | 筛选字典 |
| `get_supplier_list` | `/manage_api/supplier/get_supplier_list` | 供应商档案 |
| `get_supplier_detail` | `/manage_api/supplier/get_supplier_detail` | 供应商详情 |

### CLI 增强

| 参数 | 说明 |
|------|------|
| `--list-ops-grouped` | 按模块分组列出操作（含 `group` 字段） |
| `--fetch-all` | 列表接口自动翻页合并（或 `--param fetch_all 1`） |
| `period` / `period_label` | 周期自然语言，自动解析为 `period_type`+`period_key` |
| `auth --param action save-identity` | 保存飞书 union_id / 邮箱（智能体首次调用） |
| `auth --param action status` | 查看当前登录状态 |
| `--dry-run` | 写操作预览（写操作默认即为预览） |
| `--confirm` | 写操作确认执行（须带 `confirm_token`） |

## 写操作（两阶段交互）

写操作在 `--list-ops-grouped` 中归入 **写操作** 分组，JSON 含 `"write": true`。

### 协议

| 控制参数 | 说明 |
|---------|------|
| `dry_run` | `1` 时仅预览（写操作默认） |
| `confirm` | `1` 时真正 POST；须带有效 `confirm_token` |
| `confirm_token` | 预览返回的 HMAC 令牌，绑定 `operation`+`body` |
| `force` | `1` 跳过确认直接提交（慎用） |

预览响应示例字段：`dry_run`、`summary`、`resolved_body`、`will_call`、`confirm_token`、`warnings`、`next_step`。

### confirm_my_work_hours

| 项 | 值 |
|----|-----|
| CLI | `confirm_my_work_hours` |
| HTTP | `POST /manage_api/main_panel/confirm_anything` |
| Body | `id`（工时花费 ID）、`confirm_type`：`ConfirmTaskEstimate`（项目）或 `ConfirmNotTaskEstimate`（非项目） |

别名：`estimate_id`/`work_hour_id`→`id`；`项目`/`非项目`→`confirm_type`。

```bash
python3 scripts/api_client.py confirm_my_work_hours \
  --param id 12345 --param confirm_type 项目
```

### add_project_moment

| 项 | 值 |
|----|-----|
| CLI | `add_project_moment` |
| HTTP | `POST /manage_api/project_moment/add` |
| Body | `project_id`、`module`（meet/risk/problem）、`type`、`content`、`user_id`（数组）；风险/问题需 `risk_level` |

别名：`project_name`/`sj_num`→`project_id`；`会议`/`风险`/`问题`→`module`；`user_name`（逗号分隔）→`user_id`。

```bash
python3 scripts/api_client.py add_project_moment \
  --param project_name 某某展厅 --param module 会议 \
  --param type 周会 --param content 进度同步 --param user_name 张三,李四
```

### add_project_task_estimate

| 项 | 值 |
|----|-----|
| CLI | `add_project_task_estimate` |
| HTTP | `POST /manage_api/project_task_estimate/add` |
| 说明 | **仅项目任务**。非项目任务请用 `add_not_project_estimate`。填报 `date` 须在任务 `start_date`～`end_date` 内，否则返回 `estimate_date_out_of_range`。**同一任务同一天只能有一条工时**，当天已存在则返回 `duplicate_estimate`，应改用 `update_project_task_estimate`（若当日记录已确认则返回 `estimate_confirmed_immutable`，不可改）；跨天可分别 add |
| Body | `task_id`、`date`（默认当天）、`consumed`、`remark`；可选 `user_id` |

别名：`hours`/`work_hours`→`consumed`；`work_date`→`date`；`user_name`→`user_id`。

```bash
python3 scripts/api_client.py add_project_task_estimate \
  --param task_id 999 --param consumed 4 --param remark 完成接口开发
```

## Skill 层增强

| CLI / 参数 | 说明 |
|-----------|------|
| `--summarize` | 为支持的读操作附加 `skill_summary` |
| `agent_hints` | 写操作 `dry_run` 返回，提示 Agent 追问话术 |
| `ids` | `confirm_my_work_hours` 批量预览，逗号分隔花费 ID |

摘要支持：`get_work_hours`、`get_unconfirmed_work_hours`、`get_work_hour_statistics`、`get_performance_list`。

## 高价值只读（新增）

| 操作 | 路径 | 说明 |
|------|------|------|
| `get_unconfirmed_work_hours` | `data_export/get_work_hour_detail_list` | 未确认工时，`confirm_status=0` |
| `get_performance_list` | `data_export/get_performance_list` | 月度绩效列表 |
| `get_performance_user` | `data_export/get_performance_user` | 用户绩效详情 |
| `search_user` | `user/get_user_list` | 昵称搜用户（必填 `nick_name`） |
| `get_department_list` | `menu_department/get_dept_list` | 部门列表 |
| `get_dept_members` | `user/get_user_list` | 按 `dept_id`/`dept_name`/`my_team_scope` 列部门成员（含子部门）；**无本地权限范围限制**（登录即可查任意部门） |

`get_dept_members` 参数：

| 参数 | 必填 | 说明 |
|------|------|------|
| `dept_id` / `dept_name` / `my_team_scope` | 三选一 | 部门 ID、部门名称、或 `my_team_scope 1` 解析负责部门 |
| `get_all` | 否 | `1` 时后端返回全部（不分页） |
| `contain_leave` | 否 | `1` 时包含离职人员 |
| `fetch_all` | 否 | Skill 层自动翻页合并 |
| `get_user_project` | `data_export/get_user_project` | 人员项目看板 |
| `get_user_project_panel` | `data_export/get_user_project_panel` | 人员项目面板 |
| `get_scene_group_project` | `data_export/get_scene_group_project` | 场景组项目看板 |
| `get_project_group_info` | `data_export/get_project_group_info` | 产品线/收入类型汇总 |
| `get_last_publish_info` | `project_publish/get_last_publish_info` | 最后递交 |
| `get_publish_normal_const` | `project_publish/get_normal_const` | 递交字典 |
| `get_qa_reject_publish_list` | `produce_demand/get_qa_reject_publish_list` | QA 审批列表 |
| `get_bd_publish_list` | `produce_demand/get_bd_publish_list` | BD 递交列表 |
| `get_publish_demand_pool` | `produce_demand/get_publish_demand_pool` | 可递交需求池 |
| `get_project_moment_stat_chart_list` | `data_export/get_project_moment_stat_chart_list` | 动态图表下钻 |
| `get_employee_estimate_list` | `data_export/get_employee_estimate_list` | 甘特工时下钻 |
| `get_demand_pool_list` | `produce_demand/get_demand_pool_list` | 制作需求池全量 |
| `get_project_demand_pool_list` | `produce_demand/get_project_demand_pool_list` | 项目需求池 |
| `get_outsource_package_dimension_list` | `outsource/get_package_dimension_list` | 外包项目维度 |
| `get_outsource_asset_dimension_list` | `outsource/get_asset_dimension_list` | 外包资产维度 |
| `get_supplier_alert_list` | `supplier_outsource/get_alert_list` | 供应商告警 |
| `get_supplier_accident_list` | `supplier_outsource/get_accident_list` | 供应商事故 |
| `get_my_annual_report` | `annual_report/get_my_report` | 年终/半年报告 |
| `get_latest_report_meta` | `annual_report/get_latest_report_meta` | 报告入口 |
| `get_bug_const` | `bug/get_bug_const` | BUG 字典 |
| `get_project_moment_config_list` | `project_moment/get_config_list` | 动态类型字典 |
| `get_apply_demand_consts` | `produce_demand/get_apply_demand_consts` | 制作需求字典 |

## 写操作（新增）

| 操作 | HTTP | 说明 |
|------|------|------|
| `confirm_user_work_hours` | `POST data_export/estimate_hour_confirm_by_others` | 代确认用户某日工时 |
| `approve_work_hour_batch` | `POST data_export/process_check_by_ids` | 批量审核工时 |
| `add_not_project_estimate` | `POST project_not_task_estimate/add` | **仅非项目**任务工时；`date` 须在任务起止范围内（否则 `estimate_date_out_of_range`）；同一任务同一天仅一条，当日重复 add 返回 `duplicate_estimate`（已确认则 `estimate_confirmed_immutable`） |
| `update_project_task_estimate` | `PUT project_task_estimate/update` | 更新**项目**任务工时；已确认/`estimate_confirmed_immutable`、非当日历史/`estimate_historical_immutable` 不可改 |
| `update_project_moment` | `PUT project_moment/update` | 更新项目动态 |
| `add_bug` | `POST bug/add` | 登记 BUG |
| `apply_publish` | `POST produce_demand/apply_publish` | 申请递交 |
| `reject_publish_apply` | `POST produce_demand/reject_publish` | 驳回递交申请 |
| `start_project_task` | `POST project_task/start` | 开始任务 |
| `finish_project_task` | `POST project_task/finish` | 完成任务 |
| `save_project_overview_value` | `POST project_overview/save_value` | 保存项目价值 |
| `add_not_project_demand` | `POST project_not_task/add` | 新增非项目需求 |
| `add_not_project_task` | `POST project_not_task/add_task` | 新增非项目任务 |
| `finish_not_project_task` | `POST project_not_task/finish_task` | 完成非项目任务 |
| `update_not_project_estimate` | `PUT project_not_task_estimate/update` | 更新非项目任务工时；已确认或历史不可改 |
| `add_apply_demand` | `POST produce_demand/add_apply_demand` | 新增申请制作需求 |
| `add_demand_pool` | `POST produce_demand/add_demand_pool` | 拆解新增制作需求池 |
| `add_feedback_demand_pool` | `POST produce_demand/add_demand_pool` | 新增反馈类需求池（`demand_type=反馈`） |
| `approve_publish_apply` | `POST project_publish/add` | 通过递交申请并排期 |

批量确认预览：

```bash
python3 scripts/api_client.py confirm_my_work_hours \
  --param ids 101,102,103 --param confirm_type 项目
```
