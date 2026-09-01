---
name: pm-platform-api
label: 项目管理平台API
description: "对接项目管理平台 API。当用户提到工时/日报、项目/非项目、健康度、BUG、递交、成本、产能、外包供应商、报价单、排期甘特，或按项目/人员/部门统计时触发。"
---

# 项目管理平台 API

通过本 Skill 调用 51PM 工时接口，获取原始 JSON 后由你完成汇总与工作总结。不要编造未返回的数据。

## 可用操作

使用 CLI：

```bash
python3 scripts/api_client.py --list-ops
python3 scripts/api_client.py --list-ops-grouped
python3 scripts/api_client.py get_work_hours --param KEY VALUE
python3 scripts/api_client.py get_bug_list --fetch-all --param project_name 某某展厅
```

接口细节见 `references/api_docs.md`。`--list-ops-grouped` 按业务模块分组列出全部 **130** 个操作（含 **22** 个写操作）。

## 意图 → 操作映射

| 用户意图 | 操作 | 编排 | 分析方向 |
|---------|------|------|---------|
| 生成工作总结 / 日报 | `get_work_hours` | 单步；日期默认本周一～今天（用户说「今日」则用当天）；可带 `user_name` / `dept_name` | 按项目汇总工时，按日排列，提炼重点任务与备注 |
| 查某人/某部门工时 | `get_work_hours` | 单步；必须带人或部门（名或 ID） | 按日/项目列表，合计总工时 |
| 查项目列表（按 PM/组/状态等） | `get_project_list` | 单步；友好参数自动转平台字段 | 列表展示名称、商机号、PM、阶段、进度、工时等 |
| 查我参与的项目 | `get_my_projects` | 单步；不传 `user_name` 则用 API Key 对应账号；可传 `user_name` 查他人 | 列出相关项目及面板汇总 |
| 查项目详情 | `get_project_info` | 单步；传 `project_name` / `sj_num` / `id` | 展示项目基本信息、人员、进度等 |
| 查某项目下的工时列表 | `get_project_work_hours` | 单步；必须带项目（`project_name`/`sj_num`/`project_id`）；可带日期范围 | 按任务/人员列出花费明细 |
| 工时数据总览（可按项目筛） | `get_work_hour_statistics` | 单步；必填日期；可带 `project_name`/`user_name`/`dept_name` | 总工时、项目/非项目占比、TOP5 等 |
| 工时下钻明细（可按项目筛） | `get_work_hour_detail_list` | 单步；必填日期；可带项目/人员/部门/产出类型 | 逐条工时明细列表 |
| 项目健康度/体检 | `get_project_overview_*` | 单步；带 `project_name`/`sj_num`；按意图选子接口 | KPI、成本、质量、人员、风险等 |
| 项目递交情况 | `get_project_overview_deliver` | 同项目全景 | 递交进度、延期、临时递交 |
| QA 递交统计 | `get_qa_stat_publish` | 必填 `period_type`+`period_key`；可加部门/人 | 递交准时率、延期清单 |
| 项目动态/会议/风险/问题 | `get_project_moment_*` | 周期类带 `period_type`+`period_key`；可加项目/PM/部门 | 动态 KPI、明细列表 |
| BUG 查询 | `get_bug_list` / `get_bug_info` | 列表可带 `project_name`→`sj_num`、人员筛选 | 未关闭 BUG、指派人、等级 |
| QA 质量看板 | `get_qa_stat_kpi` / `bug` / `summary` | 必填周期；可加部门/PM/测试 | KPI、BUG 维度、周期总结 |
| 项目成本/超支 | `get_project_cost_*` | 看板需周期；明细需项目商机号 | 健康度、超支明细、成本列表 |
| 部门产能/剩余工时 | `get_dept_capacity_panel` / `get_dept_left_hour_*` | 产能面板可带 `dept_name`+日期；下钻需 `dept_key`+`status` | 产能利用率、待消耗人天 |
| 递交台账明细 | `get_publish_list` / `get_publish_info` | 可按 PM/状态/日期筛选 | 递交版本、是否超 TB、延期 |
| 递交申请 | `get_apply_publish_list` | 可带 `project_name`、申请状态、日期 | 待审批/已审批申请 |
| 项目任务/需求 | `get_task_list` / `get_task_info` | 列表必填项目；可 `assigned_to_me` | 未完成任务、指派人 |
| 全局风险面板 | `get_project_risk_panel` | 可按 PM/商机号/风险等级 | 高风险项目、未解决风险 |
| 项目复盘 | `get_project_review_panel` | 可按项目/PM/测试/日期 | 复盘得分、待办、经验 |
| ECP 项目动态 | `get_project_change_info` | 商机号+日期范围 | ECP 每日变更记录 |
| 交付形态 | `get_project_delivery_type_panel` | 可选年份、`is_wdp` | WDP 订阅占比等 |
| 人力排期/甘特 | `get_total_schedule_list` / `get_employee_project_*` | 部门/人员+日期 | 排期负荷、甘特图 |
| 工时填报矩阵 | `get_all_times_list` | 日期+部门/人员 | 缺报/填报矩阵 |
| QA 周期目标 | `get_qa_stat_period_target` | 必填 `period_type`+`period_key` | 准时率/BUG 降幅目标 |
| 项目报价单 | `get_project_quotation_list` | 必填项目（`project_name`/`sj_num`） | 报价明细、成本/标准价汇总 |
| ECP 报价项目录 | `get_ecp_baojia_list` / `get_ecp_baojia_const` | 可按版本/模块/业务线筛选 | 报价项字典、模块版本 |
| 外包报价单 | `get_outsource_quotation_list` | 可带 `package_id`/`supplier_id` | 模型外包报价金额、状态 |
| 非项目列表/工时 | `get_not_project_*` | `not_project_name`→`project_id` | 非项目需求、任务、工时花费 |
| 模型外包发包 | `get_outsource_package_*` / `get_outsource_data_overview` | 可带 `sj_num`/`pm_name` | 发包进度、结算、数据总览 |
| 供应商外包看板 | `get_supplier_outsource_*` | 场景组/供应商/日期 | 台账、画像、能力矩阵 |
| 供应商档案 | `get_supplier_list` / `get_supplier_detail` | 公司名称关键字 | 供应商基础信息 |
| 确认工时花费 | `confirm_my_work_hours` | **写** 两阶段：先 `dry_run` 预览，用户确认后再 `confirm=1` | 确认项目/非项目工时 |
| 新增项目动态 | `add_project_moment` | **写** 两阶段；`module` 可用 会议/风险/问题 | 登记会议、风险、问题 |
| 登记任务工时 | `add_project_task_estimate` | **写** 两阶段；必填 `task_id`+`consumed`+`remark` | 填报项目任务花费 |
| 未确认工时 | `get_unconfirmed_work_hours` | 本月默认；可 `--summarize` | 待确认工时清单 |
| 月度绩效 | `get_performance_list` / `get_performance_user` | 必填日期范围 | 绩效审核进度/详情 |
| 人员/部门 | `search_user` / `get_department_list` | 昵称搜索 | 解析 user_id/dept_id |
| 人员项目看板 | `get_user_project` / `get_scene_group_project` | `type` 可用 开发/设计/项目经理 等 | 岗位负荷分布 |
| 递交扩展 | `get_qa_reject_publish_list` / `get_bd_publish_list` / `get_publish_demand_pool` | 审批/BD/需求池 | 递交闭环 |
| 字典常量 | `get_bug_const` / `get_publish_normal_const` / `get_project_moment_config_list` / `get_apply_demand_consts` | 写操作前预取 | 减少 type/status 猜测 |
| 代确认/批量审核工时 | `confirm_user_work_hours` / `approve_work_hour_batch` | **写** 两阶段 | PM 确认下属工时 |
| 非项目/更新工时 | `add_not_project_estimate` / `update_project_task_estimate` | **写** | 与非项目/项目读接口闭环 |
| 非项目需求/任务 | `add_not_project_demand` / `add_not_project_task` / `finish_not_project_task` / `update_not_project_estimate` | **写** 两阶段 | 非项目闭环 |
| 制作需求/反馈 | `add_apply_demand` / `add_demand_pool` / `add_feedback_demand_pool` | **写** 两阶段；可先 `get_apply_demand_consts` | 申请制作需求、拆解需求池、新增反馈 |
| 递交通过 | `approve_publish_apply` | **写** 两阶段 | 通过递交申请并排期 |
| 登记 BUG / 申请递交 | `add_bug` / `apply_publish` / `reject_publish_apply` | **写**；BUG 可先 `get_bug_const` | QA/PM 日常操作 |

