---
name: pm-fill-hours
label: 51PM 填工时
description: "对接 51PM 项目管理平台，按飞书会话用户多轮填写项目/非项目工时。当用户提到填工时、报工、登记工时、提交工时、记录今天干了多少小时时触发。"
---

# 51PM 填工时

按当前飞书会话用户，为其 51PM 账号填写项目或非项目任务工时。通过 CLI 调用 `fill_hours_step`，根据返回的 `status` 多轮追问，直到提交成功。不要编造未返回的数据。

## 可用操作

```bash
python3 scripts/api_client.py --list-ops
python3 scripts/api_client.py fill_hours_step --param KEY VALUE
```

接口细节见 `references/api_docs.md`。

## 多轮编排

1. **取 `feishu_open_id`**：从 Aily 当前会话上下文获取飞书 open_id，每次调用 `fill_hours_step` 都必须传入 `--param feishu_open_id <open_id>`。
2. **首轮调用**：从用户话中抽取 `consumed`（工时）、`remark`（备注）、`date`（默认今天 `YYYY-MM-DD`）、`task_kind`（`project` / `not_project`，可选）。能确定的参数一并传入。
3. **按 `status` 处理**：
   - **`need_input`**：向用户展示 `next_question`；若含 `task_options`，以序号列表展示（序号、`name`、`project_name`、`task_kind`）。用户回复后，将对应字段写入 `--param` 再次调用（选任务时传 `task_id` 与 `task_kind`）。
   - **`submitted`**：向用户确认填报成功，可简述 `collected` 中的任务、日期、工时与备注。
4. **缺参顺序**（脚本内部）：先选任务（`task_id`），再 `task_kind` / `consumed` / `remark`。Aily 应优先帮用户补齐当前 `missing_fields` 中的第一项。
5. **错误**：若 stdout 为含 `error` 字段的 JSON（退出码非 0），向用户说明 `detail`，不要假装已提交。

## 调用示例

仅 open_id（脚本会返回待选任务列表）：

```bash
python3 scripts/api_client.py fill_hours_step \
  --param feishu_open_id ou_xxxxxxxx
```

补齐参数后提交：

```bash
python3 scripts/api_client.py fill_hours_step \
  --param feishu_open_id ou_xxxxxxxx \
  --param task_id 123 \
  --param task_kind project \
  --param date 2026-08-07 \
  --param consumed 2 \
  --param remark 联调接口
```

## 配置

超管 `base_url` / `api_key` 用于 open_id 解析与 impersonate，见 `scripts/config.example.json` → 复制为 `scripts/config.json`（勿提交 Git）。环境变量 `PM_PLATFORM_*` 优先于配置文件。

## 扩展

新增操作或字段时同步更新：`scripts/api_client.py`、`references/api_docs.md`、本文件的编排说明与 description。
