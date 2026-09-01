"""High-value read operations and field dictionaries."""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from operations_extended import (
    _PAGINATION_PARAMS,
    _PERIOD_PARAMS,
    _PROJECT_ALIAS_PARAMS,
    _PROJECT_HINT_KEYS,
    _USER_ROLE_PARAMS,
    _apply_period_aliases,
    _apply_user_role_aliases,
    _cleanup_project_aliases,
    _ensure_project_id,
)

_USER_PROJECT_TYPE_MAP = {
    "develop": "develop",
    "项目开发": "develop",
    "开发": "develop",
    "develop_new": "develop_new",
    "design": "design",
    "项目设计": "design",
    "设计": "design",
    "design_new": "design_new",
    "web": "web",
    "网页制作": "web",
    "scenea": "scenea",
    "sceneb": "sceneb",
    "scenec": "scenec",
    "scened": "scened",
    "pm": "pm",
    "项目经理": "pm",
    "tech": "tech",
    "技术": "tech",
    "dta": "dta",
}


def _month_range() -> tuple[str, str]:
    today = date.today()
    start = today.replace(day=1)
    return start.isoformat(), today.isoformat()


def _resolve_date_user_dept(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = _apply_user_role_aliases(params)
    if not out.get("start_date") or not out.get("end_date"):
        start, end = _month_range()
        out.setdefault("start_date", start)
        out.setdefault("end_date", end)
    user_name = out.pop("user_name", None)
    if user_name and not out.get("user_id") and not out.get("user_ids"):
        out["user_id"] = api_client.resolve_user_id(str(user_name))
    dept_name = out.pop("dept_name", None)
    if dept_name and not out.get("dept_id"):
        out["dept_id"] = api_client.resolve_dept_id(str(dept_name))
    if out.get("user_id") not in (None, "") and not isinstance(out.get("user_id"), list):
        try:
            out["user_id"] = int(out["user_id"])
        except (TypeError, ValueError):
            pass
    return out


def _resolve_sj_num_only(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(
        params,
        {"project_name": ("name",), "sj_num": ("opportunity_no", "business_no")},
    )
    if out.get("sj_num"):
        return {"sj_num": str(out["sj_num"])}
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
    return {"sj_num": str(sj_num)}


def _resolve_project_only(params: dict[str, Any]) -> dict[str, Any]:
    return _ensure_project_id(params)


def _resolve_user_project(params: dict[str, Any]) -> dict[str, Any]:
    out = dict(params)
    raw = str(out.get("type", "")).strip()
    out["type"] = _USER_PROJECT_TYPE_MAP.get(raw, _USER_PROJECT_TYPE_MAP.get(raw.lower(), raw))
    return out


def _resolve_moment_chart(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = _apply_period_aliases(params)
    out = _apply_user_role_aliases(out)
    out = api_client._apply_field_aliases(
        out,
        {"project_name": ("name",), "sj_num": ("opportunity_no", "business_no")},
    )
    if any(out.get(k) for k in _PROJECT_HINT_KEYS) and not out.get("project_id"):
        out["project_id"] = int(api_client.resolve_project_id(out))
    _cleanup_project_aliases(out)
    return out


def _resolve_employee_estimate(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = dict(params)
    user_name = out.pop("user_name", None)
    if user_name and not out.get("user_id"):
        out["user_id"] = int(api_client.resolve_user_id(str(user_name)))
    if out.get("user_id") not in (None, ""):
        out["user_id"] = int(out["user_id"])
    if out.get("task_id") not in (None, ""):
        out["task_id"] = int(out["task_id"])
    if out.get("type_p") not in (None, ""):
        out["type_p"] = int(out["type_p"])
    return out


def _resolve_unconfirmed(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = _resolve_date_user_dept(params)
    out["confirm_status"] = 0
    if out.get("user_id") and not out.get("user_ids"):
        uid = out.pop("user_id")
        out["user_ids"] = uid if isinstance(uid, list) else [int(uid)]
    if out.get("project_id") and not out.get("project_ids"):
        out["project_ids"] = api_client._parse_int_list(out.pop("project_id"))
    return out


def _resolve_publish_apply(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = _apply_user_role_aliases(params)
    out = api_client._apply_field_aliases(
        out,
        {"project_name": ("name",), "sj_num": ("opportunity_no", "business_no")},
    )
    if any(out.get(k) for k in _PROJECT_HINT_KEYS) and not out.get("project_id"):
        out["project_id"] = int(api_client.resolve_project_id(out))
    pm_name = out.pop("pm_name", None)
    if pm_name and not out.get("pm_id"):
        out["pm_id"] = int(api_client.resolve_user_id(str(pm_name)))
    _cleanup_project_aliases(out)
    return out


def _resolve_outsource_dimension(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(
        params,
        {"project_name": ("name",), "sj_num": ("opportunity_no", "business_no")},
    )
    if any(out.get(k) for k in _PROJECT_HINT_KEYS) and not out.get("project_id"):
        out["project_id"] = int(api_client.resolve_project_id(out))
    pm_name = out.pop("pm_name", None)
    if pm_name and not out.get("pm_user_id"):
        out["pm_user_id"] = int(api_client.resolve_user_id(str(pm_name)))
    package_id = out.pop("package_id", None)
    if package_id and not out.get("outsource_package_id"):
        out["outsource_package_id"] = int(package_id)
    _cleanup_project_aliases(out)
    return out


def _resolve_user_search(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = dict(params)
    dept_name = out.pop("dept_name", None)
    if dept_name and not out.get("dept_id"):
        out["dept_id"] = api_client.resolve_dept_id(str(dept_name))
    return out


def resolve_read_enhanced(mode: str, params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
        "date_user_dept": _resolve_date_user_dept,
        "project_only": _resolve_project_only,
        "user_project": _resolve_user_project,
        "moment_chart": _resolve_moment_chart,
        "employee_estimate": _resolve_employee_estimate,
        "unconfirmed": _resolve_unconfirmed,
        "publish_apply": _resolve_publish_apply,
        "outsource_dimension": _resolve_outsource_dimension,
        "user_search": _resolve_user_search,
        "sj_num_only": _resolve_sj_num_only,
    }
    handler = handlers.get(mode)
    if not handler:
        raise api_client.ClientError("validation_error", f"unknown read resolve_mode: {mode}")
    return handler(dict(params))


READ_ENHANCED_OPERATIONS: dict[str, dict[str, Any]] = {
    "get_unconfirmed_work_hours": {
        "description": "未确认工时明细（本月默认，confirm_status=0）",
        "method": "GET",
        "path": "/manage_api/data_export/get_work_hour_detail_list",
        "group": "工时",
        "params": [
            "start_date",
            "end_date",
            "user_id",
            "user_name",
            "dept_id",
            "dept_name",
            "project_id",
            "project_name",
            "sj_num",
            "page",
            "limit",
            "page_size",
        ],
        "resolve_mode": "unconfirmed",
        "summarize": True,
        "upstream_params": [
            "start_date",
            "end_date",
            "user_ids",
            "dept_id",
            "project_ids",
            "confirm_status",
            "page",
            "limit",
        ],
        "array_params": ["user_ids", "project_ids"],
        "default_limit": 500,
    },
    "get_performance_list": {
        "description": "月度绩效列表",
        "method": "GET",
        "path": "/manage_api/data_export/get_performance_list",
        "group": "工时",
        "params": [
            "start_date",
            "end_date",
            "user_id",
            "user_name",
            "dept_id",
            "dept_name",
            "page",
            "limit",
            "page_size",
        ],
        "required": ["start_date", "end_date"],
        "resolve_mode": "date_user_dept",
        "summarize": True,
        "upstream_params": ["start_date", "end_date", "user_id", "dept_id", "page", "limit"],
        "array_params": ["user_id"],
        "default_limit": 50,
    },
    "get_performance_user": {
        "description": "用户月度绩效详情",
        "method": "GET",
        "path": "/manage_api/data_export/get_performance_user",
        "group": "工时",
        "params": ["start_date", "end_date", "user_id", "user_name"],
        "required": ["start_date", "end_date"],
        "required_one_of": ["user_id", "user_name"],
        "resolve_mode": "date_user_dept",
        "upstream_params": ["start_date", "end_date", "user_id"],
    },
    "search_user": {
        "description": "按昵称搜索用户",
        "method": "GET",
        "path": "/manage_api/user/get_user_list",
        "group": "人员部门",
        "params": [
            "nick_name",
            "mobile_phone",
            "dept_id",
            "dept_name",
            "page",
            "limit",
            "page_size",
            "get_all",
            "contain_leave",
        ],
        "required": ["nick_name"],
        "resolve_mode": "user_search",
        "upstream_params": ["nick_name", "mobile_phone", "dept_id", "page", "limit", "get_all", "contain_leave"],
        "default_limit": 20,
    },
    "get_department_list": {
        "description": "部门列表",
        "method": "GET",
        "path": "/manage_api/menu_department/get_dept_list",
        "group": "人员部门",
        "params": ["page", "limit", "page_size"],
        "upstream_params": ["page", "limit"],
        "default_limit": 500,
    },
    "get_user_project": {
        "description": "人员项目看板（按岗位类型）",
        "method": "GET",
        "path": "/manage_api/data_export/get_user_project",
        "group": "项目",
        "params": ["type", "start_year", "end_year", "ecp_kaigong_zhuangtai"],
        "required": ["type"],
        "resolve_mode": "user_project",
        "upstream_params": ["type", "start_year", "end_year", "ecp_kaigong_zhuangtai"],
    },
    "get_user_project_panel": {
        "description": "人员项目看板（面板版）",
        "method": "GET",
        "path": "/manage_api/data_export/get_user_project_panel",
        "group": "项目",
        "params": ["type", "start_year", "end_year", "ecp_kaigong_zhuangtai"],
        "required": ["type"],
        "resolve_mode": "user_project",
        "upstream_params": ["type", "start_year", "end_year", "ecp_kaigong_zhuangtai"],
    },
    "get_scene_group_project": {
        "description": "按场景组获取项目看板",
        "method": "GET",
        "path": "/manage_api/data_export/get_scene_group_project",
        "group": "项目",
        "params": ["start_year", "end_year", "ecp_kaigong_zhuangtai"],
        "upstream_params": ["start_year", "end_year", "ecp_kaigong_zhuangtai"],
    },
    "get_project_group_info": {
        "description": "项目组信息（产品线/制作内容/收入类型）",
        "method": "GET",
        "path": "/manage_api/data_export/get_project_group_info",
        "group": "项目",
        "params": ["date", "date_end"],
        "upstream_params": ["date", "date_end"],
    },
    "get_last_publish_info": {
        "description": "某项目最后一次递交信息",
        "method": "GET",
        "path": "/manage_api/project_publish/get_last_publish_info",
        "group": "递交",
        "params": ["sj_num", "project_name", "name", "opportunity_no", "business_no", "project_id"],
        "required_one_of": ["sj_num", "project_name", "name", "opportunity_no", "business_no", "project_id"],
        "resolve_mode": "sj_num_only",
        "upstream_params": ["sj_num"],
    },
    "get_publish_normal_const": {
        "description": "递交状态/版本等字典常量",
        "method": "GET",
        "path": "/manage_api/project_publish/get_normal_const",
        "group": "递交",
        "params": [],
        "upstream_params": [],
        "dictionary": True,
    },
    "get_qa_reject_publish_list": {
        "description": "QA 递交审批列表",
        "method": "GET",
        "path": "/manage_api/produce_demand/get_qa_reject_publish_list",
        "group": "递交",
        "params": _PROJECT_ALIAS_PARAMS
        + _USER_ROLE_PARAMS
        + _PAGINATION_PARAMS
        + ["apply_status", "apply_publish_start_time", "apply_publish_end_time"],
        "resolve_mode": "publish_apply",
        "upstream_params": [
            "project_id",
            "pm_id",
            "apply_status",
            "apply_publish_start_time",
            "apply_publish_end_time",
            "page",
            "limit",
        ],
        "default_limit": 20,
    },
    "get_bd_publish_list": {
        "description": "BD 视角项目递交列表",
        "method": "GET",
        "path": "/manage_api/produce_demand/get_bd_publish_list",
        "group": "递交",
        "params": _PROJECT_ALIAS_PARAMS
        + _PAGINATION_PARAMS
        + ["apply_status", "apply_publish_start_time", "apply_publish_end_time", "publish_submit_status"],
        "resolve_mode": "publish_apply",
        "upstream_params": [
            "project_id",
            "apply_status",
            "apply_publish_start_time",
            "apply_publish_end_time",
            "publish_submit_status",
            "page",
            "limit",
        ],
        "default_limit": 20,
    },
    "get_publish_demand_pool": {
        "description": "可用于递交的制作需求池",
        "method": "GET",
        "path": "/manage_api/produce_demand/get_publish_demand_pool",
        "group": "递交",
        "params": _PROJECT_ALIAS_PARAMS,
        "required_any_project": True,
        "resolve_mode": "project_only",
        "upstream_params": ["project_id"],
    },
    "get_project_moment_stat_chart_list": {
        "description": "项目动态统计-图表下钻列表",
        "method": "GET",
        "path": "/manage_api/data_export/get_project_moment_stat_chart_list",
        "group": "项目动态",
        "params": _PERIOD_PARAMS
        + _PROJECT_ALIAS_PARAMS
        + _USER_ROLE_PARAMS
        + _PAGINATION_PARAMS
        + ["chart_key", "dim_type", "dim_level", "dim_user_id", "dim_name", "dim_dept_id"],
        "required": ["period_type", "period_key", "chart_key"],
        "resolve_mode": "moment_chart",
        "upstream_params": [
            "period_type",
            "period_key",
            "chart_key",
            "project_id",
            "pm_id",
            "relation_uid",
            "dept_id",
            "user_id",
            "dim_type",
            "dim_level",
            "dim_user_id",
            "dim_name",
            "dim_dept_id",
            "page",
            "limit",
        ],
        "default_limit": 50,
    },
    "get_employee_estimate_list": {
        "description": "排期甘特-某人某日某任务工时花费",
        "method": "GET",
        "path": "/manage_api/data_export/get_employee_estimate_list",
        "group": "排期",
        "params": ["user_id", "user_name", "date", "task_id", "type_p"],
        "required": ["date", "task_id", "type_p"],
        "required_one_of": ["user_id", "user_name"],
        "resolve_mode": "employee_estimate",
        "upstream_params": ["user_id", "date", "task_id", "type_p"],
    },
    "get_demand_pool_list": {
        "description": "全量制作需求池列表",
        "method": "GET",
        "path": "/manage_api/produce_demand/get_demand_pool_list",
        "group": "递交",
        "params": _PAGINATION_PARAMS + ["status", "demand_module", "start_date", "end_date"],
        "upstream_params": ["status", "demand_module", "start_date", "end_date", "page", "limit"],
        "default_limit": 20,
    },
    "get_project_demand_pool_list": {
        "description": "某项目下的制作需求池列表",
        "method": "GET",
        "path": "/manage_api/produce_demand/get_project_demand_pool_list",
        "group": "递交",
        "params": _PROJECT_ALIAS_PARAMS + ["is_feedback", "demand_module", "status", "start_date", "end_date"],
        "required_any_project": True,
        "resolve_mode": "project_only",
        "upstream_params": ["project_id", "is_feedback", "demand_module", "status", "start_date", "end_date"],
    },
    "get_outsource_package_dimension_list": {
        "description": "外包项目维度统计列表",
        "method": "GET",
        "path": "/manage_api/outsource/get_package_dimension_list",
        "group": "外包供应商",
        "params": _PROJECT_ALIAS_PARAMS
        + _PAGINATION_PARAMS
        + ["name", "supplier_id", "status", "pm_name", "pm_user_id", "outsource_start_time", "outsource_end_time"],
        "resolve_mode": "outsource_dimension",
        "upstream_params": [
            "name",
            "sj_num",
            "project_id",
            "supplier_id",
            "status",
            "pm_user_id",
            "outsource_start_time",
            "outsource_end_time",
            "page",
            "limit",
        ],
        "default_limit": 20,
    },
    "get_outsource_asset_dimension_list": {
        "description": "外包资产维度统计列表",
        "method": "GET",
        "path": "/manage_api/outsource/get_asset_dimension_list",
        "group": "外包供应商",
        "params": _PROJECT_ALIAS_PARAMS
        + _PAGINATION_PARAMS
        + ["name", "supplier_id", "package_id", "outsource_package_id", "package_status", "task_status", "pm_name"],
        "resolve_mode": "outsource_dimension",
        "upstream_params": [
            "name",
            "sj_num",
            "project_id",
            "supplier_id",
            "outsource_package_id",
            "package_status",
            "task_status",
            "pm_user_id",
            "page",
            "limit",
        ],
        "default_limit": 20,
    },
    "get_supplier_alert_list": {
        "description": "供应商外包告警列表",
        "method": "GET",
        "path": "/manage_api/supplier_outsource/get_alert_list",
        "group": "外包供应商",
        "params": ["type", "supplier_ids", "include_closed"],
        "upstream_params": ["type", "supplier_ids", "include_closed"],
    },
    "get_supplier_accident_list": {
        "description": "供应商事故档案列表",
        "method": "GET",
        "path": "/manage_api/supplier_outsource/get_accident_list",
        "group": "外包供应商",
        "params": _PAGINATION_PARAMS + ["supplier_id", "start_date", "end_date"],
        "upstream_params": ["supplier_id", "start_date", "end_date", "page", "limit"],
        "default_limit": 20,
    },
    "get_my_annual_report": {
        "description": "我的工作年终/半年报告",
        "method": "GET",
        "path": "/manage_api/annual_report/get_my_report",
        "group": "其他",
        "params": ["report_type", "year"],
        "upstream_params": ["report_type", "year"],
    },
    "get_latest_report_meta": {
        "description": "最新工作报告入口信息",
        "method": "GET",
        "path": "/manage_api/annual_report/get_latest_report_meta",
        "group": "其他",
        "params": [],
        "upstream_params": [],
    },
    "get_bug_const": {
        "description": "BUG 类型/状态/等级等字典",
        "method": "GET",
        "path": "/manage_api/bug/get_bug_const",
        "group": "BUG",
        "params": [],
        "upstream_params": [],
        "dictionary": True,
    },
    "get_project_moment_config_list": {
        "description": "项目动态类型配置字典",
        "method": "GET",
        "path": "/manage_api/project_moment/get_config_list",
        "group": "项目动态",
        "params": [],
        "upstream_params": [],
        "dictionary": True,
    },
    "get_apply_demand_consts": {
        "description": "制作需求申请模块/类型等字典",
        "method": "GET",
        "path": "/manage_api/produce_demand/get_apply_demand_consts",
        "group": "制作需求",
        "params": [],
        "upstream_params": [],
        "dictionary": True,
    },
}

READ_ENHANCED_RESOLVE_MODES = frozenset(
    {
        "date_user_dept",
        "project_only",
        "user_project",
        "moment_chart",
        "employee_estimate",
        "unconfirmed",
        "publish_apply",
        "outsource_dimension",
        "user_search",
        "sj_num_only",
    }
)