## Skill 层增强

### 结果摘要（`skill_summary`）

对 `get_work_hours`、`get_unconfirmed_work_hours`、`get_work_hour_statistics`、`get_performance_list` 等操作，加 `--summarize`（或操作元数据 `summarize: true`）会在 JSON 中附加 `skill_summary`（总工时、TOP 项目、未确认数等），便于直接生成工作总结。

### 字典预取

写 BUG/动态/递交前，可先调用：

- `get_bug_const` — BUG 类型/状态/等级
- `get_project_moment_config_list` — 动态子类型
- `get_publish_normal_const` — 递交状态/版本
- `get_apply_demand_consts` — 制作需求模块/类型

### 写操作预览增强

`dry_run` 响应除 `warnings` 外含 `agent_hints`，提示 Agent 应向用户追问的字段（如缺 `user_name`、`risk_level`）。

### 批量工时确认预览

`confirm_my_work_hours` 支持 `--param ids 1,2,3`，返回 `batch: true` 与多条 `items`（每条独立 `confirm_token`）。

### 多步编排模板（补充）

| 场景 | 步骤 |
|------|------|
| **工时确认闭环** | `get_unconfirmed_work_hours --summarize` → 用户确认 → `confirm_my_work_hours`（或主管 `confirm_user_work_hours`） |
| **递交审批闭环** | `get_apply_publish_list` → `get_qa_reject_publish_list` → `approve_publish_apply` / `reject_publish_apply` |
| **制作需求闭环** | `get_apply_demand_consts` → `add_apply_demand` → `add_demand_pool` / `add_feedback_demand_pool` |
| **非项目闭环** | `get_not_project_list` → `add_not_project_demand` → `add_not_project_task` → `add_not_project_estimate` |
| **登记 BUG** | `get_bug_const` → `add_bug`（dry_run）→ confirm |
| **项目价值维护** | `get_project_overview_value` → 编辑 rows → `save_project_overview_value` |

