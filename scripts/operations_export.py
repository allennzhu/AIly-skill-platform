"""Excel/binary export operations (manage_api, Bearer auth)."""

from __future__ import annotations

from typing import Any, Callable

EXPORT_RESOLVE_MODES = frozenset({"export_estimate_hour"})

_EXPORT_DATE_ALIASES = {
    "start_date": ("date_start", "from_date"),
    "end_date": ("date_end", "to_date"),
}


def _apply_date_aliases(params: dict[str, Any]) -> dict[str, Any]:
    out = dict(params)
    for target, aliases in _EXPORT_DATE_ALIASES.items():
        if out.get(target):
            continue
        for alias in aliases:
            if out.get(alias):
                out[target] = out.pop(alias)
                break
    return out


def resolve_export_estimate_hour(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = _apply_date_aliases(params)
    dept_name = out.pop("dept_name", None)
    if dept_name and not out.get("dept_id"):
        out["dept_id"] = api_client.resolve_dept_id(str(dept_name))

    project_ids = out.pop("project_ids", None)
    if project_ids and not out.get("project_id"):
        out["project_id"] = project_ids

    if not out.get("project_id"):
        project_name = out.pop("project_name", None) or out.pop("name", None)
        sj_num = out.pop("sj_num", None) or out.pop("opportunity_no", None)
        if project_name or sj_num or out.get("project_id"):
            pid = api_client.resolve_project_id(
                {
                    "project_name": project_name,
                    "sj_num": sj_num,
                    "project_id": out.get("project_id"),
                }
            )
            out["project_id"] = [int(pid)]
    elif not isinstance(out.get("project_id"), list):
        out["project_id"] = api_client._parse_int_list(out.get("project_id"))

    return out


def resolve_export(mode: str, params: dict[str, Any]) -> dict[str, Any]:
    handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
        "export_estimate_hour": resolve_export_estimate_hour,
    }
    handler = handlers.get(mode)
    if not handler:
        raise ValueError(f"unknown export resolve mode: {mode}")
    return handler(params)


EXPORT_OPERATIONS: dict[str, dict[str, Any]] = {
    "export_estimate_hour_by_project": {
        "description": "按项目/部门/日期导出全量工时明细 Excel（含项目与非项目）",
        "method": "GET",
        "path": "/manage_api/data_export/export_estimate_hour_for_cd",
        "group": "工时导出",
        "params": [
            "start_date",
            "end_date",
            "date_start",
            "date_end",
            "from_date",
            "to_date",
            "project_id",
            "project_ids",
            "project_name",
            "name",
            "sj_num",
            "opportunity_no",
            "dept_id",
            "dept_name",
            "output_name",
        ],
        "required": ["start_date", "end_date"],
        "resolve_mode": "export_estimate_hour",
        "upstream_params": ["start_date", "end_date", "project_id", "dept_id"],
        "array_params": ["project_id"],
        "binary_export": True,
    },
}
