"""Non-project work hours and outsource/supplier read-only operations."""

from __future__ import annotations

from typing import Any, Callable

_PAGINATION_PARAMS = ["page", "limit", "page_size"]

_NOT_PROJECT_ID_PARAMS = [
    "not_project_id",
    "project_id",
    "not_project_name",
    "name",
]


def resolve_domains(mode: str, params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
        "not_project_list": _resolve_not_project_list,
        "not_project_id": _resolve_not_project_id,
        "not_project_demand": _resolve_not_project_demand,
        "not_project_task": _resolve_not_project_task,
        "not_project_work_hours": _resolve_not_project_work_hours,
        "outsource_package": _resolve_outsource_package,
        "outsource_overview": _resolve_outsource_overview,
        "supplier_outsource": _resolve_supplier_outsource,
        "supplier": _resolve_supplier,
    }
    handler = handlers.get(mode)
    if not handler:
        raise api_client.ClientError("validation_error", f"unknown resolve_mode: {mode}")
    return handler(dict(params))


def _apply_date_range(out: dict[str, Any]) -> dict[str, Any]:
    import api_client

    return api_client._apply_field_aliases(
        out,
        {
            "start_date": ("date_start", "from_date"),
            "end_date": ("date_end", "to_date"),
        },
    )


def _resolve_not_project_id_value(out: dict[str, Any], field: str = "project_id") -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(
        out,
        {
            field: ("not_project_id",),
            "not_project_name": ("name",),
        },
    )
    if out.get(field):
        return out
    name = out.pop("not_project_name", None) or out.pop("name", None)
    if not name:
        raise api_client.ClientError(
            "validation_error",
            "missing not_project_id / not_project_name / name",
        )
    payload = api_client.api_request(
        "GET",
        "/manage_api/not_project/get_list",
        {"name": str(name), "page": 1, "limit": 10},
    )
    items = api_client._list_items_from_response(payload)
    if not items:
        raise api_client.ClientError("resolve_failed", f"not_project not found: {name}")
    exact = [item for item in items if str(item.get("name", "")) == str(name)]
    chosen = exact[0] if exact else items[0]
    nid = chosen.get("id")
    if not nid:
        raise api_client.ClientError("resolve_failed", f"not_project id missing: {name}")
    out[field] = int(nid)
    return out