## 写操作交互协议

写操作（`write: true`）**禁止**在未预览的情况下直接 `confirm=1`。默认行为等价于 `dry_run=1`：解析参数、校验、返回 `summary` + `confirm_token`，由你向用户展示预览并征求确认。

### 流程

1. **预览**：`dry_run=1`（默认，或 CLI `--dry-run`）→ 返回 `dry_run: true`、`summary`、`resolved_body`、`confirm_token`、`warnings`
2. **向用户说明**：用自然语言复述 `summary`；若有 `warnings` 一并提示（如缺 `user_id`、`risk_level`）
3. **用户确认后执行**：相同业务参数 + `confirm=1` + `confirm_token`（CLI `--confirm --param confirm_token ...`）
4. **跳过确认**（仅用户明确要求直接提交时）：`force=1`

### 试点写操作

| 操作 | 场景 | 关键参数 |
|------|------|---------|
| `confirm_my_work_hours` | 确认待确认工时 | `id`（或 `estimate_id`）+ `confirm_type`（`项目`/`非项目` 或 `ConfirmTaskEstimate`/`ConfirmNotTaskEstimate`） |
| `add_project_moment` | 新增会议/风险/问题动态 | `project_name`/`sj_num` + `module` + `content` + `type` + `user_name`（多人逗号分隔）；风险/问题建议带 `risk_level` |
| `add_project_task_estimate` | 登记任务工时 | `task_id` + `consumed` + `remark`；可选 `date`（默认今天）、`user_name` |

### 对话示例

用户：「帮我把工时 12345 确认了，是项目工时。」

```bash
# 1. 预览（Agent 内部先执行，向用户展示结果）
python3 scripts/api_client.py confirm_my_work_hours \
  --param id 12345 --param confirm_type 项目

# 2. 用户说「确认」后
python3 scripts/api_client.py confirm_my_work_hours \
  --confirm --param id 12345 --param confirm_type 项目 \
  --param confirm_token <上一步返回的 token>
```

用户：「在某某展厅项目记一条风险：接口延期，负责人张三。」

```bash
python3 scripts/api_client.py add_project_moment \
  --param project_name 某某展厅 --param module 风险 \
  --param content 接口延期 --param type 技术风险 \
  --param risk_level 高 --param user_name 张三
```

若预览 `warnings` 提示缺字段，先追问用户补全，再重新 `dry_run`，不要带着无效 token 强行 `confirm`。

