"""Skill-layer helpers: period NL parsing, pagination merge, operation grouping."""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any


def _today() -> date:
    return date.today()


def _month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _quarter_key(d: date) -> str:
    q = (d.month - 1) // 3 + 1
    return f"{d.year:04d}-Q{q}"


def _week_key(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso.year:04d}-W{iso.week:02d}"


def _looks_natural_period(text: str) -> bool:
    lowered = text.strip().lower()
    if re.fullmatch(r"\d{4}-\d{2}", lowered):
        return False
    if re.fullmatch(r"\d{4}-w\d{2}", lowered):
        return False
    if re.fullmatch(r"\d{4}-q[1-4]", lowered):
        return False
    if re.fullmatch(r"\d{4}", lowered):
        return False
    return any(
        token in text
        for token in (
            "本月",
            "上月",
            "本周",
            "上周",
            "本季",
            "本季度",
            "今年",
            "去年",
            "半年",
        )
    ) or bool(re.search(r"Q[1-4]", text, re.I))


def _parse_period_label(label: str) -> tuple[str | None, str | None]:
    text = label.strip()
    lowered = text.lower()
    today = _today()

    if text in ("本月", "这个月"):
        return "month", _month_key(today)
    if text in ("上月", "上个月"):
        prev = today.replace(day=1) - timedelta(days=1)
        return "month", _month_key(prev)
    if text in ("本周", "这周"):
        return "week", _week_key(today)
    if text in ("上周", "上星期"):
        return "week", _week_key(today - timedelta(days=7))
    if text in ("本季", "本季度", "这个季度"):
        return "quarter", _quarter_key(today)
    if text in ("今年",):
        return "year", f"{today.year:04d}"
    if text in ("去年",):
        return "year", f"{today.year - 1:04d}"
    if text in ("半年", "本半年"):
        half = 1 if today.month <= 6 else 2
        return "half", f"{today.year:04d}-H{half}"

    m = re.fullmatch(r"(?i)q([1-4])\s*[-/]?\s*(\d{4})", text)
    if m:
        return "quarter", f"{m.group(2)}-Q{m.group(1)}"
    m = re.fullmatch(r"(?i)(\d{4})\s*[-/]?\s*q([1-4])", text)
    if m:
        return "quarter", f"{m.group(1)}-Q{m.group(2)}"

    if re.fullmatch(r"\d{4}-\d{2}", text):
        return "month", text
    if re.fullmatch(r"(?i)\d{4}-w\d{2}", text):
        return "week", text.upper().replace("W", "-W") if "-w" in lowered else text
    if re.fullmatch(r"(?i)\d{4}-q[1-4]", text):
        parts = text.upper().split("-")
        return "quarter", f"{parts[0]}-{parts[1]}"
    if re.fullmatch(r"\d{4}", text):
        return "year", text

    return None, None


def apply_period_natural_language(params: dict[str, Any]) -> dict[str, Any]:
    out = dict(params)
    label = out.pop("period", None) or out.pop("period_label", None)
    if label is None and out.get("period_key") and _looks_natural_period(str(out["period_key"])):
        label = out["period_key"]
    if label is None:
        return out
    ptype, pkey = _parse_period_label(str(label))
    if ptype and not out.get("period_type"):
        out["period_type"] = ptype
    if pkey:
        out["period_key"] = pkey
    return out


def infer_operation_group(name: str, meta: dict[str, Any] | None = None) -> str:
    if meta and meta.get("group"):
        return str(meta["group"])
    rules: list[tuple[tuple[str, ...], str]] = [
        (("not_project",), "非项目"),
        (("outsource", "supplier"), "外包供应商"),
        (("work_hour", "get_work_hours", "all_times"), "工时"),
        (("overview", "project_list", "project_info", "my_projects"), "项目"),
        (("moment",), "项目动态"),
        (("bug",), "BUG"),
        (("qa_stat",), "QA"),
        (("cost",), "成本"),
        (("dept_", "capacity", "left_hour"), "部门产能"),
        (("publish",), "递交"),
        (("task",), "任务"),
        (("risk", "review", "change", "delivery"), "风险复盘"),
        (("schedule", "employee_project"), "排期"),
        (("quotation", "baojia"), "报价"),
    ]
    for keys, group in rules:
        if any(k in name for k in keys):
            return group
    return "其他"


def extract_page_items(payload: Any) -> tuple[list[Any], int | None]:
    import api_client

    data = api_client._business_data(payload)
    total: int | None = None
    if isinstance(data, list):
        return data, len(data)
    if isinstance(data, dict):
        total = data.get("total")
        if total is not None:
            try:
                total = int(total)
            except (TypeError, ValueError):
                total = None
        for key in ("data", "list", "rows"):
            value = data.get(key)
            if isinstance(value, list):
                return value, total
    return [], total


