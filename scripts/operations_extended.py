"""Extended 51PM read-only operations for pm-platform-api skill."""

from __future__ import annotations

from typing import Any, Callable

# Imported lazily from api_client inside resolve_extended to avoid circular imports.

_PROJECT_HINT_KEYS = (
    "project_id",
    "project_name",
    "name",
    "sj_num",
    "opportunity_no",
    "business_no",
)

_PERIOD_TYPE_MAP = {
    "day": "day",
    "日": "day",
    "week": "week",
    "周": "week",
    "weeks": "week",
    "month": "month",
    "月": "month",
    "quarter": "quarter",
    "季": "quarter",
    "季度": "quarter",
    "half": "half",
    "半年": "half",
    "year": "year",
    "年": "year",
}

_MOMENT_MODULE_MAP = {
    "": "",
    "all": "all",
    "全部": "all",
    "meet": "meet",
    "会议": "meet",
    "meeting": "meet",
    "risk": "risk",
    "风险": "risk",
    "problem": "problem",
    "问题": "problem",
}

_DEPT_LEFT_STATUS_MAP = {
    "doing": "doing",
    "进行中": "doing",
    "制作中": "doing",
    "pause": "pause",
    "暂停": "pause",
    "wait": "wait",
    "未开工": "wait",
    "待开工": "wait",
}

_PAGINATION_PARAMS = ["page", "limit", "page_size"]
_PROJECT_ALIAS_PARAMS = [
    "project_id",
    "project_name",
    "name",
    "sj_num",
    "opportunity_no",
    "business_no",
]
_PERIOD_PARAMS = [
    "period_type",
    "period_key",
    "cycle_type",
    "cycle_key",
    "period",
]
_USER_ROLE_PARAMS = [
    "pm_name",
    "pm_id",
    "tester_name",
    "tester",
    "assignee_name",
    "assigned_name",
    "assigned_to",
    "relation_name",
    "relation_uid",
    "user_name",
    "user_id",
    "dept_name",
    "dept_id",
]


def _normalize_map(value: Any, mapping: dict[str, Any], default: Any = None) -> Any:
    if value in (None, ""):
        return default
    key = str(value).strip()
    if key in mapping:
        return mapping[key]
    lowered = key.lower()
    if lowered in mapping:
        return mapping[lowered]
    return key


def resolve_extended(mode: str, params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
        "overview": _resolve_overview,
        "qa_stat": _resolve_qa_stat,
        "moment_stat": _resolve_moment_stat,
        "moment_list": _resolve_moment_list,
        "bug": _resolve_bug,
        "project_cost_stat": _resolve_project_cost_stat,
        "project_cost_list": _resolve_project_cost_list,
        "project_cost_by_id": _resolve_project_cost_by_id,
        "dept_capacity": _resolve_dept_capacity,
        "dept_left_hour_demand": _resolve_dept_left_hour_demand,
        "publish_list": _resolve_publish_list,
        "apply_publish_list": _resolve_apply_publish_list,
        "task_list": _resolve_task_list,
        "project_demand_list": _resolve_project_demand_list,
        "project_risk_panel": _resolve_project_risk_panel,
        "project_review_panel": _resolve_project_review_panel,
        "project_change_info": _resolve_project_change_info,
        "schedule_list": _resolve_schedule_list,
        "schedule_charts": _resolve_schedule_charts,
        "all_times_list": _resolve_all_times_list,
        "quotation_list": _resolve_quotation_list,
        "ecp_baojia_list": _resolve_ecp_baojia_list,
        "outsource_quotation_list": _resolve_outsource_quotation_list,
    }
    handler = handlers.get(mode)
    if not handler:
        raise api_client.ClientError("validation_error", f"unknown resolve_mode: {mode}")
    return handler(dict(params))