## Skill 层增强

### 周期自然语言

QA/成本等周期接口可直接传 `period`（或把自然语言写在 `period_key`）：

| 用户说法 | 解析结果 |
|---------|---------|
| 本月 / 上月 | `month` + `YYYY-MM` |
| 本周 / 上周 | `week` + `YYYY-Www` |
| 本季 / 本季度 | `quarter` + `YYYY-Qn` |
| 今年 / 去年 | `year` + `YYYY` |
| Q3 2026 / 2026-Q3 | `quarter` + `2026-Q3` |

示例：`--param period 本月` 等价于 `--param period_type month --param period_key 2026-09`。

### 自动翻页

列表类接口支持 `--fetch-all`（或 `--param fetch_all 1`），自动合并多页 `data`/`list` 数组（最多 50 页）。

### 多步编排模板

| 场景 | 步骤 |
|------|------|
| **项目体检** | `get_project_overview_header` → `req_cost` → `quality` → `deliver` → `risk` |
| **部门周报** | `get_dept_capacity_panel` + `get_qa_stat_summary`（`period` 本周/本月） |
| **递交闭环** | `get_apply_publish_list` → `get_publish_list` → `get_qa_stat_publish` |
| **非项目工时** | `get_not_project_list` → `get_not_project_work_hours` |
| **外包发包** | `get_outsource_package_list` → `get_outsource_package_detail` → `get_outsource_settlement_list` |
| **供应商评估** | `get_supplier_outsource_board` → `get_supplier_outsource_profile` |

编排时前一步返回的 `id`/`sj_num`/`package_id` 应传给下一步，不要编造。

## 编排规则

1. 从用户话中抽取：起止日期、人名、部门名。缺日期时：本周一～今天；明确「今日/今天」则起止均为当天。
2. 优先传 `user_name` / `dept_name`，不要猜测数字 ID。
3. 执行示例：

```bash
python3 scripts/api_client.py get_work_hours \
  --param start_date 2026-08-03 \
  --param end_date 2026-08-06 \
  --param user_name 张三
```

按部门：

```bash
python3 scripts/api_client.py get_work_hours \
  --param start_date 2026-08-01 \
  --param end_date 2026-08-06 \
  --param dept_name 研发部
```

4. 若返回 JSON 含 `error` 字段：向用户说明原因（配置缺失、人名/部门找不到、鉴权失败、网络错误等），不要编造工时数据。
5. 成功时只基于返回的 `data` 分析，数字必须能追溯到原始字段（如 `consumed`、`task_name`、`name`）。

### 项目查询编排

**原则**：用户自然语言中的筛选条件，优先映射为下表「友好别名」；平台 ID 字段与 `*_name` 同时存在时以 ID 为准；不要猜测数字 ID。

#### get_project_list（全量项目筛选）

| 用户意图 | 推荐传参 |
|---------|---------|
| 按项目名称 | `project_name` 或 `name` |
| 按商机号 | `sj_num` / `opportunity_no` / `business_no` |
| 按项目经理 | `pm_name` |
| 按开发/测试/BD/UI/美术/技术/Web | `develop_name` / `tester_name` / `bd_name` / `ui_name` / `scene_duty_name` / `tech_name` / `web_dev_name` |
| 按区域/制作组 | `group_name` / `team_name` / `region_team` / `ecp_group` / `make_team` |
| 按 ECP 阶段/状态 | `stage` / `project_stage` / `status` / `ecp_stage` |
| 按项目进度 | `process` / `progress` / `project_process` |
| 按风险等级 | `risk` / `risk_level` |
| 按事业部 | `business_unit` / `shi_ye_bu` / `ecp_shi_ye_bu` |
| 按商机行业 | `industry_type` / `hang_ye_lei_xing` / `ecp_industry` |
| 按制作组/场景 | `scene` / `make_group` / `project_scene` |
| 按 DTA 资产 | `dta` / `project_dta` |
| 按开工日期范围 | `kaigong_start` + `kaigong_end`（或 `kaigong_date_start` / `kaigong_date_end`） |
| 按 ECP 开工令时间 | `ecp_kaigong_date` / `kaigong_ling_date` |
| 按营收时间/状态 | `revenue_date` / `income_date`；`income_status` / `is_income` |
| 仅含离职人员项目 | `only_resigned` / `only_lizhi` = `1` |

