---
name: pm-platform-api
label: 项目管理平台API
description: "对接项目管理平台 API。当用户提到工时统计、工作日报、生成工作总结、本周/今日工作汇总，或按人员/部门查询工时时触发。"
---

# 项目管理平台 API

通过本 Skill 调用 51PM 工时接口，获取原始 JSON 后由你完成汇总与工作总结。不要编造未返回的数据。

## 可用操作

使用 CLI：

```bash
python3 scripts/api_client.py --list-ops
python3 scripts/api_client.py get_work_hours --param KEY VALUE
```

接口细节见 `references/api_docs.md`。

## 意图 → 操作映射

| 用户意图 | 操作 | 编排 | 分析方向 |
|---------|------|------|---------|
| 生成工作总结 / 日报 | `get_work_hours` | 单步；日期默认本周一～今天（用户说「今日」则用当天）；可带 `user_name` / `dept_name` | 按项目汇总工时，按日排列，提炼重点任务与备注 |
| 查某人/某部门工时 | `get_work_hours` | 单步；必须带人或部门（名或 ID） | 按日/项目列表，合计总工时 |

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

## 工作总结输出结构

1. **概览**：时间范围、人员/部门、总工时、涉及项目数
2. **按项目**：各项目工时合计 + 主要任务
3. **按日期**：每日要点（任务 + 工时）
4. **备注与风险**：未确认工时（`confirm_status`）、进度偏低项（若有）

## 扩展

新增接口时同步更新：`scripts/api_client.py` 的 `OPERATIONS`、`references/api_docs.md`、本文件的意图映射与 description。
