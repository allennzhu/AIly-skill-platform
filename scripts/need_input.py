"""Structured missing-parameter feedback for Aily Agent — ask user, don't guess."""

from __future__ import annotations

from datetime import date
from typing import Any

PARAM_LABELS: dict[str, str] = {
    "start_date": "开始日期",
    "end_date": "结束日期",
    "date": "日期",
    "period_type": "统计周期类型",
    "period_key": "统计周期",
    "user_name": "用户昵称",
    "user_id": "用户 ID",
    "dept_name": "部门名称",
    "dept_id": "部门 ID",
    "my_team_scope": "我们组/我团队范围（负责人含子部门）",
    "team_scope": "我们组/我团队范围",
    "project_name": "项目名称",
    "project_id": "项目 ID",
    "sj_num": "商机号",
    "pm_name": "项目经理",
    "publish_id": "递交 ID",
    "task_id": "任务 ID",
    "bug_id": "BUG ID",
    "chart_key": "图表类型",
    "module": "模块",
    "type": "类型",
    "status": "状态",
    "keywords": "关键词",
}

PARAM_HINTS: dict[str, str] = {
    "start_date": "格式 YYYY-MM-DD，例如 2026-08-01",
    "end_date": "格式 YYYY-MM-DD，例如 2026-08-31",
    "period_type": "可选：day / week / month / quarter / year",
    "period_key": "与 period_type 对应，例如 month 填 2026-08",
    "chart_key": "见 get_qa_stat_period_target 或接口文档",
}

DATE_PARAMS = frozenset({"start_date", "end_date", "date"})


def _field_type(name: str) -> str:
    if name in DATE_PARAMS:
        return "date"
    if name.endswith("_id") or name in {"page", "limit"}:
        return "number"
    if name in {"period_type", "status", "chart_key", "module", "type"}:
        return "select"
    return "text"


def _example_value(name: str) -> str:
    today = date.today().isoformat()
    if name == "start_date":
        return today[:8] + "01"
    if name == "end_date":
        return today
    if name == "period_type":
        return "month"
    if name == "period_key":
        return today[:7]
    return ""


def build_need_input_payload(
    operation: str,
    meta: dict[str, Any],
    *,
    missing_fields: list[str],
    message: str = "",
    provided: dict[str, Any] | None = None,
    one_of_groups: list[list[str]] | None = None,
) -> dict[str, Any]:
    """Build JSON for Agent to present a form or ask the user directly."""
    provided = dict(provided or {})
    desc = str(meta.get("description") or operation)
    fields: list[dict[str, Any]] = []

    if one_of_groups:
        for group in one_of_groups:
            label = " / ".join(PARAM_LABELS.get(k, k) for k in group)
            fields.append(
                {
                    "name": group[0],
                    "label": f"以下填一项即可：{label}",
                    "type": "one_of",
                    "options": [
                        {"value": k, "label": PARAM_LABELS.get(k, k)}
                        for k in group
                    ],
                    "required": True,
                }
            )
    else:
        for key in missing_fields:
            fields.append(
                {
                    "name": key,
                    "label": PARAM_LABELS.get(key, key),
                    "type": _field_type(key),
                    "required": True,
                    "hint": PARAM_HINTS.get(key, ""),
                    "example": _example_value(key),
                }
            )

    example_parts = [f"--param {k} <值>" for k in (missing_fields[:3] or ["KEY", "VALUE"])]
    return {
        "error": "need_input",
        "operation": operation,
        "description": desc,
        "message": message or f"缺少必填信息，请向用户确认以下内容后重试（不要自行猜测或查源码）",
        "missing_fields": missing_fields,
        "form": fields,
        "provided": provided,
        "next_step": "把 form 中的问题直接发给用户；收到回答后带 --param 重试同一条命令",
        "example_command": (
            f"python3 scripts/api_client.py {operation} "
            + " ".join(example_parts)
        ),
    }


def _param_satisfied(params: dict[str, Any], key: str) -> bool:
    if params.get(key) not in (None, ""):
        return True
    if key == "dept_name" and params.get("dept_id") not in (None, ""):
        return True
    if key == "my_team_scope" and str(params.get("my_team_scope") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "是",
    ):
        return True
    if key == "user_name" and any(
        params.get(k) not in (None, "", [])
        for k in ("user_id", "user_ids", "assignee_name", "assigned_to_me")
    ):
        return True
    return False


def collect_missing_required(
    meta: dict[str, Any], params: dict[str, Any]
) -> tuple[list[str], list[list[str]]]:
    """Return (missing_all_required, one_of_groups_that_failed)."""
    missing: list[str] = []
    one_of_failed: list[list[str]] = []

    one_of = list(meta.get("required_one_of", []) or [])
    if one_of and not any(_param_satisfied(params, key) for key in one_of):
        one_of_failed.append(one_of)

    if meta.get("required_any"):
        if not any(params.get(key) for key in meta.get("required", [])):
            missing.extend(list(meta.get("required", [])))
    elif meta.get("required_any_not_project"):
        keys = (
            "not_project_id",
            "not_project_name",
            "name",
            "project_id",
        )
        if not any(params.get(key) for key in keys):
            missing.extend(list(keys))
    elif meta.get("required_any_project"):
        keys = (
            "project_id",
            "project_name",
            "name",
            "sj_num",
            "opportunity_no",
            "business_no",
        )
        if not any(params.get(key) for key in keys):
            missing.extend(list(keys))
    elif not one_of:
        for key in meta.get("required", []):
            if params.get(key) in (None, ""):
                missing.append(key)

    skip_required = set(one_of)
    for key in meta.get("required", []):
        if key in skip_required:
            continue
        if params.get(key) in (None, ""):
            if key not in missing:
                missing.append(key)

    return missing, one_of_failed