#### get_my_projects（我参与的项目）

| 用户意图 | 推荐传参 |
|---------|---------|
| 我参与的 | 不传 `user_name` |
| 某人参与的 | `user_name` |
| 按名称/商机号/状态/开工日期 | `project_name`、`opportunity_no`、`stage`、`kaigong_start`、`kaigong_end` 等（见 `api_docs.md`） |

#### get_project_info（项目详情）

传 `project_name` / `name` / `sj_num` / `opportunity_no` / `id` 之一即可。

#### 项目下工时查询

| 用户意图 | 操作 | 推荐传参 |
|---------|------|---------|
| 某项目花了多少工时（明细） | `get_project_work_hours` | `project_name` 或 `sj_num` + 可选 `start_date`/`end_date` |
| 某项目工时汇总/占比/排行 | `get_work_hour_statistics` | 日期 + `project_name`/`project_ids`；可加 `user_name`/`dept_name` |
| 某项目逐条工时明细（下钻） | `get_work_hour_detail_list` | 日期 + `project_name`/`project_ids`；可加 `output_type`（产出/非产出） |

通用别名（三个操作均适用，见 `api_docs.md`）：

- 日期：`date_start`/`from_date` → `start_date`；`date_end`/`to_date` → `end_date`
- 项目：`project_name`/`name`/`sj_num`/`opportunity_no` → `project_id` 或 `project_ids`
- 人员/部门：`user_name` → `user_ids`；`dept_name` → `dept_id`
- 确认状态：`待确认`/`已确认`/`全部` → `confirm_status`
- 项目类型：`项目`/`非项目`/`全部` → `project_type`
- 产出类型：`产出`/`非产出` → `output_type`（仅明细接口）

示例：

```bash
# 某项目下的工时花费列表
python3 scripts/api_client.py get_project_work_hours \
  --param project_name 某某展厅 \
  --param start_date 2026-08-01 \
  --param end_date 2026-08-31

# 按项目统计工时总览
python3 scripts/api_client.py get_work_hour_statistics \
  --param start_date 2026-08-01 \
  --param end_date 2026-08-31 \
  --param sj_num SJ20240001

# 项目工时下钻明细
python3 scripts/api_client.py get_work_hour_detail_list \
  --param start_date 2026-08-01 \
  --param end_date 2026-08-31 \
  --param project_name 某某展厅 \
  --param output_type 产出
```

### 项目健康度（`get_project_overview_*`）

均需项目标识（`project_name` / `sj_num` / `project_id`）：

| 操作 | 场景 |
|------|------|
| `get_project_overview_header` | 身份卡、核心 KPI、成本预警 |
| `get_project_overview_req_cost` | 需求人天、超支、变更成本 |
| `get_project_overview_quality` | BUG 分布、反馈验收 |
| `get_project_overview_deliver` | 递交进度、延期 |
| `get_project_overview_people` | 人员投入、工时成本 |
| `get_project_overview_risk` | 风险与执行问题全量 |
| `get_project_overview_value` | 项目价值 |
| `get_project_overview_req_detail` | 需 `chart_key`（nature/task_day） |
| `get_project_overview_quality_detail` | 需 `chart_key` + `option` |

### 项目动态（`get_project_moment_*`）

- 统计看板：`get_project_moment_stat`（必填 `period_type`+`period_key`，如 `week`+`2026-W35`）
- 明细列表：`get_project_moment_stat_list` / `get_project_moment_stat_detail`
- 单项目列表：`get_project_moment_list`（`module` 可用 `会议`/`风险`/`问题`）
- 动态详情：`get_project_moment_info`（`id` 或 `moment_id`）

### BUG 与 QA / 递交

```bash
# 某项目 BUG
python3 scripts/api_client.py get_bug_list --param project_name 某某展厅

# QA 递交维度（本月）
python3 scripts/api_client.py get_qa_stat_publish \
  --param period_type month --param period_key 2026-08 --param dept_name 研发部
```

周期参数：`period_type` 支持 `week`/`month`/`quarter`/`half`/`year`（或中文 周/月/季/半年/年）。

### 项目成本

```bash
# 成本看板
python3 scripts/api_client.py get_project_cost_stat \
  --param period_type month --param period_key 2026-08 --param group_name 华东组

# 单项目成本明细
python3 scripts/api_client.py get_project_cost_stat_list --param sj_num SJ20240001
```