def _resolve_not_project_list(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    return api_client._apply_field_aliases(
        params,
        {
            "name": ("not_project_name", "keyword"),
            "category_id": ("category",),
        },
    )


def _resolve_not_project_id(params: dict[str, Any]) -> dict[str, Any]:
    out = dict(params)
    if out.get("id") in (None, "") and out.get("not_project_id"):
        out["id"] = out.pop("not_project_id")
    if out.get("id") in (None, ""):
        out = _resolve_not_project_id_value(out, "id")
        out.pop("project_id", None)
    return out


def _resolve_not_project_demand(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = _resolve_not_project_id_value(params)
    assignee = out.pop("assignee_name", None) or out.pop("user_name", None)
    if assignee and not out.get("assigned_to"):
        out["assigned_to"] = api_client.resolve_user_id(str(assignee))
    return out


def _resolve_not_project_task(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = _resolve_not_project_id_value(params)
    out = api_client._apply_field_aliases(out, {"pid": ("demand_id",)})
    assignee = out.pop("assignee_name", None)
    if assignee and not out.get("assigned_to"):
        out["assigned_to"] = api_client.resolve_user_id(str(assignee))
    return out


def _resolve_not_project_work_hours(params: dict[str, Any]) -> dict[str, Any]:
    out = _resolve_not_project_id_value(params)
    return _apply_date_range(out)


def _resolve_outsource_package(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = _apply_date_range(params)
    out = api_client._apply_field_aliases(
        out,
        {
            "sj_num": ("opportunity_no", "business_no"),
            "outsource_start_time": ("start_date",),
            "outsource_end_time": ("end_date",),
            "package_id": ("id",),
        },
    )
    if any(out.get(k) for k in ("project_name", "name")) and not out.get("project_id"):
        out["project_id"] = api_client.resolve_project_id(
            {
                "project_name": out.pop("project_name", None) or out.pop("name", None),
                "sj_num": out.get("sj_num"),
            }
        )
    pm_name = out.pop("pm_name", None)
    if pm_name and not out.get("pm_user_id"):
        out["pm_user_id"] = api_client.resolve_user_id(str(pm_name))
    if out.get("outsource_type") and not isinstance(out["outsource_type"], list):
        out["outsource_type"] = [
            part.strip() for part in str(out["outsource_type"]).split(",") if part.strip()
        ]
    return out


def _resolve_outsource_overview(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(
        params,
        {
            "sj_num": ("opportunity_no", "business_no"),
            "producer_scope": ("producer",),
            "score_scope": ("score_filter",),
        },
    )
    if any(out.get(k) for k in ("project_name", "name")) and not out.get("project_id"):
        out["project_id"] = api_client.resolve_project_id(
            {
                "project_name": out.pop("project_name", None) or out.pop("name", None),
                "sj_num": out.get("sj_num"),
            }
        )
    return out


def _resolve_supplier_outsource(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = _apply_date_range(params)
    out = api_client._apply_field_aliases(
        out,
        {
            "keyword": ("name",),
            "project": ("project_name",),
            "group": ("group_name", "team_name"),
            "no": ("package_no", "package_id"),
        },
    )
    if out.get("package_id") and not out.get("no"):
        out["no"] = str(out.pop("package_id"))
    elif out.get("package_no") and not out.get("no"):
        out["no"] = str(out.pop("package_no"))
    return out


def _resolve_supplier(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(
        params,
        {
            "company_name": ("supplier_name", "keyword", "name"),
            "id": ("supplier_id",),
        },
    )
    if out.get("id") and not out.get("supplier_id"):
        out["supplier_id"] = out["id"]
    return out


def _op(
    name: str,
    description: str,
    path: str,
    *,
    group: str,
    params: list[str] | None = None,
    required: list[str] | None = None,
    required_any: bool = False,
    required_any_not_project: bool = False,
    resolve_mode: str | None = None,
    upstream_params: list[str] | None = None,
    array_params: list[str] | None = None,
    default_limit: int = 20,
    paginated: bool = True,
    id_aliases: list[str] | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "description": description,
        "method": "GET",
        "path": path,
        "params": (params or []) + _PAGINATION_PARAMS,
        "group": group,
        "upstream_params": upstream_params or [],
        "default_limit": default_limit,
        "paginated": paginated,
    }
    if required:
        meta["required"] = required
    if required_any:
        meta["required_any"] = True
    if required_any_not_project:
        meta["required_any_not_project"] = True
    if resolve_mode:
        meta["resolve_mode"] = resolve_mode
    if array_params:
        meta["array_params"] = array_params
    if id_aliases:
        meta["id_aliases"] = id_aliases
    return meta


DOMAIN_RESOLVE_MODES = frozenset(
    {
        "not_project_list",
        "not_project_id",
        "not_project_demand",
        "not_project_task",
        "not_project_work_hours",
        "outsource_package",
        "outsource_overview",
        "supplier_outsource",
        "supplier",
    }
)

DOMAIN_OPERATIONS: dict[str, dict[str, Any]] = {
  # --- 非项目 ---
  "get_not_project_list": _op(
      "get_not_project_list",
      "非项目列表",
      "/manage_api/not_project/get_list",
      group="非项目",
      params=["name", "not_project_name", "sj_num", "status", "category_id", "category", "is_all"],
      resolve_mode="not_project_list",
      upstream_params=["name", "sj_num", "status", "category_id", "is_all", "page", "limit"],
  ),
  "get_not_project_info": _op(
      "get_not_project_info",
      "非项目详情",
      "/manage_api/not_project/get_info",
      group="非项目",
      params=["id", "not_project_id", "not_project_name", "name"],
      required=["id", "not_project_id", "not_project_name", "name"],
      required_any=True,
      resolve_mode="not_project_id",
      upstream_params=["id"],
      paginated=False,
  ),
  "get_not_project_select_list": _op(
      "get_not_project_select_list",
      "非项目下拉列表",
      "/manage_api/not_project/get_select_list",
      group="非项目",
      params=["name", "not_project_name", "sj_num"],
      resolve_mode="not_project_list",
      upstream_params=["name", "sj_num"],
      paginated=False,
  ),
  "get_not_project_display_tree": _op(
      "get_not_project_display_tree",
      "非项目展示树（分类+非项目）",
      "/manage_api/not_project/get_display_tree",
      group="非项目",
      params=["name", "not_project_name"],
      resolve_mode="not_project_list",
      upstream_params=["name"],
      paginated=False,
  ),
  "get_not_project_category_list": _op(
      "get_not_project_category_list",
      "非项目分类列表",
      "/manage_api/not_project_category/get_list",
      group="非项目",
      params=["name", "is_all"],
      upstream_params=["name", "is_all", "page", "limit"],
  ),
  "get_not_project_demand_list": _op(
      "get_not_project_demand_list",
      "非项目需求列表",
      "/manage_api/project_not_task/get_demand_list",
      group="非项目",
      params=_NOT_PROJECT_ID_PARAMS + ["protype", "status", "assigned_to", "assignee_name", "user_name", "name"],
      required_any_not_project=True,
      resolve_mode="not_project_demand",
      upstream_params=["project_id", "protype", "status", "assigned_to", "name", "page", "limit"],
  ),
  "get_not_project_demand_info": _op(
      "get_not_project_demand_info",
      "非项目需求详情",
      "/manage_api/project_not_task/get_demand_info",
      group="非项目",
      params=["id", "demand_id"],
      required=["id", "demand_id"],
      required_any=True,
      upstream_params=["id"],
      paginated=False,
      id_aliases=["demand_id"],
  ),
  "get_not_project_task_list": _op(
      "get_not_project_task_list",
      "非项目需求下任务列表",
      "/manage_api/project_not_task/get_task_list",
      group="非项目",
      params=_NOT_PROJECT_ID_PARAMS
      + ["pid", "demand_id", "name", "desc", "status", "assigned_to", "assignee_name", "one_type", "estimate_type"],
      required=["pid", "demand_id"],
      required_any=True,
      required_any_not_project=True,
      resolve_mode="not_project_task",
      upstream_params=["project_id", "pid", "name", "desc", "status", "assigned_to", "one_type", "estimate_type", "page", "limit"],
      paginated=False,
  ),
  "get_not_project_task_info": _op(
      "get_not_project_task_info",
      "非项目任务详情",
      "/manage_api/project_not_task/get_task_info",
      group="非项目",
      params=["id", "task_id"],
      required=["id", "task_id"],
      required_any=True,
      upstream_params=["id"],
      paginated=False,
      id_aliases=["task_id"],
  ),
  "get_not_project_work_hours": _op(
      "get_not_project_work_hours",
      "非项目工时花费列表",
      "/manage_api/project_not_task_estimate/get_estimate_list_by_project_id",
      group="非项目",
      params=_NOT_PROJECT_ID_PARAMS + ["start_date", "end_date", "date_start", "date_end"],
      required_any_not_project=True,
      resolve_mode="not_project_work_hours",
      upstream_params=["project_id", "start_date", "end_date", "page", "limit"],
  ),
  "get_not_project_task_estimate_list": _op(
      "get_not_project_task_estimate_list",
      "非项目单任务工时明细",
      "/manage_api/project_not_task_estimate/get_task_estimate_list",
      group="非项目",
      params=["task_id", "id"],
      required=["task_id", "id"],
      required_any=True,
      upstream_params=["task_id", "page", "limit"],
  ),
  # --- 模型外包管理 ---
  "get_outsource_package_list": _op(
      "get_outsource_package_list",
      "模型外包发包列表",
      "/manage_api/outsource/get_package_list",
      group="外包",
      params=[
          "name", "sj_num", "opportunity_no", "business_no", "project_id", "project_name",
          "supplier_id", "status", "pm_user_id", "pm_name", "outsource_type",
          "is_self_made", "outsource_start_time", "outsource_end_time", "start_date", "end_date",
      ],
      resolve_mode="outsource_package",
      upstream_params=[
          "name", "sj_num", "project_id", "supplier_id", "status", "pm_user_id",
          "outsource_type", "is_self_made", "outsource_start_time", "outsource_end_time",
          "page", "limit",
      ],
      array_params=["outsource_type"],
  ),
  "get_outsource_package_detail": _op(
      "get_outsource_package_detail",
      "模型外包发包详情",
      "/manage_api/outsource/get_package_detail",
      group="外包",
      params=["id", "package_id"],
      required=["id", "package_id"],
      required_any=True,
      upstream_params=["id"],
      paginated=False,
      id_aliases=["package_id"],
  ),
  "get_outsource_data_overview": _op(
      "get_outsource_data_overview",
      "模型外包数据总览",
      "/manage_api/outsource/get_data_overview",
      group="外包",
      params=[
          "sj_num", "opportunity_no", "business_no", "project_id", "project_name",
          "period", "producer_scope", "producer", "score_scope", "score_filter",
      ],
      resolve_mode="outsource_overview",
      upstream_params=["sj_num", "project_id", "period", "producer_scope", "score_scope"],
      paginated=False,
  ),
  "get_outsource_data_overview_package_list": _op(
      "get_outsource_data_overview_package_list",
      "模型外包总览-发包下钻列表",
      "/manage_api/outsource/get_data_overview_package_list",
      group="外包",
      params=[
          "sj_num", "project_id", "project_name", "name", "producer_name",
          "status_label", "stack_status", "outsource_type", "is_self_made",
          "outsource_start_time", "outsource_end_time", "start_date", "end_date",
      ],
      resolve_mode="outsource_overview",
      upstream_params=[
          "sj_num", "project_id", "name", "producer_name", "status_label",
          "stack_status", "outsource_type", "is_self_made",
          "outsource_start_time", "outsource_end_time", "page", "limit",
      ],
      array_params=["outsource_type"],
  ),
  "get_outsource_settlement_list": _op(
      "get_outsource_settlement_list",
      "模型外包结算列表",
      "/manage_api/outsource_settlement/get_settlement_list",
      group="外包",
      params=["outsource_package_id", "package_id", "supplier_id", "status"],
      resolve_mode="outsource_package",
      upstream_params=["outsource_package_id", "supplier_id", "status", "page", "limit"],
  ),
  "get_outsource_settlement_detail": _op(
      "get_outsource_settlement_detail",
      "模型外包结算详情",
      "/manage_api/outsource_settlement/get_settlement_detail",
      group="外包",
      params=["id", "settlement_id"],
      required=["id", "settlement_id"],
      required_any=True,
      upstream_params=["id"],
      paginated=False,
      id_aliases=["settlement_id"],
  ),
  # --- 供应商外包看板 ---
  "get_supplier_outsource_overview": _op(
      "get_supplier_outsource_overview",
      "供应商外包-模型制作概览",
      "/manage_api/supplier_outsource/get_overview",
      group="供应商",
      params=["group", "group_name", "team_name", "status", "supplier_id", "start_date", "end_date"],
      resolve_mode="supplier_outsource",
      upstream_params=["group", "status", "supplier_id", "start_date", "end_date"],
      paginated=False,
  ),
  "get_supplier_outsource_work_ledger": _op(
      "get_supplier_outsource_work_ledger",
      "供应商外包-发包明细台账",
      "/manage_api/supplier_outsource/get_work_ledger",
      group="供应商",
      params=["mode", "keyword", "status", "person", "start_date", "end_date"],
      resolve_mode="supplier_outsource",
      upstream_params=["mode", "keyword", "status", "person", "start_date", "end_date", "page", "limit"],
  ),
  "get_supplier_outsource_package_list": _op(
      "get_supplier_outsource_package_list",
      "供应商外包-发包列表",
      "/manage_api/supplier_outsource/get_package_list",
      group="供应商",
      params=[
          "keyword", "project", "project_name", "supplier_id", "group", "group_name",
          "type", "status", "start_date", "end_date",
      ],
      resolve_mode="supplier_outsource",
      upstream_params=["keyword", "project", "supplier_id", "group", "type", "status", "start_date", "end_date", "page", "limit"],
  ),
  "get_supplier_outsource_package_detail": _op(
      "get_supplier_outsource_package_detail",
      "供应商外包-发包详情（编号）",
      "/manage_api/supplier_outsource/get_package_detail",
      group="供应商",
      params=["no", "package_no", "package_id"],
      required=["no", "package_no", "package_id"],
      required_any=True,
      resolve_mode="supplier_outsource",
      upstream_params=["no"],
      paginated=False,
  ),
  "get_supplier_outsource_board": _op(
      "get_supplier_outsource_board",
      "供应商外包-供应商看板",
      "/manage_api/supplier_outsource/get_supplier_board",
      group="供应商",
      params=["keyword", "name"],
      resolve_mode="supplier_outsource",
      upstream_params=["keyword"],
      paginated=False,
  ),
  "get_supplier_outsource_profile": _op(
      "get_supplier_outsource_profile",
      "供应商外包-供应商画像",
      "/manage_api/supplier_outsource/get_supplier_profile",
      group="供应商",
      params=["supplier_id", "id"],
      required=["supplier_id", "id"],
      required_any=True,
      resolve_mode="supplier",
      upstream_params=["supplier_id"],
      paginated=False,
  ),
  "get_supplier_outsource_capability_matrix": _op(
      "get_supplier_outsource_capability_matrix",
      "供应商外包-能力矩阵",
      "/manage_api/supplier_outsource/get_capability_matrix",
      group="供应商",
      params=[],
      upstream_params=[],
      paginated=False,
  ),
  "get_supplier_outsource_filter_options": _op(
      "get_supplier_outsource_filter_options",
      "供应商外包-筛选字典",
      "/manage_api/supplier_outsource/get_filter_options",
      group="供应商",
      params=[],
      upstream_params=[],
      paginated=False,
  ),
  "get_supplier_list": _op(
      "get_supplier_list",
      "供应商档案列表",
      "/manage_api/supplier/get_supplier_list",
      group="供应商",
      params=["company_name", "supplier_name", "keyword", "name", "status", "level"],
      resolve_mode="supplier",
      upstream_params=["company_name", "status", "level", "page", "limit"],
  ),
  "get_supplier_detail": _op(
      "get_supplier_detail",
      "供应商档案详情",
      "/manage_api/supplier/get_supplier_detail",
      group="供应商",
      params=["id", "supplier_id"],
      required=["id", "supplier_id"],
      required_any=True,
      resolve_mode="supplier",
      upstream_params=["id"],
      paginated=False,
      id_aliases=["supplier_id"],
  ),
}
