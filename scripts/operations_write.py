"""Interactive write operations (dry_run → confirm → POST)."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Callable

from operations_domains import _resolve_not_project_id_value

_MOMENT_MODULE_MAP = {
    "": "",
    "meet": "meet",
    "会议": "meet",
    "meeting": "meet",
    "risk": "risk",
    "风险": "risk",
    "problem": "problem",
    "问题": "problem",
}

_CONFIRM_TYPE_MAP = {
    "confirmtaskestimate": "ConfirmTaskEstimate",
    "confirmnottaskestimate": "ConfirmNotTaskEstimate",
    "project": "ConfirmTaskEstimate",
    "task": "ConfirmTaskEstimate",
    "项目": "ConfirmTaskEstimate",
    "项目工时": "ConfirmTaskEstimate",
    "not_project": "ConfirmNotTaskEstimate",
    "非项目": "ConfirmNotTaskEstimate",
    "非项目工时": "ConfirmNotTaskEstimate",
}

_MODULE_LABEL = {"meet": "会议", "risk": "风险", "problem": "问题"}
_CONFIRM_LABEL = {
    "ConfirmTaskEstimate": "项目工时",
    "ConfirmNotTaskEstimate": "非项目工时",
}

# 同一任务（同一填写人）只能有一条工时记录；已存在则必须改走 update
UNIQUE_TASK_ESTIMATE_OPS: dict[str, dict[str, Any]] = {
    "add_project_task_estimate": {
        "kind": "项目",
        "update_operation": "update_project_task_estimate",
        "list_paths": (
            "/manage_api/project_task_estimate/get_task_estimate_list",
            "/manage_api/project_task_estimate/get_estimate_list",
        ),
    },
    "add_not_project_estimate": {
        "kind": "非项目",
        "update_operation": "update_not_project_estimate",
        "list_paths": (
            "/manage_api/project_not_task_estimate/get_task_estimate_list",
        ),
    },
}


def _parse_estimate_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _estimate_items_from_payload(payload: Any) -> list[dict[str, Any]]:
    from skill_enhancements import extract_page_items

    items, _ = extract_page_items(payload)
    out = [item for item in items if isinstance(item, dict)]
    if out:
        return out
    if not isinstance(payload, dict):
        return []
    data = payload.get("data", payload)
    if isinstance(data, dict):
        for key in ("estimate_list", "estimates", "list", "rows"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        nested = data.get("data")
        if isinstance(nested, dict):
            for key in ("estimate_list", "estimates", "list"):
                value = nested.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
    return []


def find_existing_task_estimate(
    *,
    list_paths: tuple[str, ...] | list[str],
    task_id: int,
    user_id: int | None,
    token: str | None,
    api_request_fn,
) -> dict[str, Any] | None:
    """Return the existing estimate row for this task (optionally scoped to user)."""
    import api_client

    last_error: Exception | None = None
    for path in list_paths:
        try:
            payload = api_request_fn(
                "GET",
                path,
                {"task_id": task_id, "page": 1, "limit": 100},
                token=token,
            )
        except (api_client.ClientError, OSError) as exc:
            last_error = exc
            continue
        items = _estimate_items_from_payload(payload)
        matches: list[dict[str, Any]] = []
        for item in items:
            item_task = _parse_estimate_int(item.get("task_id"))
            if item_task is not None and item_task != task_id:
                continue
            item_user = _parse_estimate_int(
                item.get("user_id") or item.get("uid") or item.get("create_user_id")
            )
            if user_id is not None and item_user is not None and item_user != user_id:
                continue
            matches.append(item)
        if user_id is not None:
            same_user = [
                item
                for item in matches
                if _parse_estimate_int(
                    item.get("user_id") or item.get("uid") or item.get("create_user_id")
                )
                == user_id
            ]
            if same_user:
                matches = same_user
        return matches[0] if matches else None
    _ = last_error
    return None


def duplicate_estimate_payload(
    *,
    operation: str,
    task_id: int,
    existing: dict[str, Any],
    update_operation: str,
    kind: str,
) -> dict[str, Any]:
    existing_id = _parse_estimate_int(
        existing.get("id") or existing.get("estimate_id") or existing.get("work_hour_id")
    )
    return {
        "error": "duplicate_estimate",
        "detail": (
            f"该{kind}任务（task_id={task_id}）已有工时记录，同一任务只能有一条。"
            f"请改用 {update_operation} 更新已有记录，不要再次 add。"
        ),
        "operation": operation,
        "task_id": task_id,
        "existing_estimate_id": existing_id,
        "existing": {
            "id": existing_id,
            "task_id": _parse_estimate_int(existing.get("task_id")) or task_id,
            "date": existing.get("date"),
            "consumed": existing.get("consumed"),
            "remark": existing.get("remark"),
            "user_id": existing.get("user_id") or existing.get("uid"),
        },
        "next_operation": update_operation,
        "message": "同一任务已有工时，请改为更新而不是新增。",
        "agent_instruction": (
            f"禁止再次调用 {operation}。"
            f"向用户说明该任务已有工时记录（id={existing_id}），"
            f"确认要改工时后调用 {update_operation}，"
            f"--param id {existing_id} 并带上新的 consumed/remark/date。"
        ),
        "example_command": (
            f"python3 scripts/api_client.py {update_operation} "
            f"--param id {existing_id} --param consumed <工时> --param remark <备注>"
        ),
    }


def enforce_unique_task_estimate(
    operation: str,
    body: dict[str, Any],
    *,
    token: str | None,
    api_request_fn,
    actor_user_id: int | None = None,
) -> None:
    spec = UNIQUE_TASK_ESTIMATE_OPS.get(operation)
    if not spec:
        return
    task_id = _parse_estimate_int(body.get("task_id"))
    if task_id is None:
        return
    user_id = _parse_estimate_int(body.get("user_id")) or actor_user_id
    existing = find_existing_task_estimate(
        list_paths=spec["list_paths"],
        task_id=task_id,
        user_id=user_id,
        token=token,
        api_request_fn=api_request_fn,
    )
    if not existing:
        return
    import api_client

    payload = duplicate_estimate_payload(
        operation=operation,
        task_id=task_id,
        existing=existing,
        update_operation=str(spec["update_operation"]),
        kind=str(spec["kind"]),
    )
    raise api_client.ClientError("duplicate_estimate", json.dumps(payload, ensure_ascii=False))


def resolve_write(mode: str, params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
        "confirm_work_hours": _resolve_confirm_work_hours,
        "add_project_moment": _resolve_add_project_moment,
        "add_project_task_estimate": _resolve_add_project_task_estimate,
        "confirm_user_work_hours": _resolve_confirm_user_work_hours,
        "approve_work_hour_batch": _resolve_approve_work_hour_batch,
        "add_not_project_estimate": _resolve_add_not_project_estimate,
        "update_project_task_estimate": _resolve_update_project_task_estimate,
        "update_project_moment": _resolve_update_project_moment,
        "add_bug": _resolve_add_bug,
        "apply_publish": _resolve_apply_publish,
        "reject_publish": _resolve_reject_publish,
        "task_action": _resolve_task_action,
        "save_project_overview_value": _resolve_save_project_overview_value,
        "add_not_project_demand": _resolve_add_not_project_demand,
        "add_not_project_task": _resolve_add_not_project_task,
        "finish_not_project_task": _resolve_finish_not_project_task,
        "update_not_project_estimate": _resolve_update_not_project_estimate,
        "add_apply_demand": _resolve_add_apply_demand,
        "add_demand_pool": _resolve_add_demand_pool,
        "add_feedback_demand_pool": _resolve_add_feedback_demand_pool,
        "approve_publish_apply": _resolve_approve_publish_apply,
    }
    handler = handlers.get(mode)
    if not handler:
        raise api_client.ClientError("validation_error", f"unknown write resolve_mode: {mode}")
    return handler(dict(params))


def _resolve_confirm_work_hours(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(
        params, {"id": ("estimate_id", "work_hour_id")}
    )
    if out.get("id") in (None, ""):
        for key in ("estimate_id", "work_hour_id"):
            if out.get(key) not in (None, ""):
                out["id"] = int(out[key])
                break
    out.pop("estimate_id", None)
    out.pop("work_hour_id", None)
    raw_type = str(out.get("confirm_type", "")).strip()
    key = raw_type.replace(" ", "").lower()
    if key in _CONFIRM_TYPE_MAP:
        out["confirm_type"] = _CONFIRM_TYPE_MAP[key]
    elif raw_type in _CONFIRM_TYPE_MAP.values():
        out["confirm_type"] = raw_type
    elif raw_type:
        out["confirm_type"] = raw_type
    if out.get("id") not in (None, ""):
        out["id"] = int(out["id"])
    ids_raw = out.pop("ids", None)
    if ids_raw not in (None, ""):
        import api_client

        out["_batch_ids"] = api_client._parse_int_list(ids_raw)
    return out


def _parse_json_value(value: Any) -> Any:
    if value in (None, ""):
        return value
    if isinstance(value, (list, dict)):
        return value
    text = str(value).strip()
    if text.startswith("[") or text.startswith("{"):
        return json.loads(text)
    return value


def _resolve_confirm_user_work_hours(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = dict(params)
    user_name = out.pop("user_name", None)
    if user_name and not out.get("user_id"):
        out["user_id"] = int(api_client.resolve_user_id(str(user_name)))
    if not out.get("date"):
        out["date"] = date.today().isoformat()
    if out.get("user_id") not in (None, ""):
        out["user_id"] = int(out["user_id"])
    return out


def _resolve_approve_work_hour_batch(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = dict(params)
    user_name = out.pop("user_name", None)
    if user_name and not out.get("user_id"):
        out["user_id"] = int(api_client.resolve_user_id(str(user_name)))
    if out.get("user_id") not in (None, ""):
        out["user_id"] = int(out["user_id"])
    project_ids = out.pop("project_ids", None) or out.pop("id_arr_one", None)
    not_project_ids = out.pop("not_project_ids", None) or out.pop("id_arr_two", None)
    if project_ids not in (None, ""):
        out["id_arr_one"] = api_client._parse_int_list(project_ids)
    if not_project_ids not in (None, ""):
        out["id_arr_two"] = api_client._parse_int_list(not_project_ids)
    if out.get("module_sort") not in (None, ""):
        out["module_sort"] = int(out["module_sort"])
    return out


def _resolve_add_not_project_estimate(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(
        params,
        {
            "date": ("work_date", "start_date"),
            "consumed": ("hours", "work_hours"),
            "remark": ("note", "description"),
            "task_id": ("id",),
        },
    )
    if not out.get("date"):
        out["date"] = date.today().isoformat()
    if out.get("consumed") not in (None, ""):
        out["consumed"] = float(out["consumed"])
    user_name = out.pop("user_name", None)
    if user_name and not out.get("user_id"):
        out["user_id"] = int(api_client.resolve_user_id(str(user_name)))
    if out.get("task_id") in (None, "") and out.get("id") not in (None, ""):
        out["task_id"] = int(out.pop("id"))
    elif out.get("task_id") not in (None, ""):
        out["task_id"] = int(out["task_id"])
    if out.get("user_id") not in (None, ""):
        out["user_id"] = int(out["user_id"])
    return out


def _resolve_update_project_task_estimate(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(
        params,
        {
            "id": ("estimate_id", "work_hour_id"),
            "consumed": ("hours", "work_hours"),
            "remark": ("note", "description"),
            "date": ("work_date",),
        },
    )
    if out.get("id") in (None, ""):
        for key in ("estimate_id", "work_hour_id"):
            if out.get(key) not in (None, ""):
                out["id"] = int(out[key])
                break
    out.pop("estimate_id", None)
    out.pop("work_hour_id", None)
    if out.get("id") not in (None, ""):
        out["id"] = int(out["id"])
    if out.get("consumed") not in (None, ""):
        out["consumed"] = float(out["consumed"])
    return out


def _resolve_update_project_moment(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(params, {"id": ("moment_id",)})
    if out.get("id") in (None, "") and out.get("moment_id") not in (None, ""):
        out["id"] = int(out.pop("moment_id"))
    elif out.get("id") not in (None, ""):
        out["id"] = int(out["id"])
    user_names = out.pop("user_names", None) or out.pop("user_name", None)
    if user_names and not out.get("user_id"):
        ids: list[int] = []
        for part in str(user_names).replace("，", ",").split(","):
            name = part.strip()
            if name:
                ids.append(int(api_client.resolve_user_id(name)))
        out["user_id"] = ids
    elif out.get("user_id") and not isinstance(out.get("user_id"), list):
        out["user_id"] = api_client._parse_int_list(out["user_id"])
    return out


def _resolve_add_bug(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(
        params,
        {"project_name": ("name",), "sj_num": ("opportunity_no", "business_no")},
    )
    if not out.get("project_id"):
        out["project_id"] = int(api_client.resolve_project_id(out))
    for key in ("project_name", "name", "sj_num", "opportunity_no", "business_no"):
        out.pop(key, None)
    if not out.get("submit_time"):
        out["submit_time"] = date.today().isoformat()
    for name_key, id_key in (
        ("tester_name", "tester"),
        ("assigned_to_name", "assigned_to"),
        ("assignee_name", "assigned_to"),
    ):
        nm = out.pop(name_key, None)
        if nm and not out.get(id_key):
            out[id_key] = int(api_client.resolve_user_id(str(nm)))
    for key in ("project_id", "task_id", "bug_type", "bug_status", "bug_level", "priority", "tester", "assigned_to"):
        if out.get(key) not in (None, ""):
            out[key] = int(out[key])
    return out


def _resolve_apply_publish(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(
        params,
        {"project_name": ("name",), "sj_num": ("opportunity_no", "business_no")},
    )
    if not out.get("project_id"):
        out["project_id"] = int(api_client.resolve_project_id(out))
    if not out.get("sj_num"):
        payload = api_client.api_request(
            "GET",
            "/manage_api/project/get_project_info",
            {"id": str(out["project_id"])},
        )
        data = api_client._business_data(payload)
        info = data.get("info") if isinstance(data, dict) else {}
        if isinstance(info, dict) and info.get("sj_num"):
            out["sj_num"] = str(info["sj_num"])
        if isinstance(info, dict) and info.get("name") and not out.get("project_name"):
            out["project_name"] = str(info["name"])
    for key in ("name", "opportunity_no", "business_no"):
        out.pop(key, None)
    pool = out.pop("demand_pool_id", None) or out.pop("demand_pool_ids", None)
    if pool not in (None, ""):
        out["demand_pool_id"] = api_client._parse_int_list(pool)
    if out.get("publish_dijiao_version") not in (None, ""):
        out["publish_dijiao_version"] = int(out["publish_dijiao_version"])
    if out.get("project_id") not in (None, ""):
        out["project_id"] = int(out["project_id"])
    return out


def _resolve_reject_publish(params: dict[str, Any]) -> dict[str, Any]:
    out = dict(params)
    if out.get("id") in (None, "") and out.get("publish_id") not in (None, ""):
        out["id"] = int(out.pop("publish_id"))
    elif out.get("id") not in (None, ""):
        out["id"] = int(out["id"])
    return out


def _resolve_task_action(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(params, {"id": ("task_id",)})
    if out.get("id") in (None, "") and out.get("task_id") not in (None, ""):
        out["id"] = int(out.pop("task_id"))
    elif out.get("id") not in (None, ""):
        out["id"] = int(out["id"])
    assigned = out.pop("assigned_to_names", None) or out.pop("assigned_to_name", None)
    if assigned and not out.get("assigned_to"):
        ids = []
        for part in str(assigned).replace("，", ",").split(","):
            name = part.strip()
            if name:
                ids.append(int(api_client.resolve_user_id(name)))
        out["assigned_to"] = ids
    elif out.get("assigned_to") and not isinstance(out.get("assigned_to"), list):
        out["assigned_to"] = api_client._parse_int_list(out["assigned_to"])
    return out


def _resolve_save_project_overview_value(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(
        params,
        {"project_name": ("name",), "sj_num": ("opportunity_no", "business_no")},
    )
    if not out.get("project_id"):
        out["project_id"] = int(api_client.resolve_project_id(out))
    for key in ("project_name", "name", "sj_num", "opportunity_no", "business_no"):
        out.pop(key, None)
    rows = out.get("rows")
    out["rows"] = _parse_json_value(rows)
    if out.get("project_id") not in (None, ""):
        out["project_id"] = int(out["project_id"])
    return out


def _resolve_assigned_to_list(out: dict[str, Any], name_key: str = "assigned_to_names") -> dict[str, Any]:
    import api_client

    names = out.pop(name_key, None) or out.pop("assigned_to_name", None) or out.pop("user_names", None)
    if names and not out.get("assigned_to"):
        ids: list[int] = []
        for part in str(names).replace("，", ",").split(","):
            name = part.strip()
            if name:
                ids.append(int(api_client.resolve_user_id(name)))
        out["assigned_to"] = ids
    elif out.get("assigned_to") and not isinstance(out.get("assigned_to"), list):
        out["assigned_to"] = api_client._parse_int_list(out["assigned_to"])
    return out


def _resolve_project_apply_fields(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(
        params,
        {"project_name": ("name",), "sj_num": ("opportunity_no", "business_no")},
    )
    if not out.get("project_id"):
        out["project_id"] = int(api_client.resolve_project_id(out))
    if not out.get("sj_num"):
        payload = api_client.api_request(
            "GET",
            "/manage_api/project/get_project_info",
            {"id": str(out["project_id"])},
        )
        data = api_client._business_data(payload)
        info = data.get("info") if isinstance(data, dict) else {}
        if isinstance(info, dict):
            if info.get("sj_num"):
                out["sj_num"] = str(info["sj_num"])
            if info.get("name") and not out.get("project_name"):
                out["project_name"] = str(info["name"])
    for key in ("name", "opportunity_no", "business_no"):
        out.pop(key, None)
    if out.get("project_id") not in (None, ""):
        out["project_id"] = int(out["project_id"])
    return out


def _resolve_demand_pool_params(params: list[Any], *, feedback: bool) -> list[dict[str, Any]]:
    import api_client

    resolved: list[dict[str, Any]] = []
    for raw in params:
        if not isinstance(raw, dict):
            raise api_client.ClientError("validation_error", "params must be a JSON array of objects")
        item = dict(raw)
        if feedback:
            item["demand_type"] = "反馈"
        executor_name = item.pop("executor_name", None)
        if executor_name and not item.get("executor"):
            uid = int(api_client.resolve_user_id(str(executor_name)))
            item["executor"] = uid
            item.setdefault("executor_name", str(executor_name))
        if item.get("executor") not in (None, ""):
            item["executor"] = int(item["executor"])
        if item.get("cost") not in (None, ""):
            item["cost"] = float(item["cost"])
        if item.get("option_ids") and not isinstance(item.get("option_ids"), list):
            item["option_ids"] = api_client._parse_int_list(item["option_ids"])
        resolved.append(item)
    return resolved


def _resolve_add_not_project_demand(params: dict[str, Any]) -> dict[str, Any]:
    out = _resolve_not_project_id_value(dict(params))
    out = _resolve_assigned_to_list(out)
    if out.get("assigned_to") and isinstance(out.get("assigned_to"), list) and len(out["assigned_to"]) == 1:
        out["assigned_to"] = [int(x) for x in out["assigned_to"]]
    elif out.get("assigned_to"):
        out["assigned_to"] = [int(x) for x in out["assigned_to"]]
    if out.get("project_id") not in (None, ""):
        out["project_id"] = int(out["project_id"])
    if out.get("plan_hour") not in (None, ""):
        out["plan_hour"] = float(out["plan_hour"])
    return out


def _resolve_add_not_project_task(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = _resolve_not_project_id_value(dict(params))
    out = api_client._apply_field_aliases(out, {"pid": ("demand_id",)})
    assignee = out.pop("assignee_name", None) or out.pop("user_name", None)
    if assignee and not out.get("assigned_to"):
        out["assigned_to"] = int(api_client.resolve_user_id(str(assignee)))
    if out.get("project_id") not in (None, ""):
        out["project_id"] = int(out["project_id"])
    if out.get("pid") not in (None, ""):
        out["pid"] = int(out["pid"])
    if out.get("assigned_to") not in (None, ""):
        out["assigned_to"] = int(out["assigned_to"])
    if out.get("plan_hour") not in (None, ""):
        out["plan_hour"] = float(out["plan_hour"])
    if out.get("option_ids") and not isinstance(out.get("option_ids"), list):
        out["option_ids"] = api_client._parse_int_list(out["option_ids"])
    return out


def _resolve_finish_not_project_task(params: dict[str, Any]) -> dict[str, Any]:
    out = dict(params)
    if out.get("id") in (None, "") and out.get("task_id") not in (None, ""):
        out["id"] = int(out.pop("task_id"))
    elif out.get("id") not in (None, ""):
        out["id"] = int(out["id"])
    return out


def _resolve_update_not_project_estimate(params: dict[str, Any]) -> dict[str, Any]:
    out = _resolve_update_project_task_estimate(params)
    return out


def _resolve_add_apply_demand(params: dict[str, Any]) -> dict[str, Any]:
    out = _resolve_project_apply_fields(params)
    modules = out.pop("apply_demand_module", None) or out.pop("apply_demand_modules", None)
    if modules not in (None, ""):
        if isinstance(modules, list):
            out["apply_demand_module"] = modules
        else:
            out["apply_demand_module"] = [
                m.strip() for m in str(modules).replace("，", ",").split(",") if m.strip()
            ]
    return out


def _resolve_add_demand_pool(params: dict[str, Any], *, feedback: bool = False) -> dict[str, Any]:
    import api_client

    out = dict(params)
    a_id = out.pop("a_id", None) or out.pop("apply_demand_id", None)
    if a_id in (None, ""):
        raise api_client.ClientError("validation_error", "missing a_id / apply_demand_id")
    out["a_id"] = int(a_id)
    raw_params = out.pop("params", None)
    parsed = _parse_json_value(raw_params)
    if not isinstance(parsed, list) or not parsed:
        raise api_client.ClientError("validation_error", "params must be a non-empty JSON array")
    out["params"] = _resolve_demand_pool_params(parsed, feedback=feedback)
    return out


def _resolve_add_feedback_demand_pool(params: dict[str, Any]) -> dict[str, Any]:
    return _resolve_add_demand_pool(params, feedback=True)


def _resolve_approve_publish_apply(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = dict(params)
    if out.get("apply_publish_id") in (None, "") and out.get("id") not in (None, ""):
        out["apply_publish_id"] = int(out.pop("id"))
    elif out.get("apply_publish_id") not in (None, ""):
        out["apply_publish_id"] = int(out["apply_publish_id"])
    out.pop("publish_id", None)
    if not out.get("sj_num"):
        out = _resolve_project_apply_fields(out)
    else:
        out.pop("project_id", None)
        out.pop("project_name", None)
    if out.get("publish_submit_type") and not isinstance(out.get("publish_submit_type"), list):
        out["publish_submit_type"] = [
            x.strip() for x in str(out["publish_submit_type"]).replace("，", ",").split(",") if x.strip()
        ]
    if out.get("publish_dijiao_version") not in (None, ""):
        out["publish_dijiao_version"] = int(out["publish_dijiao_version"])
    if out.get("project_type") not in (None, ""):
        out["project_type"] = int(out["project_type"])
    if out.get("contain_logo") not in (None, ""):
        out["contain_logo"] = int(out["contain_logo"])
    if out.get("linshi_status") not in (None, ""):
        out["linshi_status"] = int(out["linshi_status"])
    pool = out.pop("selected_demand_pool_ids", None) or out.pop("demand_pool_id", None)
    if pool not in (None, ""):
        out["selected_demand_pool_ids"] = api_client._parse_int_list(pool)
    return out


def _resolve_add_project_moment(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(
        params,
        {
            "project_name": ("name",),
            "sj_num": ("opportunity_no", "business_no"),
        },
    )
    if not out.get("project_id"):
        out["project_id"] = int(api_client.resolve_project_id(out))
    for key in ("project_name", "name", "sj_num", "opportunity_no", "business_no"):
        out.pop(key, None)
    if "module" in out:
        mod = str(out["module"]).strip()
        out["module"] = _MOMENT_MODULE_MAP.get(mod, _MOMENT_MODULE_MAP.get(mod.lower(), mod))
    user_names = out.pop("user_names", None) or out.pop("user_name", None)
    if user_names and not out.get("user_id"):
        ids: list[int] = []
        for part in str(user_names).replace("，", ",").split(","):
            name = part.strip()
            if name:
                ids.append(int(api_client.resolve_user_id(name)))
        out["user_id"] = ids
    elif out.get("user_id") and not isinstance(out.get("user_id"), list):
        out["user_id"] = api_client._parse_int_list(out["user_id"])
    if out.get("project_id") not in (None, ""):
        out["project_id"] = int(out["project_id"])
    return out


def _resolve_add_project_task_estimate(params: dict[str, Any]) -> dict[str, Any]:
    import api_client

    out = api_client._apply_field_aliases(
        params,
        {
            "date": ("work_date", "start_date"),
            "consumed": ("hours", "work_hours"),
            "remark": ("note", "description"),
            "task_id": ("id",),
        },
    )
    if not out.get("date"):
        out["date"] = date.today().isoformat()
    if out.get("consumed") not in (None, ""):
        out["consumed"] = float(out["consumed"])
    user_name = out.pop("user_name", None)
    if user_name and not out.get("user_id"):
        out["user_id"] = int(api_client.resolve_user_id(str(user_name)))
    if out.get("task_id") in (None, "") and out.get("id") not in (None, ""):
        out["task_id"] = int(out.pop("id"))
    elif out.get("task_id") not in (None, ""):
        out["task_id"] = int(out["task_id"])
        out.pop("id", None)
    if out.get("user_id") not in (None, ""):
        out["user_id"] = int(out["user_id"])
    return out


def _preview_confirm_work_hours(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "estimate_id": body.get("id"),
        "confirm_type": body.get("confirm_type"),
        "confirm_type_label": _CONFIRM_LABEL.get(str(body.get("confirm_type")), ""),
    }


def _warnings_add_moment(body: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    module = body.get("module")
    if module in ("risk", "problem") and not body.get("risk_level"):
        warnings.append("风险/问题类动态建议填写 risk_level（风险等级/影响程度）")
    if not body.get("user_id"):
        warnings.append("未指定 user_id/user_name，提交可能失败")
    if not body.get("type"):
        warnings.append("未指定 type（子类型），提交可能失败")
    return warnings


def _preview_add_moment(body: dict[str, Any]) -> dict[str, Any]:
    module = body.get("module", "")
    return {
        "project_id": body.get("project_id"),
        "module": module,
        "module_label": _MODULE_LABEL.get(str(module), module),
        "type": body.get("type"),
        "content": body.get("content"),
        "remark": body.get("remark"),
        "risk_level": body.get("risk_level"),
        "user_id": body.get("user_id"),
    }


def _preview_add_project_estimate(body: dict[str, Any]) -> dict[str, Any]:
    preview = _preview_add_estimate(body)
    preview["work_hour_kind"] = "项目"
    preview["work_hour_kind_note"] = (
        "本操作为项目任务工时。若用户说的是非项目任务，请改用 add_not_project_estimate"
    )
    return preview


def _preview_add_not_project_estimate(body: dict[str, Any]) -> dict[str, Any]:
    preview = _preview_add_estimate(body)
    preview["work_hour_kind"] = "非项目"
    preview["work_hour_kind_note"] = (
        "本操作为非项目任务工时。若用户说的是项目任务，请改用 add_project_task_estimate"
    )
    return preview


def _warnings_add_project_estimate(body: dict[str, Any]) -> list[str]:
    return [
        "请确认是【项目任务】工时；非项目任务必须改用 add_not_project_estimate，禁止写入本接口"
    ]


def _warnings_add_not_project_estimate(body: dict[str, Any]) -> list[str]:
    return [
        "请确认是【非项目任务】工时；项目任务必须改用 add_project_task_estimate，禁止写入本接口"
    ]


def _preview_add_estimate(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": body.get("task_id"),
        "date": body.get("date"),
        "consumed": body.get("consumed"),
        "remark": body.get("remark"),
        "user_id": body.get("user_id"),
    }


_WRITE_CONTROL_PARAMS = [
    "dry_run",
    "confirm",
    "confirm_token",
    "force",
    "skip_confirm",
]

WRITE_OPERATIONS: dict[str, dict[str, Any]] = {
    "confirm_my_work_hours": {
        "description": "【写】确认工时花费（项目/非项目）",
        "method": "POST",
        "path": "/manage_api/main_panel/confirm_anything",
        "write": True,
        "group": "写操作",
        "params": [
            "id",
            "ids",
            "estimate_id",
            "work_hour_id",
            "confirm_type",
            "dry_run",
            "confirm",
            "confirm_token",
            "force",
        ],
        "required_one_of": ["id", "ids", "estimate_id", "work_hour_id"],
        "required": ["confirm_type"],
        "write_resolve_mode": "confirm_work_hours",
        "body_params": ["id", "confirm_type"],
        "body_required": ["id", "confirm_type"],
        "preview_summary": _preview_confirm_work_hours,
    },
    "add_project_moment": {
        "description": "【写】新增项目动态（会议/风险/问题）",
        "method": "POST",
        "path": "/manage_api/project_moment/add",
        "write": True,
        "group": "写操作",
        "params": [
            "project_id",
            "project_name",
            "name",
            "sj_num",
            "opportunity_no",
            "business_no",
            "module",
            "meeting",
            "risk",
            "problem",
            "type",
            "content",
            "remark",
            "risk_level",
            "status",
            "done_time",
            "user_id",
            "user_name",
            "user_names",
            "dry_run",
            "confirm",
            "confirm_token",
            "force",
        ],
        "required_any_project": True,
        "required": ["module", "content"],
        "write_resolve_mode": "add_project_moment",
        "body_params": [
            "project_id",
            "module",
            "type",
            "content",
            "remark",
            "risk_level",
            "status",
            "done_time",
            "user_id",
        ],
        "body_required": ["project_id", "module", "type", "content", "user_id"],
        "body_required_preview": ["project_id", "module", "content"],
        "preview_summary": _preview_add_moment,
        "preview_warnings": _warnings_add_moment,
    },
    "add_project_task_estimate": {
        "description": "【写】登记项目任务工时",
        "method": "POST",
        "path": "/manage_api/project_task_estimate/add",
        "write": True,
        "group": "写操作",
        "params": [
            "task_id",
            "id",
            "date",
            "work_date",
            "consumed",
            "hours",
            "work_hours",
            "remark",
            "note",
            "description",
            "user_id",
            "user_name",
            "risk_desc",
            "dry_run",
            "confirm",
            "confirm_token",
            "force",
        ],
        "required_one_of": ["task_id", "id"],
        "required": ["consumed", "remark"],
        "write_resolve_mode": "add_project_task_estimate",
        "body_params": [
            "task_id",
            "date",
            "consumed",
            "remark",
            "user_id",
            "risk_desc",
        ],
        "body_required": ["task_id", "date", "consumed", "remark"],
        "preview_summary": _preview_add_project_estimate,
        "preview_warnings": _warnings_add_project_estimate,
    },
    "confirm_user_work_hours": {
        "description": "【写】代确认用户某日工时",
        "method": "POST",
        "path": "/manage_api/data_export/estimate_hour_confirm_by_others",
        "write": True,
        "group": "写操作",
        "params": ["date", "user_id", "user_name", "remark", "dry_run", "confirm", "confirm_token", "force"],
        "required": ["remark"],
        "required_one_of": ["user_id", "user_name"],
        "write_resolve_mode": "confirm_user_work_hours",
        "body_params": ["date", "user_id", "remark"],
        "body_required": ["date", "user_id", "remark"],
        "preview_summary": lambda b: {"date": b.get("date"), "user_id": b.get("user_id"), "remark": b.get("remark")},
    },
    "approve_work_hour_batch": {
        "description": "【写】批量审核工时花费",
        "method": "POST",
        "path": "/manage_api/data_export/process_check_by_ids",
        "write": True,
        "group": "写操作",
        "params": [
            "module_name",
            "module_sort",
            "user_id",
            "user_name",
            "project_ids",
            "not_project_ids",
            "id_arr_one",
            "id_arr_two",
            "dry_run",
            "confirm",
            "confirm_token",
            "force",
        ],
        "required": ["module_name", "module_sort"],
        "required_one_of": ["user_id", "user_name"],
        "write_resolve_mode": "approve_work_hour_batch",
        "body_params": ["module_name", "module_sort", "user_id", "id_arr_one", "id_arr_two"],
        "body_required": ["module_name", "module_sort", "user_id"],
        "preview_summary": lambda b: {
            "module_name": b.get("module_name"),
            "module_sort": b.get("module_sort"),
            "user_id": b.get("user_id"),
            "project_count": len(b.get("id_arr_one") or []),
            "not_project_count": len(b.get("id_arr_two") or []),
        },
        "preview_warnings": lambda b: (
            ["project_ids 与 not_project_ids 至少填一组"]
            if not (b.get("id_arr_one") or b.get("id_arr_two"))
            else []
        ),
    },
    "add_not_project_estimate": {
        "description": "【写】登记非项目任务工时",
        "method": "POST",
        "path": "/manage_api/project_not_task_estimate/add",
        "write": True,
        "group": "写操作",
        "params": [
            "task_id",
            "id",
            "date",
            "work_date",
            "consumed",
            "hours",
            "remark",
            "user_id",
            "user_name",
            "dry_run",
            "confirm",
            "confirm_token",
            "force",
        ],
        "required_one_of": ["task_id", "id"],
        "required": ["consumed", "remark"],
        "write_resolve_mode": "add_not_project_estimate",
        "body_params": ["task_id", "date", "consumed", "remark", "user_id"],
        "body_required": ["task_id", "date", "consumed", "remark"],
        "preview_summary": _preview_add_not_project_estimate,
        "preview_warnings": _warnings_add_not_project_estimate,
    },
    "update_project_task_estimate": {
        "description": "【写】更新项目任务工时",
        "method": "PUT",
        "path": "/manage_api/project_task_estimate/update",
        "write": True,
        "group": "写操作",
        "params": [
            "id",
            "estimate_id",
            "work_hour_id",
            "date",
            "consumed",
            "remark",
            "risk_desc",
            "dry_run",
            "confirm",
            "confirm_token",
            "force",
        ],
        "required_one_of": ["id", "estimate_id", "work_hour_id"],
        "required": ["consumed", "remark"],
        "write_resolve_mode": "update_project_task_estimate",
        "body_params": ["id", "date", "consumed", "remark", "risk_desc"],
        "body_required": ["id", "consumed", "remark"],
        "preview_summary": lambda b: {
            "estimate_id": b.get("id"),
            "date": b.get("date"),
            "consumed": b.get("consumed"),
            "remark": b.get("remark"),
        },
    },
    "update_project_moment": {
        "description": "【写】更新项目动态",
        "method": "PUT",
        "path": "/manage_api/project_moment/update",
        "write": True,
        "group": "写操作",
        "params": [
            "id",
            "moment_id",
            "type",
            "content",
            "remark",
            "risk_level",
            "status",
            "done_time",
            "user_id",
            "user_name",
            "user_names",
            "dry_run",
            "confirm",
            "confirm_token",
            "force",
        ],
        "required_one_of": ["id", "moment_id"],
        "required": ["content", "type"],
        "write_resolve_mode": "update_project_moment",
        "body_params": ["id", "type", "content", "remark", "risk_level", "status", "done_time", "user_id"],
        "body_required": ["id", "type", "content", "user_id"],
        "body_required_preview": ["id", "content"],
        "preview_summary": lambda b: {
            "moment_id": b.get("id"),
            "type": b.get("type"),
            "content": b.get("content"),
            "user_id": b.get("user_id"),
        },
        "preview_warnings": _warnings_add_moment,
    },
    "add_bug": {
        "description": "【写】登记 BUG",
        "method": "POST",
        "path": "/manage_api/bug/add",
        "write": True,
        "group": "写操作",
        "params": [
            "project_id",
            "project_name",
            "sj_num",
            "task_id",
            "submit_time",
            "bug_type",
            "bug_status",
            "bug_level",
            "priority",
            "tester",
            "tester_name",
            "assigned_to",
            "assigned_to_name",
            "assignee_name",
            "content",
            "remark",
            "dry_run",
            "confirm",
            "confirm_token",
            "force",
        ],
        "required_any_project": True,
        "required": ["bug_type", "bug_status", "bug_level", "priority", "content"],
        "write_resolve_mode": "add_bug",
        "body_params": [
            "project_id",
            "task_id",
            "submit_time",
            "bug_type",
            "bug_status",
            "bug_level",
            "priority",
            "tester",
            "assigned_to",
            "content",
            "remark",
        ],
        "body_required": [
            "project_id",
            "submit_time",
            "bug_type",
            "bug_status",
            "bug_level",
            "priority",
            "tester",
            "assigned_to",
            "content",
        ],
        "body_required_preview": ["project_id", "content", "bug_type"],
        "preview_summary": lambda b: {
            "project_id": b.get("project_id"),
            "content": b.get("content"),
            "bug_type": b.get("bug_type"),
            "assigned_to": b.get("assigned_to"),
        },
        "preview_warnings": lambda b: [
            w
            for w, missing in (
                ("未指定 tester/tester_name", not b.get("tester")),
                ("未指定 assigned_to/assigned_to_name", not b.get("assigned_to")),
            )
            if missing
        ],
    },
    "apply_publish": {
        "description": "【写】申请项目递交",
        "method": "POST",
        "path": "/manage_api/produce_demand/apply_publish",
        "write": True,
        "group": "写操作",
        "params": [
            "project_id",
            "project_name",
            "sj_num",
            "apply_publish_content",
            "apply_publish_time",
            "demand_pool_id",
            "demand_pool_ids",
            "publish_dijiao_version",
            "dry_run",
            "confirm",
            "confirm_token",
            "force",
        ],
        "required_any_project": True,
        "required": ["apply_publish_content", "apply_publish_time"],
        "write_resolve_mode": "apply_publish",
        "body_params": [
            "sj_num",
            "project_name",
            "project_id",
            "apply_publish_content",
            "apply_publish_time",
            "demand_pool_id",
            "publish_dijiao_version",
        ],
        "body_required": [
            "sj_num",
            "project_name",
            "project_id",
            "apply_publish_content",
            "apply_publish_time",
        ],
        "preview_summary": lambda b: {
            "sj_num": b.get("sj_num"),
            "project_name": b.get("project_name"),
            "apply_publish_time": b.get("apply_publish_time"),
            "content": b.get("apply_publish_content"),
        },
    },
    "reject_publish_apply": {
        "description": "【写】驳回递交申请",
        "method": "POST",
        "path": "/manage_api/produce_demand/reject_publish",
        "write": True,
        "group": "写操作",
        "params": ["id", "publish_id", "reject_reason", "dry_run", "confirm", "confirm_token", "force"],
        "required_one_of": ["id", "publish_id"],
        "required": ["reject_reason"],
        "write_resolve_mode": "reject_publish",
        "body_params": ["id", "reject_reason"],
        "body_required": ["id", "reject_reason"],
        "preview_summary": lambda b: {"apply_id": b.get("id"), "reject_reason": b.get("reject_reason")},
    },
    "start_project_task": {
        "description": "【写】开始项目任务",
        "method": "POST",
        "path": "/manage_api/project_task/start",
        "write": True,
        "group": "写操作",
        "params": ["id", "task_id", "remark", "assigned_to", "assigned_to_name", "dry_run", "confirm", "confirm_token", "force"],
        "required_one_of": ["id", "task_id"],
        "required": ["remark"],
        "write_resolve_mode": "task_action",
        "body_params": ["id", "remark", "assigned_to"],
        "body_required": ["id", "remark"],
        "preview_summary": lambda b: {"task_id": b.get("id"), "remark": b.get("remark")},
    },
    "finish_project_task": {
        "description": "【写】完成项目任务",
        "method": "POST",
        "path": "/manage_api/project_task/finish",
        "write": True,
        "group": "写操作",
        "params": ["id", "task_id", "remark", "dry_run", "confirm", "confirm_token", "force"],
        "required_one_of": ["id", "task_id"],
        "required": ["remark"],
        "write_resolve_mode": "task_action",
        "body_params": ["id", "remark"],
        "body_required": ["id", "remark"],
        "preview_summary": lambda b: {"task_id": b.get("id"), "remark": b.get("remark")},
    },
    "save_project_overview_value": {
        "description": "【写】保存项目价值（概览）",
        "method": "POST",
        "path": "/manage_api/project_overview/save_value",
        "write": True,
        "group": "写操作",
        "params": [
            "project_id",
            "project_name",
            "sj_num",
            "rows",
            "dry_run",
            "confirm",
            "confirm_token",
            "force",
        ],
        "required_any_project": True,
        "required": ["rows"],
        "write_resolve_mode": "save_project_overview_value",
        "body_params": ["project_id", "rows"],
        "body_required": ["project_id", "rows"],
        "preview_summary": lambda b: {
            "project_id": b.get("project_id"),
            "row_count": len(b.get("rows") or []) if isinstance(b.get("rows"), list) else 0,
        },
        "preview_warnings": lambda b: (
            ["rows 需为 JSON 数组；可先 get_project_overview_value 查看现有内容"]
            if not isinstance(b.get("rows"), list)
            else []
        ),
    },
    "add_not_project_demand": {
        "description": "【写】新增非项目需求",
        "method": "POST",
        "path": "/manage_api/project_not_task/add",
        "write": True,
        "group": "写操作",
        "params": [
            "project_id",
            "not_project_id",
            "not_project_name",
            "name",
            "protype",
            "status",
            "plan_hour",
            "assigned_to",
            "assigned_to_names",
            "dry_run",
            "confirm",
            "confirm_token",
            "force",
        ],
        "required": ["name"],
        "required_one_of": ["project_id", "not_project_id", "not_project_name", "name"],
        "write_resolve_mode": "add_not_project_demand",
        "body_params": ["project_id", "name", "desc", "status", "plan_hour", "assigned_to", "protype", "one_type", "pid"],
        "body_required": ["project_id", "name"],
        "body_required_preview": ["project_id", "name"],
        "preview_summary": lambda b: {
            "not_project_id": b.get("project_id"),
            "name": b.get("name"),
            "assigned_to": b.get("assigned_to"),
        },
    },
    "add_not_project_task": {
        "description": "【写】新增非项目任务",
        "method": "POST",
        "path": "/manage_api/project_not_task/add_task",
        "write": True,
        "group": "写操作",
        "params": [
            "project_id",
            "not_project_id",
            "not_project_name",
            "pid",
            "demand_id",
            "name",
            "start_date",
            "end_date",
            "plan_hour",
            "assigned_to",
            "assignee_name",
            "dry_run",
            "confirm",
            "confirm_token",
            "force",
        ],
        "required": ["name", "start_date", "end_date", "plan_hour"],
        "required_one_of": ["project_id", "not_project_id", "not_project_name"],
        "write_resolve_mode": "add_not_project_task",
        "body_params": [
            "project_id",
            "pid",
            "name",
            "desc",
            "status",
            "assigned_to",
            "start_date",
            "end_date",
            "plan_hour",
            "one_type",
            "estimate_type",
            "option_ids",
        ],
        "body_required": ["project_id", "pid", "name", "start_date", "end_date", "plan_hour"],
        "preview_summary": lambda b: {
            "not_project_id": b.get("project_id"),
            "demand_id": b.get("pid"),
            "name": b.get("name"),
            "plan_hour": b.get("plan_hour"),
        },
    },
    "finish_not_project_task": {
        "description": "【写】完成非项目任务",
        "method": "POST",
        "path": "/manage_api/project_not_task/finish_task",
        "write": True,
        "group": "写操作",
        "params": ["id", "task_id", "dry_run", "confirm", "confirm_token", "force"],
        "required_one_of": ["id", "task_id"],
        "write_resolve_mode": "finish_not_project_task",
        "body_params": ["id"],
        "body_required": ["id"],
        "preview_summary": lambda b: {"task_id": b.get("id")},
    },
    "update_not_project_estimate": {
        "description": "【写】更新非项目任务工时",
        "method": "PUT",
        "path": "/manage_api/project_not_task_estimate/update",
        "write": True,
        "group": "写操作",
        "params": [
            "id",
            "estimate_id",
            "date",
            "consumed",
            "remark",
            "dry_run",
            "confirm",
            "confirm_token",
            "force",
        ],
        "required_one_of": ["id", "estimate_id"],
        "required": ["consumed", "remark"],
        "write_resolve_mode": "update_not_project_estimate",
        "body_params": ["id", "date", "consumed", "remark"],
        "body_required": ["id", "consumed", "remark"],
        "preview_summary": lambda b: {
            "estimate_id": b.get("id"),
            "consumed": b.get("consumed"),
            "remark": b.get("remark"),
        },
    },
    "add_apply_demand": {
        "description": "【写】新增申请制作需求",
        "method": "POST",
        "path": "/manage_api/produce_demand/add_apply_demand",
        "write": True,
        "group": "写操作",
        "params": [
            "project_id",
            "project_name",
            "sj_num",
            "apply_demand_module",
            "apply_demand_modules",
            "apply_demand_desc",
            "apply_material_address",
            "dry_run",
            "confirm",
            "confirm_token",
            "force",
        ],
        "required_any_project": True,
        "required": ["apply_demand_module", "apply_demand_desc"],
        "write_resolve_mode": "add_apply_demand",
        "body_params": [
            "sj_num",
            "project_name",
            "project_id",
            "apply_demand_module",
            "apply_demand_desc",
            "apply_material_address",
            "demand_url",
        ],
        "body_required": ["sj_num", "project_name", "project_id", "apply_demand_module", "apply_demand_desc"],
        "preview_summary": lambda b: {
            "sj_num": b.get("sj_num"),
            "project_name": b.get("project_name"),
            "modules": b.get("apply_demand_module"),
            "desc": b.get("apply_demand_desc"),
        },
        "preview_warnings": lambda b: (
            ["可先调用 get_apply_demand_consts 查看模块/类型字典"] if not b.get("apply_demand_module") else []
        ),
    },
    "add_demand_pool": {
        "description": "【写】拆解新增制作需求池",
        "method": "POST",
        "path": "/manage_api/produce_demand/add_demand_pool",
        "write": True,
        "group": "写操作",
        "params": [
            "a_id",
            "apply_demand_id",
            "params",
            "dry_run",
            "confirm",
            "confirm_token",
            "force",
        ],
        "required_one_of": ["a_id", "apply_demand_id"],
        "required": ["params"],
        "write_resolve_mode": "add_demand_pool",
        "body_params": ["a_id", "params"],
        "body_required": ["a_id", "params"],
        "preview_summary": lambda b: {
            "apply_demand_id": b.get("a_id"),
            "item_count": len(b.get("params") or []),
        },
        "preview_warnings": lambda b: (
            ["params 需为 JSON 数组，每项含 demand_type/demand_module/cost/executor_name 等"]
            if not isinstance(b.get("params"), list)
            else []
        ),
    },
    "add_feedback_demand_pool": {
        "description": "【写】新增反馈类制作需求池（demand_type=反馈）",
        "method": "POST",
        "path": "/manage_api/produce_demand/add_demand_pool",
        "write": True,
        "group": "写操作",
        "params": [
            "a_id",
            "apply_demand_id",
            "params",
            "dry_run",
            "confirm",
            "confirm_token",
            "force",
        ],
        "required_one_of": ["a_id", "apply_demand_id"],
        "required": ["params"],
        "write_resolve_mode": "add_feedback_demand_pool",
        "body_params": ["a_id", "params"],
        "body_required": ["a_id", "params"],
        "preview_summary": lambda b: {
            "apply_demand_id": b.get("a_id"),
            "feedback_item_count": len(b.get("params") or []),
        },
    },
    "approve_publish_apply": {
        "description": "【写】通过递交申请并排期（创建正式递交，状态→已排期）",
        "method": "POST",
        "path": "/manage_api/project_publish/add",
        "write": True,
        "group": "写操作",
        "params": [
            "apply_publish_id",
            "id",
            "publish_id",
            "sj_num",
            "project_name",
            "publish_content",
            "pm_name",
            "project_develop",
            "scene_group",
            "publish_submit_type",
            "publish_dijiao_version",
            "real_publish_people",
            "selected_demand_pool_ids",
            "demand_pool_id",
            "dry_run",
            "confirm",
            "confirm_token",
            "force",
        ],
        "required_one_of": ["apply_publish_id", "id"],
        "required": ["publish_content"],
        "write_resolve_mode": "approve_publish_apply",
        "body_params": [
            "apply_publish_id",
            "sj_num",
            "publish_content",
            "pm_name",
            "project_develop",
            "scene_group",
            "project_area",
            "project_type",
            "publish_submit_type",
            "publish_dijiao_version",
            "real_publish_people",
            "contain_logo",
            "basic_version",
            "wdp_api_version",
            "industry_plugins",
            "engine_version",
            "linshi_status",
            "linshi_duty",
            "linshi_reason",
            "regional_organization",
            "publish_url",
            "selected_demand_pool_ids",
        ],
        "body_required": ["apply_publish_id", "sj_num", "publish_content"],
        "body_required_preview": ["apply_publish_id", "publish_content"],
        "preview_summary": lambda b: {
            "apply_publish_id": b.get("apply_publish_id"),
            "sj_num": b.get("sj_num"),
            "publish_content": b.get("publish_content"),
        },
        "preview_warnings": lambda b: [
            w
            for w, missing in (
                ("未指定 sj_num/project_name，确认前需补全", not b.get("sj_num")),
                ("可先 get_publish_normal_const 查递交版本/交付形式字典", not b.get("publish_dijiao_version")),
            )
            if missing
        ],
    },
}

WRITE_RESOLVE_MODES = frozenset(
    {
        "confirm_work_hours",
        "add_project_moment",
        "add_project_task_estimate",
        "confirm_user_work_hours",
        "approve_work_hour_batch",
        "add_not_project_estimate",
        "update_project_task_estimate",
        "update_project_moment",
        "add_bug",
        "apply_publish",
        "reject_publish",
        "task_action",
        "save_project_overview_value",
        "add_not_project_demand",
        "add_not_project_task",
        "finish_not_project_task",
        "update_not_project_estimate",
        "add_apply_demand",
        "add_demand_pool",
        "add_feedback_demand_pool",
        "approve_publish_apply",
    }
)