### 部门产能

```bash
python3 scripts/api_client.py get_dept_capacity_panel \
  --param dept_name 研发部 --param start_date 2026-08-01 --param end_date 2026-08-07

python3 scripts/api_client.py get_dept_left_hour_panel

python3 scripts/api_client.py get_dept_left_hour_demand_list \
  --param dept_key sceneA --param status doing
```

### 递交台账与申请

```bash
# 递交台账（本月、某 PM）
python3 scripts/api_client.py get_publish_list \
  --param pm_name 张三 --param start_date 2026-08-01 --param end_date 2026-08-31

# 递交详情
python3 scripts/api_client.py get_publish_info --param publish_id 12345

# 递交申请列表
python3 scripts/api_client.py get_apply_publish_list \
  --param project_name 某某展厅 --param apply_status 待审批
```

### 项目任务

```bash
python3 scripts/api_client.py get_task_list \
  --param project_name 某某展厅 --param assigned_to_me 1

python3 scripts/api_client.py get_task_info --param task_id 999
```

### 风险 / 复盘 / ECP / 排期

```bash
python3 scripts/api_client.py get_project_risk_panel --param risk_level 高
python3 scripts/api_client.py get_project_review_panel --param pm_name 张三
python3 scripts/api_client.py get_project_change_info --param sj_num SJ20240001
python3 scripts/api_client.py get_employee_project_list \
  --param dept_name 研发部 --param start_date 2026-08-01 --param end_date 2026-08-07
python3 scripts/api_client.py get_all_times_list \
  --param start_date 2026-08-01 --param end_date 2026-08-31 --param dept_name 研发部
python3 scripts/api_client.py get_qa_stat_period_target \
  --param period_type month --param period_key 2026-08
```

### 报价单

```bash
# 某项目 ECP 报价单
python3 scripts/api_client.py get_project_quotation_list \
  --param project_name 某某展厅

# ECP 报价项目录
python3 scripts/api_client.py get_ecp_baojia_list --param ywx 数字娱乐
python3 scripts/api_client.py get_ecp_baojia_const

# 模型外包报价
python3 scripts/api_client.py get_outsource_quotation_list \
  --param package_id 1001 --param status 1
```

### 非项目工时

```bash
python3 scripts/api_client.py get_not_project_list
python3 scripts/api_client.py get_not_project_work_hours \
  --param not_project_name 内部运营 --param start_date 2026-08-01 --param end_date 2026-08-31
python3 scripts/api_client.py get_not_project_demand_list --param not_project_name 内部运营
```

### 外包 / 供应商

```bash
python3 scripts/api_client.py get_outsource_package_list --param pm_name 张三
python3 scripts/api_client.py get_outsource_data_overview --param sj_num SJ20240001
python3 scripts/api_client.py get_supplier_outsource_work_ledger \
  --param start_date 2026-08-01 --param end_date 2026-08-31
python3 scripts/api_client.py get_supplier_outsource_profile --param supplier_id 12
python3 scripts/api_client.py get_supplier_list --param company_name 某某科技
```

#### get_project_list / get_my_projects（项目筛选）

```bash
# 查某 PM 负责、华东组、制作中的项目
python3 scripts/api_client.py get_project_list \
  --param pm_name 张三 \
  --param group_name 华东组 \
  --param stage 制作中

# 按事业部 + 营收状态
python3 scripts/api_client.py get_project_list \
  --param business_unit 数字娱乐 \
  --param income_status 1

# 我参与的项目（带筛选）
python3 scripts/api_client.py get_my_projects --param stage 制作中

# 某人参与的项目
python3 scripts/api_client.py get_my_projects --param user_name 李四

# 项目详情（多种入参等价）
python3 scripts/api_client.py get_project_info --param sj_num SJ20240001
python3 scripts/api_client.py get_project_info --param project_name 某某展厅
```

## 工作总结输出结构

1. **概览**：时间范围、人员/部门、总工时、涉及项目数
2. **按项目**：各项目工时合计 + 主要任务
3. **按日期**：每日要点（任务 + 工时）
4. **备注与风险**：未确认工时（`confirm_status`）、进度偏低项（若有）

## 扩展

新增接口时同步更新：`scripts/api_client.py` 的 `OPERATIONS`、`references/api_docs.md`、本文件的意图映射与 description。