def inject_merged_items(payload: Any, items: list[Any]) -> Any:
    if not isinstance(payload, dict):
        return {"data": items}
    out = dict(payload)
    data = out.get("data")
    if isinstance(data, list):
        out["data"] = items
        return out
    if isinstance(data, dict):
        merged = dict(data)
        for key in ("data", "list", "rows"):
            if key in merged:
                merged[key] = items
                break
        else:
            merged["data"] = items
        if "total" in merged:
            merged["total"] = len(items)
        out["data"] = merged
        return out
    out["data"] = items
    return out


def _items_from_payload(payload: Any) -> list[Any]:
    items, _ = extract_page_items(payload)
    return items


def _sum_consumed(items: list[Any]) -> float:
    total = 0.0
    for row in items:
        if not isinstance(row, dict):
            continue
        try:
            total += float(row.get("consumed") or 0)
        except (TypeError, ValueError):
            pass
    return round(total, 2)


def _summarize_work_hours(payload: Any) -> dict[str, Any]:
    items = _items_from_payload(payload)
    by_project: dict[str, float] = {}
    by_user: dict[str, float] = {}
    unconfirmed = 0
    for row in items:
        if not isinstance(row, dict):
            continue
        consumed = float(row.get("consumed") or 0)
        project = str(row.get("name") or row.get("project_name") or row.get("sj_num") or "未知项目")
        by_project[project] = by_project.get(project, 0.0) + consumed
        user = str(row.get("user_name") or row.get("user_id") or "未知")
        by_user[user] = by_user.get(user, 0.0) + consumed
        status = row.get("confirm_status")
        if status in (0, "0", "待确认"):
            unconfirmed += 1
    top_projects = sorted(by_project.items(), key=lambda x: x[1], reverse=True)[:5]
    return {
        "record_count": len(items),
        "total_consumed": _sum_consumed(items),
        "unconfirmed_count": unconfirmed,
        "top_projects": [{"name": k, "consumed": round(v, 2)} for k, v in top_projects],
        "user_count": len(by_user),
    }


def _summarize_unconfirmed(payload: Any) -> dict[str, Any]:
    items = _items_from_payload(payload)
    by_user: dict[str, int] = {}
    for row in items:
        if not isinstance(row, dict):
            continue
        user = str(row.get("user_name") or row.get("user_id") or "未知")
        by_user[user] = by_user.get(user, 0) + 1
    top_users = sorted(by_user.items(), key=lambda x: x[1], reverse=True)[:10]
    return {
        "unconfirmed_count": len(items),
        "total_consumed": _sum_consumed(items),
        "users_with_pending": len(by_user),
        "top_users": [{"user": k, "count": v} for k, v in top_users],
    }


def _summarize_performance_list(payload: Any) -> dict[str, Any]:
    items = _items_from_payload(payload)
    return {"user_count": len(items), "record_count": len(items)}


def _summarize_work_hour_statistics(payload: Any) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(data, dict):
        return {}
    return {
        k: data.get(k)
        for k in (
            "total_consumed",
            "project_consumed",
            "not_project_consumed",
            "project_ratio",
            "not_project_ratio",
        )
        if data.get(k) not in (None, "")
    }


SUMMARIZE_HANDLERS: dict[str, Any] = {
    "get_work_hours": _summarize_work_hours,
    "get_unconfirmed_work_hours": _summarize_unconfirmed,
    "get_performance_list": _summarize_performance_list,
    "get_work_hour_statistics": _summarize_work_hour_statistics,
}


def attach_skill_summary(operation: str, payload: Any, enabled: bool = True) -> Any:
    if not enabled or not isinstance(payload, dict):
        return payload
    if payload.get("dry_run") or payload.get("error"):
        return payload
    handler = SUMMARIZE_HANDLERS.get(operation)
    if not handler:
        return payload
    out = dict(payload)
    out["skill_summary"] = handler(payload)
    return out


_WARNING_AGENT_HINTS: dict[str, str] = {
    "user_id": "请向用户追问相关人员（可传 user_name，多人用逗号分隔）",
    "user_name": "请向用户追问相关人员姓名",
    "type": "请向用户确认动态子类型（可先调用 get_project_moment_config_list 查字典）",
    "risk_level": "风险/问题类动态需填写 risk_level（影响程度/风险等级）",
    "confirm_type": "请确认是「项目工时」还是「非项目工时」",
    "remark": "请向用户索取备注说明",
    "consumed": "请向用户确认花费工时数",
    "task_id": "请提供任务 ID（可先 get_task_list 查询）",
    "project_id": "请提供项目（project_name / sj_num）",
    "date": "请确认日期（默认今天）",
    "rows": "项目价值需提交 rows JSON（可先 get_project_overview_value 查看现有内容）",
}


def build_agent_hints(warnings: list[str]) -> list[str]:
    hints: list[str] = []
    for warning in warnings:
        for key, hint in _WARNING_AGENT_HINTS.items():
            if key in warning and hint not in hints:
                hints.append(hint)
    return hints