def _apply_period_aliases(out: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(
        out,
        {
            "period_type": ("cycle_type", "period"),
            "period_key": ("cycle_key",),
        },
    )
    if "period_type" in out:
        mapped = _normalize_map(out["period_type"], _PERIOD_TYPE_MAP)
        if mapped is not None:
            out["period_type"] = mapped
    return out


def _apply_user_role_aliases(out: dict[str, Any]) -> dict[str, Any]:
    import api_client

    mapping = {
        "pm_name": "pm_id",
        "tester_name": "tester",
        "assignee_name": "assigned_to",
        "assigned_name": "assigned_to",
        "relation_name": "relation_uid",
    }
    for name_key, id_key in mapping.items():
        role_name = out.pop(name_key, None)
        if role_name and not out.get(id_key):
            out[id_key] = api_client.resolve_user_id(str(role_name))
    user_name = out.pop("user_name", None)
    if user_name and not out.get("user_id"):
        out["user_id"] = api_client.resolve_user_id(str(user_name))
    dept_name = out.pop("dept_name", None)
    if dept_name and not out.get("dept_id"):
        out["dept_id"] = api_client.resolve_dept_id(str(dept_name))
    return out


def _cleanup_project_aliases(out: dict[str, Any]) -> None:
    for key in ("project_name", "name", "opportunity_no", "business_no"):
        out.pop(key, None)


def _ensure_project_id(out: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(
        out,
        {
            "project_name": ("name",),
            "sj_num": ("opportunity_no", "business_no"),
        },
    )
    if not out.get("project_id"):
        out["project_id"] = api_client.resolve_project_id(out)
    _cleanup_project_aliases(out)
    return out


def _ensure_project_sj_num(out: dict[str, Any]) -> dict[str, Any]:
    import api_client

    if out.get("project_id") and not str(out["project_id"]).upper().startswith("SJ"):
        # numeric project_id → lookup sj_num
        payload = api_client.api_request(
            "GET",
            "/manage_api/project/get_project_info",
            {"id": str(out["project_id"])},
        )
        data = api_client._business_data(payload)
        info = data.get("info") if isinstance(data, dict) else {}
        sj_num = info.get("sj_num") if isinstance(info, dict) else None
        if sj_num:
            out["project_id"] = str(sj_num)
            return out
    out = api_client._apply_field_aliases(
        out,
        {
            "project_name": ("name",),
            "sj_num": ("opportunity_no", "business_no"),
        },
    )
    if out.get("sj_num") and not out.get("project_id"):
        out["project_id"] = str(out["sj_num"])
    elif not out.get("project_id"):
        pid = api_client.resolve_project_id(out)
        payload = api_client.api_request(
            "GET",
            "/manage_api/project/get_project_info",
            {"id": pid},
        )
        data = api_client._business_data(payload)
        info = data.get("info") if isinstance(data, dict) else {}
        sj_num = info.get("sj_num") if isinstance(info, dict) else None
        if not sj_num:
            raise api_client.ClientError("resolve_failed", "project sj_num not found")
        out["project_id"] = str(sj_num)
    _cleanup_project_aliases(out)
    return out


def _resolve_overview(params: dict[str, Any]) -> dict[str, Any]:
    return _ensure_project_id(params)


def _resolve_qa_stat(params: dict[str, Any]) -> dict[str, Any]:
    out = _apply_period_aliases(params)
    return _apply_user_role_aliases(out)


def _resolve_moment_stat(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = _apply_period_aliases(params)
    out = _apply_user_role_aliases(out)
    out = api_client._apply_field_aliases(
        out,
        {
            "project_name": ("name",),
            "sj_num": ("opportunity_no", "business_no"),
        },
    )
    if (
        any(out.get(k) for k in ("project_name", "name", "sj_num", "opportunity_no", "business_no"))
        and not out.get("project_id")
    ):
        out["project_id"] = api_client.resolve_project_id(out)
    _cleanup_project_aliases(out)
    if "module" in out:
        mapped = _normalize_map(out["module"], _MOMENT_MODULE_MAP, out["module"])
        out["module"] = mapped
    return out


def _resolve_moment_list(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = _apply_user_role_aliases(params)
    out = api_client._apply_field_aliases(
        out,
        {
            "project_name": ("name",),
            "sj_num": ("opportunity_no", "business_no"),
        },
    )
    if (
        any(out.get(k) for k in ("project_name", "name", "sj_num", "opportunity_no", "business_no"))
        and not out.get("project_id")
    ):
        out["project_id"] = api_client.resolve_project_id(out)
    _cleanup_project_aliases(out)
    if "module" in out:
        out["module"] = _normalize_map(out["module"], _MOMENT_MODULE_MAP, out["module"])
    return out


def _resolve_bug(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(
        params,
        {
            "project_name": ("name",),
            "sj_num": ("opportunity_no", "business_no"),
            "submit_begin_time": ("start_date", "date_start"),
            "submit_end_time": ("end_date", "date_end"),
        },
    )
    if not out.get("sj_num") and any(
        out.get(k) for k in ("project_name", "name", "project_id", "opportunity_no", "business_no")
    ):
        out["sj_num"] = _ensure_project_sj_num(dict(out))["project_id"]
    _cleanup_project_aliases(out)
    out = _apply_user_role_aliases(out)
    if out.get("bug_type") and not isinstance(out.get("bug_type"), list):
        out["bug_type"] = api_client._parse_int_list(out["bug_type"])
    return out


def _resolve_project_cost_stat(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = _apply_period_aliases(params)
    out = api_client._apply_field_aliases(out, {"group": ("group_name", "team_name")})
    pm_name = out.pop("pm_name", None)
    if pm_name and not out.get("pm"):
        out["pm"] = pm_name
    if any(out.get(k) for k in _PROJECT_HINT_KEYS if k != "project_id") or out.get(
        "project_name"
    ):
        out = _ensure_project_sj_num(out)
    return out


def _resolve_project_cost_list(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    return api_client.apply_project_param_resolution(params)


def _resolve_project_cost_by_id(params: dict[str, Any]) -> dict[str, Any]:
    out = _ensure_project_id(params)
    if "id" not in out and out.get("project_id"):
        out["id"] = out.pop("project_id")
    return out


def _resolve_dept_capacity(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(
        params,
        {
            "start_date": ("date_start", "from_date"),
            "end_date": ("date_end", "to_date"),
        },
    )
    out = _apply_user_role_aliases(out)
    if out.get("exclude_user_ids") and not isinstance(out["exclude_user_ids"], list):
        out["exclude_user_ids"] = api_client._parse_int_list(out["exclude_user_ids"])
    return out


def _resolve_dept_left_hour_demand(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = dict(params)
    out = api_client._apply_field_aliases(
        out, {"dept_key": ("department_key",), "name": ("demand_name", "project_name")}
    )
    if "status" in out:
        out["status"] = _normalize_map(out["status"], _DEPT_LEFT_STATUS_MAP, out["status"])
    return out


def _apply_date_range_aliases(
    out: dict[str, Any],
    start_key: str = "start_date",
    end_key: str = "end_date",
) -> dict[str, Any]:
    import api_client

    return api_client._apply_field_aliases(
        out,
        {
            start_key: ("date_start", "from_date"),
            end_key: ("date_end", "to_date"),
        },
    )


def _resolve_publish_list(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = _apply_date_range_aliases(dict(params), "begin", "end")
    out = api_client._apply_field_aliases(
        out,
        {
            "keywords": ("keyword",),
            "begin": ("start_date",),
            "end": ("end_date",),
        },
    )
    pm_name = out.pop("pm_name", None)
    if pm_name and not out.get("project_pm"):
        out["project_pm"] = api_client.resolve_user_id(str(pm_name))
    develop_name = out.pop("develop_name", None)
    if develop_name and not out.get("chengxu_people"):
        out["chengxu_people"] = api_client.resolve_user_id(str(develop_name))
    if out.get("publish_industry_line") and not isinstance(
        out["publish_industry_line"], list
    ):
        raw = str(out["publish_industry_line"])
        out["publish_industry_line"] = [
            part.strip() for part in raw.split(",") if part.strip()
        ]
    return out


def _resolve_apply_publish_list(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(
        params,
        {
            "apply_publish_start_time": ("start_date", "date_start", "from_date"),
            "apply_publish_end_time": ("end_date", "date_end", "to_date"),
            "apply_status": ("status",),
        },
    )
    if any(out.get(k) for k in _PROJECT_HINT_KEYS) and not out.get("project_id"):
        out["project_id"] = api_client.resolve_project_id(out)
    _cleanup_project_aliases(out)
    return out


def _resolve_task_list(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = _apply_date_range_aliases(dict(params))
    out = api_client._apply_field_aliases(
        out,
        {
            "project_name": ("name",),
            "sj_num": ("opportunity_no", "business_no"),
        },
    )
    if any(out.get(k) for k in _PROJECT_HINT_KEYS) and not out.get("project_id"):
        out["project_id"] = int(api_client.resolve_project_id(out))
    elif out.get("project_id") not in (None, ""):
        out["project_id"] = int(out["project_id"])
    _cleanup_project_aliases(out)

    assignee_name = out.pop("assignee_name", None) or out.pop("assigned_name", None)
    user_name = out.pop("user_name", None)
    if assignee_name and not out.get("assigned_to"):
        out["assigned_to"] = [int(api_client.resolve_user_id(str(assignee_name)))]
    elif user_name and not out.get("assigned_to"):
        out["assigned_to"] = [int(api_client.resolve_user_id(str(user_name)))]
    elif out.get("assigned_to") not in (None, ""):
        if not isinstance(out.get("assigned_to"), list):
            out["assigned_to"] = api_client._parse_int_list(out["assigned_to"])

    for flag in ("assigned_to_me", "done_by_me"):
        if flag in out and out[flag] not in (None, ""):
            out[flag] = int(str(out[flag]).strip() in ("1", "true", "True", "yes", "是"))

    date_type = str(out.get("date_type") or "").strip().lower()
    if date_type in ("任务", "task"):
        out["date_type"] = "task"
    elif date_type in ("花费", "cost", ""):
        if date_type:
            out["date_type"] = "cost"
    dept_name = out.pop("dept_name", None)
    if dept_name and not out.get("dept_id"):
        out["dept_id"] = int(api_client.resolve_dept_id(str(dept_name)))
    elif out.get("dept_id") not in (None, ""):
        out["dept_id"] = int(out["dept_id"])
    if out.get("one_type") not in (None, ""):
        out["one_type"] = int(out["one_type"])
    return out


def _resolve_project_demand_list(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = _ensure_project_id(params)
    assignee_name = out.pop("assignee_name", None) or out.pop("assigned_name", None)
    if assignee_name and not out.get("assigned_to"):
        out["assigned_to"] = int(api_client.resolve_user_id(str(assignee_name)))
    elif out.get("assigned_to") not in (None, ""):
        out["assigned_to"] = int(out["assigned_to"])
    for flag in ("assigned_to_me", "done_by_me"):
        if flag in out and out[flag] not in (None, ""):
            out[flag] = int(str(out[flag]).strip() in ("1", "true", "True", "yes", "是"))
    return out


def _resolve_project_risk_panel(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(
        params,
        {
            "project_name": ("name",),
            "sj_num": ("opportunity_no", "business_no"),
            "kaigong_start_date": ("kaigong_start", "start_kaigong_date"),
            "kaigong_end_date": ("kaigong_end", "end_kaigong_date"),
            "start_time": ("start_date", "date_start"),
            "end_time": ("end_date", "date_end"),
        },
    )
    pm_name = out.pop("pm_name", None)
    if pm_name and not out.get("project_pm"):
        out["project_pm"] = api_client.resolve_user_id(str(pm_name))
    bd_name = out.pop("bd_name", None)
    if bd_name and not out.get("project_bd_tb"):
        out["project_bd_tb"] = api_client.resolve_user_id(str(bd_name))
    if not out.get("sj_num") and any(
        out.get(k) for k in ("project_name", "name", "project_id", "opportunity_no", "business_no")
    ):
        out["sj_num"] = _ensure_project_sj_num(dict(out))["project_id"]
    _cleanup_project_aliases(out)
    out.pop("project_id", None)
    return out


def _resolve_project_review_panel(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = _apply_date_range_aliases(dict(params))
    out = api_client._apply_field_aliases(
        out,
        {
            "project_name": ("name",),
            "sj_num": ("opportunity_no", "business_no"),
            "ecp_shi_ye_bu": ("business_unit", "shi_ye_bu"),
            "project_scene": ("scene", "make_group"),
        },
    )
    role_map = {
        "pm_name": "project_pm",
        "tester_name": "project_tester",
        "participant_name": "participant",
        "todo_owner_name": "todo_owner_user_id",
        "todo_follow_name": "todo_follow_user_id",
        "experience_owner_name": "experience_owner_user_id",
    }
    for name_key, id_key in role_map.items():
        role_name = out.pop(name_key, None)
        if role_name and not out.get(id_key):
            out[id_key] = api_client.resolve_user_id(str(role_name))
    return out


def _resolve_project_change_info(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = _apply_date_range_aliases(dict(params))
    out = api_client._apply_field_aliases(
        out,
        {
            "sj_num": ("opportunity_no", "business_no"),
            "action_name": ("action",),
        },
    )
    if not out.get("sj_num") and any(
        out.get(k) for k in ("project_name", "name", "project_id", "opportunity_no", "business_no")
    ):
        out["sj_num"] = _ensure_project_sj_num(dict(out))["project_id"]
    pm_name = out.pop("pm_name", None)
    if pm_name and not out.get("pm"):
        out["pm"] = [str(pm_name)]
    elif out.get("pm") and not isinstance(out["pm"], list):
        out["pm"] = [part.strip() for part in str(out["pm"]).split(",") if part.strip()]
    _cleanup_project_aliases(out)
    out.pop("project_id", None)
    return out


def _resolve_schedule_list(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = _apply_date_range_aliases(dict(params))
    dept_name = out.pop("dept_name", None)
    if dept_name and not out.get("dept_id"):
        out["dept_id"] = [api_client.resolve_dept_id(str(dept_name))]
    elif out.get("dept_id") not in (None, "") and not isinstance(out.get("dept_id"), list):
        out["dept_id"] = api_client._parse_int_list(out["dept_id"])
    user_name = out.pop("user_name", None)
    if user_name and not out.get("user_id"):
        out["user_id"] = [int(api_client.resolve_user_id(str(user_name)))]
    elif out.get("user_id") not in (None, "") and not isinstance(out.get("user_id"), list):
        out["user_id"] = api_client._parse_int_list(out["user_id"])
    if out.get("filter_type") in ("项目", "项目任务"):
        out["filter_type"] = "project"
    elif out.get("filter_type") in ("非项目",):
        out["filter_type"] = "not_project"
    elif out.get("filter_type") in ("休假", "假期"):
        out["filter_type"] = "vacation"
    elif out.get("filter_type") in ("全部",):
        out["filter_type"] = "all"
    return out


def _resolve_schedule_charts(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = _apply_date_range_aliases(dict(params))
    dept_name = out.pop("dept_name", None)
    if dept_name and not out.get("dept_id"):
        out["dept_id"] = api_client.resolve_dept_id(str(dept_name))
    user_name = out.pop("user_name", None)
    if user_name and not out.get("user_id"):
        out["user_id"] = [int(api_client.resolve_user_id(str(user_name)))]
    elif out.get("user_id") not in (None, "") and not isinstance(out.get("user_id"), list):
        out["user_id"] = api_client._parse_int_list(out["user_id"])
    return out


def _resolve_all_times_list(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = _apply_date_range_aliases(dict(params))
    dept_name = out.pop("dept_name", None)
    if dept_name and not out.get("dept_id"):
        out["dept_id"] = api_client.resolve_dept_id(str(dept_name))
    user_name = out.pop("user_name", None)
    if user_name and not out.get("user_id"):
        out["user_id"] = [int(api_client.resolve_user_id(str(user_name)))]
    elif out.get("user_id") not in (None, "") and not isinstance(out.get("user_id"), list):
        out["user_id"] = api_client._parse_int_list(out["user_id"])
    return out


def _resolve_quotation_list(params: dict[str, Any]) -> dict[str, Any]:
    out = _ensure_project_sj_num(dict(params))
    out["sj_num"] = str(out.pop("project_id"))
    if out.get("module_id") not in (None, "") and not isinstance(out.get("module_id"), list):
        import api_client

        out["module_id"] = api_client._parse_int_list(out["module_id"])
    return out


def _resolve_ecp_baojia_list(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(
        params,
        {
            "ywx": ("business_unit", "shi_ye_bu", "ecp_shi_ye_bu"),
            "name": ("keyword", "product_name"),
        },
    )
    if out.get("module_id") not in (None, "") and not isinstance(out.get("module_id"), list):
        out["module_id"] = api_client._parse_int_list(out["module_id"])
    return out


def _resolve_outsource_quotation_list(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    return api_client._apply_field_aliases(
        params, {"outsource_package_id": ("package_id",)}
    )


def _overview_op(
    suffix: str,
    description: str,
    extra_upstream: list[str] | None = None,
    extra_params: list[str] | None = None,
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "description": description,
        "method": "GET",
        "path": f"/manage_api/project_overview/{suffix}",
        "params": _PROJECT_ALIAS_PARAMS + _PAGINATION_PARAMS + (extra_params or []),
        "required": required or [],
        "required_any_project": not required,
        "resolve_mode": "overview",
        "upstream_params": ["project_id"] + (extra_upstream or []),
        "default_limit": 500,
    }


def build_extended_operations(project_list_params: list[str]) -> dict[str, dict[str, Any]]:
    ops = dict(EXTENDED_OPERATIONS)
    ops["get_project_cost_list"] = {
        "description": "项目成本列表（管理端筛选）",
        "method": "GET",
        "path": "/manage_api/data_export/get_project_cost_list",
        "params": project_list_params,
        "resolve_mode": "project_cost_list",
        "upstream_params": [
            "sj_num",
            "kaigong_date_start",
            "kaigong_date_end",
            "project_pm",
            "project_bd_tb",
            "ecp_qu_yu_tuan_dui",
            "ecp_shi_ye_bu",
            "page",
            "limit",
        ],
        "default_limit": 20,
    }
    return ops


EXTENDED_OPERATIONS: dict[str, dict[str, Any]] = {
    # --- 项目健康度 / 单项目全景 ---
    "get_project_overview_header": _overview_op(
        "get_header", "项目概览-身份卡与 KPI"
    ),
    "get_project_overview_req_cost": _overview_op(
        "get_req_cost", "项目概览-需求与成本"
    ),
    "get_project_overview_quality": _overview_op(
        "get_quality", "项目概览-质量与 BUG"
    ),
    "get_project_overview_deliver": _overview_op(
        "get_deliver", "项目概览-递交情况"
    ),
    "get_project_overview_people": _overview_op(
        "get_people", "项目概览-人员投入"
    ),
    "get_project_overview_risk": _overview_op(
        "get_risk", "项目概览-风险与执行问题"
    ),
    "get_project_overview_value": _overview_op(
        "get_value", "项目概览-项目价值"
    ),
    "get_project_overview_req_detail": _overview_op(
        "get_req_detail",
        "项目概览-需求/任务下钻",
        extra_upstream=["chart_key", "option"],
        extra_params=["chart_key", "option"],
        required=["chart_key"],
    ),
    "get_project_overview_quality_detail": _overview_op(
        "get_quality_detail",
        "项目概览-质量下钻明细",
        extra_upstream=["chart_key", "option", "sub_option"],
        extra_params=["chart_key", "option", "sub_option"],
        required=["chart_key", "option"],
    ),
    # --- 项目动态 ---
    "get_project_moment_list": {
        "description": "单项目动态列表（会议/风险/问题）",
        "method": "GET",
        "path": "/manage_api/project_moment/get_list",
        "params": _PROJECT_ALIAS_PARAMS
        + _USER_ROLE_PARAMS
        + _PAGINATION_PARAMS
        + ["module", "meeting", "risk", "problem"],
        "resolve_mode": "moment_list",
        "upstream_params": [
            "project_id",
            "module",
            "relation_uid",
            "pm_id",
            "dept_id",
            "page",
            "limit",
        ],
        "default_limit": 500,
    },
    "get_project_moment_info": {
        "description": "项目动态详情",
        "method": "GET",
        "path": "/manage_api/project_moment/get_info",
        "params": ["id", "moment_id"],
        "required": ["id", "moment_id"],
        "required_any": True,
        "resolve_mode": "moment_list",
        "upstream_params": ["id"],
    },
    "get_project_moment_stat": {
        "description": "项目动态统计看板（会议/风险/问题 KPI）",
        "method": "GET",
        "path": "/manage_api/data_export/get_project_moment_stat",
        "params": _PERIOD_PARAMS
        + _PROJECT_ALIAS_PARAMS
        + _USER_ROLE_PARAMS
        + ["module", "meeting", "risk", "problem"],
        "required": ["period_type", "period_key"],
        "resolve_mode": "moment_stat",
        "upstream_params": [
            "period_type",
            "period_key",
            "module",
            "project_id",
            "pm_id",
            "relation_uid",
            "dept_id",
            "user_id",
        ],
    },
    "get_project_moment_stat_list": {
        "description": "项目动态统计-动态明细列表",
        "method": "GET",
        "path": "/manage_api/data_export/get_project_moment_stat_list",
        "params": _PERIOD_PARAMS
        + _PROJECT_ALIAS_PARAMS
        + _USER_ROLE_PARAMS
        + _PAGINATION_PARAMS
        + ["module"],
        "required": ["period_type", "period_key"],
        "resolve_mode": "moment_stat",
        "upstream_params": [
            "period_type",
            "period_key",
            "module",
            "project_id",
            "pm_id",
            "relation_uid",
            "dept_id",
            "user_id",
            "page",
            "limit",
        ],
        "default_limit": 20,
    },
    "get_project_moment_stat_detail": {
        "description": "项目动态统计-本期新增明细",
        "method": "GET",
        "path": "/manage_api/data_export/get_project_moment_stat_detail",
        "params": _PERIOD_PARAMS
        + _PROJECT_ALIAS_PARAMS
        + _USER_ROLE_PARAMS
        + ["module", "status", "type", "filter_dept_id"],
        "required": ["period_type", "period_key", "module"],
        "resolve_mode": "moment_stat",
        "upstream_params": [
            "period_type",
            "period_key",
            "module",
            "project_id",
            "pm_id",
            "relation_uid",
            "dept_id",
            "user_id",
            "status",
            "type",
            "filter_dept_id",
        ],
    },
    # --- BUG ---
    "get_bug_list": {
        "description": "BUG 列表查询",
        "method": "GET",
        "path": "/manage_api/bug/get_list",
        "params": _PROJECT_ALIAS_PARAMS
        + _USER_ROLE_PARAMS
        + _PAGINATION_PARAMS
        + [
            "bug_status",
            "bug_type",
            "bug_level",
            "priority",
            "submit_begin_time",
            "submit_end_time",
            "start_date",
            "end_date",
            "is_self_check",
        ],
        "resolve_mode": "bug",
        "upstream_params": [
            "sj_num",
            "bug_status",
            "bug_type",
            "bug_level",
            "priority",
            "tester",
            "assigned_to",
            "submit_begin_time",
            "submit_end_time",
            "is_self_check",
            "page",
            "limit",
        ],
        "array_params": ["bug_type"],
        "default_limit": 20,
    },
    "get_bug_info": {
        "description": "BUG 详情",
        "method": "GET",
        "path": "/manage_api/bug/get_info",
        "params": ["id", "bug_id"],
        "required": ["id", "bug_id"],
        "required_any": True,
        "upstream_params": ["id"],
    },
    "get_bug_total": {
        "description": "BUG 数量统计",
        "method": "GET",
        "path": "/manage_api/bug/get_bug_total",
        "params": [],
        "upstream_params": [],
    },
    # --- QA / 递交 ---
    "get_qa_stat_kpi": {
        "description": "QA 统计看板-关键指标",
        "method": "GET",
        "path": "/manage_api/data_export/get_qa_stat_kpi",
        "params": _PERIOD_PARAMS + _USER_ROLE_PARAMS,
        "required": ["period_type", "period_key"],
        "resolve_mode": "qa_stat",
        "upstream_params": [
            "period_type",
            "period_key",
            "dept_id",
            "assigned_to",
            "tester",
            "pm_id",
        ],
    },
    "get_qa_stat_bug": {
        "description": "QA 统计看板-BUG 维度",
        "method": "GET",
        "path": "/manage_api/data_export/get_qa_stat_bug",
        "params": _PERIOD_PARAMS + _USER_ROLE_PARAMS,
        "required": ["period_type", "period_key"],
        "resolve_mode": "qa_stat",
        "upstream_params": [
            "period_type",
            "period_key",
            "dept_id",
            "assigned_to",
            "tester",
            "pm_id",
        ],
    },
    "get_qa_stat_publish": {
        "description": "QA 统计看板-递交维度",
        "method": "GET",
        "path": "/manage_api/data_export/get_qa_stat_publish",
        "params": _PERIOD_PARAMS + _USER_ROLE_PARAMS,
        "required": ["period_type", "period_key"],
        "resolve_mode": "qa_stat",
        "upstream_params": [
            "period_type",
            "period_key",
            "dept_id",
            "assigned_to",
            "tester",
            "pm_id",
        ],
    },
    "get_qa_stat_summary": {
        "description": "QA 统计看板-周期总结",
        "method": "GET",
        "path": "/manage_api/data_export/get_qa_stat_summary",
        "params": _PERIOD_PARAMS,
        "required": ["period_type", "period_key"],
        "resolve_mode": "qa_stat",
        "upstream_params": ["period_type", "period_key"],
    },
    "get_qa_stat_detail_list": {
        "description": "QA 统计看板-下钻列表",
        "method": "GET",
        "path": "/manage_api/data_export/get_qa_stat_detail_list",
        "params": _PERIOD_PARAMS
        + _USER_ROLE_PARAMS
        + _PAGINATION_PARAMS
        + ["chart_key", "option_id", "bug_level", "list_type"],
        "required": ["period_type", "period_key", "chart_key"],
        "resolve_mode": "qa_stat",
        "upstream_params": [
            "period_type",
            "period_key",
            "dept_id",
            "assigned_to",
            "tester",
            "pm_id",
            "chart_key",
            "option_id",
            "bug_level",
            "list_type",
            "page",
            "limit",
        ],
        "default_limit": 20,
    },
    # --- 项目成本 ---
    "get_project_cost_stat": {
        "description": "项目成本动态看板聚合",
        "method": "GET",
        "path": "/manage_api/data_export/get_project_cost_stat",
        "params": _PERIOD_PARAMS
        + _PROJECT_ALIAS_PARAMS
        + ["group", "team_name", "group_name", "pm", "pm_name"],
        "required": ["period_type", "period_key"],
        "resolve_mode": "project_cost_stat",
        "upstream_params": ["period_type", "period_key", "group", "pm", "project_id"],
    },
    "get_project_cost_stat_list": {
        "description": "项目成本动态看板-工时明细",
        "method": "GET",
        "path": "/manage_api/data_export/get_project_cost_stat_list",
        "params": _PROJECT_ALIAS_PARAMS
        + _PAGINATION_PARAMS
        + ["output_type", "keyword", "all"],
        "required": ["project_id", "project_name", "name", "sj_num", "opportunity_no", "business_no"],
        "required_any": True,
        "resolve_mode": "project_cost_stat",
        "upstream_params": [
            "project_id",
            "output_type",
            "keyword",
            "all",
            "page",
            "limit",
        ],
        "default_limit": 20,
    },
    "get_project_cost_by_id": {
        "description": "单项目成本明细列表",
        "method": "GET",
        "path": "/manage_api/project/get_cost_list_by_project_id",
        "params": _PROJECT_ALIAS_PARAMS + _PAGINATION_PARAMS + ["type", "cost_type"],
        "required": ["project_id", "project_name", "name", "sj_num", "opportunity_no", "business_no"],
        "required_any": True,
        "resolve_mode": "project_cost_by_id",
        "upstream_params": ["id", "type", "page", "limit"],
        "default_limit": 20,
    },
    # --- 部门产能 ---
    "get_dept_capacity_panel": {
        "description": "部门产能面板",
        "method": "GET",
        "path": "/manage_api/data_export/get_dept_capacity_panel",
        "params": [
            "dept_id",
            "dept_name",
            "start_date",
            "end_date",
            "date_start",
            "date_end",
            "hire_type",
            "total_consumed_start_year",
            "total_consumed_end_year",
            "total_consumed_month",
            "exclude_user_ids",
        ],
        "resolve_mode": "dept_capacity",
        "upstream_params": [
            "dept_id",
            "start_date",
            "end_date",
            "hire_type",
            "total_consumed_start_year",
            "total_consumed_end_year",
            "total_consumed_month",
            "exclude_user_ids",
        ],
        "array_params": ["exclude_user_ids"],
    },
    "get_dept_left_hour_panel": {
        "description": "部门剩余工时看板",
        "method": "GET",
        "path": "/manage_api/data_export/get_dept_left_hour_panel",
        "params": [],
        "upstream_params": [],
    },
    "get_dept_left_hour_demand_list": {
        "description": "部门剩余工时-需求详情列表",
        "method": "GET",
        "path": "/manage_api/data_export/get_dept_left_hour_demand_list",
        "params": _PAGINATION_PARAMS
        + ["dept_key", "department_key", "status", "name", "demand_name"],
        "required": ["dept_key", "status"],
        "resolve_mode": "dept_left_hour_demand",
        "upstream_params": ["dept_key", "status", "name", "page", "limit"],
        "default_limit": 20,
    },
    # --- 递交明细 / 申请 ---
    "get_publish_list": {
        "description": "递交台账列表（可按 PM/状态/时间筛选）",
        "method": "GET",
        "path": "/manage_api/project_publish/get_list",
        "params": _PAGINATION_PARAMS
        + [
            "keywords",
            "keyword",
            "publish_content",
            "publish_submit_status",
            "publish_dijiao_version",
            "project_scene",
            "begin",
            "end",
            "start_date",
            "end_date",
            "date_start",
            "date_end",
            "pm_name",
            "project_pm",
            "chengxu_people",
            "develop_name",
            "publish_industry_line",
            "is_increment_pack",
            "is_over_tb_time",
        ],
        "resolve_mode": "publish_list",
        "upstream_params": [
            "keywords",
            "publish_content",
            "publish_submit_status",
            "publish_dijiao_version",
            "project_scene",
            "begin",
            "end",
            "project_pm",
            "chengxu_people",
            "publish_industry_line",
            "is_increment_pack",
            "is_over_tb_time",
            "page",
            "limit",
        ],
        "default_limit": 20,
    },
    "get_publish_info": {
        "description": "递交详情",
        "method": "GET",
        "path": "/manage_api/project_publish/publish_info",
        "params": ["id", "publish_id"],
        "required": ["id", "publish_id"],
        "required_any": True,
        "upstream_params": ["id"],
    },
    "get_apply_publish_list": {
        "description": "递交申请列表",
        "method": "GET",
        "path": "/manage_api/produce_demand/get_publish_list",
        "params": _PROJECT_ALIAS_PARAMS
        + _PAGINATION_PARAMS
        + [
            "apply_status",
            "status",
            "apply_publish_start_time",
            "apply_publish_end_time",
            "start_date",
            "end_date",
            "date_start",
            "date_end",
        ],
        "resolve_mode": "apply_publish_list",
        "upstream_params": [
            "project_id",
            "apply_status",
            "apply_publish_start_time",
            "apply_publish_end_time",
            "page",
            "limit",
        ],
        "default_limit": 20,
    },
    # --- 项目任务（task_type=2，走任务接口）---
    "get_task_list": {
        "description": "项目任务列表（不含需求）",
        "method": "GET",
        "path": "/manage_api/task/get_task_list",
        "params": _PROJECT_ALIAS_PARAMS
        + _PAGINATION_PARAMS
        + _USER_ROLE_PARAMS
        + [
            "status",
            "name",
            "start_date",
            "end_date",
            "date_start",
            "date_end",
            "date_type",
            "one_type",
            "assigned_to_me",
        ],
        "resolve_mode": "task_list",
        "upstream_params": [
            "project_id",
            "status",
            "name",
            "assigned_to",
            "start_date",
            "end_date",
            "date_type",
            "one_type",
            "dept_id",
            "page",
            "limit",
        ],
        "array_params": ["assigned_to"],
        "default_limit": 20,
    },
    "get_project_demand_list": {
        "description": "项目需求列表（含需求与任务混合树，走需求接口）",
        "method": "GET",
        "path": "/manage_api/project_task/get_task_list",
        "params": _PROJECT_ALIAS_PARAMS
        + _PAGINATION_PARAMS
        + [
            "status",
            "name",
            "assigned_to",
            "assignee_name",
            "assigned_name",
            "assigned_to_me",
            "done_by_me",
        ],
        "required_any_project": True,
        "resolve_mode": "project_demand_list",
        "upstream_params": [
            "project_id",
            "status",
            "name",
            "assigned_to",
            "assigned_to_me",
            "done_by_me",
            "page",
            "limit",
        ],
        "default_limit": 20,
    },
    "get_task_info": {
        "description": "项目任务详情",
        "method": "GET",
        "path": "/manage_api/project_task/get_task_info",
        "params": ["id", "task_id"],
        "required": ["id", "task_id"],
        "required_any": True,
        "upstream_params": ["id"],
    },
    # --- 风险 / 复盘 / ECP 动态 / 交付形态 ---
    "get_project_risk_panel": {
        "description": "项目风险面板（全局视角）",
        "method": "GET",
        "path": "/manage_api/data_export/get_project_risk_panel",
        "params": _PROJECT_ALIAS_PARAMS
        + [
            "kaigong_start_date",
            "kaigong_end_date",
            "kaigong_start",
            "kaigong_end",
            "pm_name",
            "project_pm",
            "bd_name",
            "project_bd_tb",
            "status",
            "risk_level",
            "type",
            "start_time",
            "end_time",
            "start_date",
            "end_date",
        ],
        "resolve_mode": "project_risk_panel",
        "upstream_params": [
            "sj_num",
            "kaigong_start_date",
            "kaigong_end_date",
            "project_pm",
            "project_bd_tb",
            "status",
            "risk_level",
            "type",
            "start_time",
            "end_time",
        ],
    },
    "get_project_review_panel": {
        "description": "项目复盘面板（得分/待办/经验沉淀）",
        "method": "GET",
        "path": "/manage_api/data_export/get_project_review_panel",
        "params": _PROJECT_ALIAS_PARAMS
        + [
            "start_date",
            "end_date",
            "date_start",
            "date_end",
            "project_scene",
            "scene",
            "pm_name",
            "project_pm",
            "tester_name",
            "project_tester",
            "participant_name",
            "participant",
            "ecp_shi_ye_bu",
            "business_unit",
            "todo_status",
            "todo_owner_user_id",
            "todo_owner_name",
            "todo_follow_user_id",
            "todo_follow_name",
            "experience_keyword",
            "experience_owner_user_id",
            "experience_owner_name",
        ],
        "resolve_mode": "project_review_panel",
        "upstream_params": [
            "sj_num",
            "project_name",
            "start_date",
            "end_date",
            "project_scene",
            "project_pm",
            "project_tester",
            "participant",
            "ecp_shi_ye_bu",
            "todo_status",
            "todo_owner_user_id",
            "todo_follow_user_id",
            "experience_keyword",
            "experience_owner_user_id",
        ],
    },
    "get_project_change_info": {
        "description": "ECP 项目每日动态",
        "method": "GET",
        "path": "/manage_api/data_export/get_project_change_info",
        "params": _PROJECT_ALIAS_PARAMS
        + _PAGINATION_PARAMS
        + [
            "start_date",
            "end_date",
            "date_start",
            "date_end",
            "action_name",
            "action",
            "pm",
            "pm_name",
        ],
        "resolve_mode": "project_change_info",
        "upstream_params": [
            "sj_num",
            "start_date",
            "end_date",
            "action_name",
            "pm",
            "page",
            "limit",
        ],
        "default_limit": 20,
    },
    "get_project_delivery_type_panel": {
        "description": "项目交付形态面板",
        "method": "GET",
        "path": "/manage_api/data_export/get_project_delivery_type_panel",
        "params": ["start_year", "end_year", "is_wdp"],
        "upstream_params": ["start_year", "end_year", "is_wdp"],
    },
    # --- 人力排期 / 工时矩阵 ---
    "get_total_schedule_list": {
        "description": "人力排期总览（排期数量与时间轴）",
        "method": "GET",
        "path": "/manage_api/data_export/get_total_paiqi_list",
        "params": [],
        "upstream_params": [],
    },
    "get_employee_project_list": {
        "description": "人力排期列表（按部门/人员/日期）",
        "method": "GET",
        "path": "/manage_api/data_export/get_employee_project_list",
        "params": [
            "dept_id",
            "dept_name",
            "user_id",
            "user_name",
            "start_date",
            "end_date",
            "date_start",
            "date_end",
            "hire_type",
            "filter_type",
            "page",
            "limit",
            "page_size",
        ],
        "resolve_mode": "schedule_list",
        "upstream_params": [
            "dept_id",
            "user_id",
            "start_date",
            "end_date",
            "hire_type",
            "filter_type",
            "page",
            "limit",
        ],
        "array_params": ["dept_id", "user_id"],
        "default_limit": 20,
    },
    "get_employee_project_charts": {
        "description": "人力甘特图数据",
        "method": "GET",
        "path": "/manage_api/data_export/get_employee_project_charts",
        "params": [
            "dept_id",
            "dept_name",
            "user_id",
            "user_name",
            "start_date",
            "end_date",
            "date_start",
            "date_end",
            "page",
            "limit",
            "page_size",
        ],
        "resolve_mode": "schedule_charts",
        "upstream_params": [
            "dept_id",
            "user_id",
            "start_date",
            "end_date",
            "page",
            "limit",
        ],
        "array_params": ["user_id"],
        "default_limit": 20,
    },
    "get_all_times_list": {
        "description": "当月工时填报矩阵总览",
        "method": "GET",
        "path": "/manage_api/data_export/get_all_times_list",
        "params": [
            "start_date",
            "end_date",
            "date_start",
            "date_end",
            "user_id",
            "user_name",
            "dept_id",
            "dept_name",
        ],
        "resolve_mode": "all_times_list",
        "upstream_params": ["start_date", "end_date", "user_id", "dept_id"],
        "array_params": ["user_id"],
    },
    "get_qa_stat_period_target": {
        "description": "QA 统计看板-周期目标",
        "method": "GET",
        "path": "/manage_api/data_export/get_qa_stat_period_target",
        "params": _PERIOD_PARAMS,
        "required": ["period_type", "period_key"],
        "resolve_mode": "qa_stat",
        "upstream_params": ["period_type", "period_key"],
    },
    # --- 报价单 ---
    "get_project_quotation_list": {
        "description": "项目 ECP 报价单列表（含成本/标准价汇总）",
        "method": "GET",
        "path": "/manage_api/project_quotation/get_quotation_list",
        "params": _PROJECT_ALIAS_PARAMS
        + _PAGINATION_PARAMS
        + ["status", "module_id"],
        "required_any_project": True,
        "resolve_mode": "quotation_list",
        "upstream_params": ["sj_num", "status", "module_id", "page", "limit"],
        "array_params": ["module_id"],
        "default_limit": 20,
    },
    "get_ecp_baojia_list": {
        "description": "ECP 报价项目录列表",
        "method": "GET",
        "path": "/manage_api/data_export/get_ecp_baojia_list",
        "params": _PAGINATION_PARAMS
        + [
            "version_id",
            "module_id",
            "ywx",
            "business_unit",
            "shi_ye_bu",
            "ecp_shi_ye_bu",
            "name",
            "keyword",
            "product_name",
        ],
        "resolve_mode": "ecp_baojia_list",
        "upstream_params": ["version_id", "module_id", "ywx", "name", "page", "limit"],
        "array_params": ["module_id"],
        "default_limit": 20,
    },
    "get_ecp_baojia_const": {
        "description": "ECP 报价项常量（模块/版本字典）",
        "method": "GET",
        "path": "/manage_api/data_export/get_ecp_baojia_const",
        "params": [],
        "upstream_params": [],
    },
    "get_outsource_quotation_list": {
        "description": "模型外包报价单列表",
        "method": "GET",
        "path": "/manage_api/outsource_quotation/get_quotation_list",
        "params": _PAGINATION_PARAMS
        + [
            "outsource_package_id",
            "package_id",
            "supplier_id",
            "status",
        ],
        "resolve_mode": "outsource_quotation_list",
        "upstream_params": [
            "outsource_package_id",
            "supplier_id",
            "status",
            "page",
            "limit",
        ],
        "default_limit": 20,
    },
}

# get_project_cost_list is injected by build_extended_operations().
