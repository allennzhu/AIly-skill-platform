"""Resolve「我们组 / 我团队 / 组员」→ dept_id（子部门由 51PM GetAllDeptIds 展开）."""

from __future__ import annotations

from typing import Any, Callable

_MY_TEAM_FLAGS = frozenset({"1", "true", "yes", "my_team", "team"})

_SCOPE_PARAM_KEYS = (
    "dept_id",
    "dept_name",
    "user_name",
    "user_id",
    "user_ids",
    "assignee_name",
    "assigned_to",
    "assigned_to_me",
)


def truthy_team_scope(value: Any) -> bool:
    if value in (None, ""):
        return False
    return str(value).strip().lower() in _MY_TEAM_FLAGS


def flatten_department_tree(
    nodes: list[Any], out: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    out = out or []
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        info = {
            "id": node.get("id"),
            "pid": node.get("pid"),
            "leader_id": node.get("leader_id"),
            "title": node.get("title"),
            "status": node.get("status"),
        }
        if info["id"] not in (None, ""):
            out.append(info)
        children = node.get("children") or []
        if children:
            flatten_department_tree(children, out)
    return out


def _dept_by_id(departments: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    by_id: dict[int, dict[str, Any]] = {}
    for item in departments:
        dept_id = item.get("id")
        if dept_id in (None, ""):
            continue
        by_id[int(dept_id)] = item
    return by_id


def _is_dept_ancestor(
    ancestor_id: int, node_id: int, by_id: dict[int, dict[str, Any]]
) -> bool:
    cur = node_id
    seen: set[int] = set()
    while cur and cur not in seen:
        if cur == ancestor_id:
            return True
        seen.add(cur)
        parent = by_id.get(cur, {}).get("pid")
        if parent in (None, "", 0):
            break
        cur = int(parent)
    return False


def _dept_depth(dept_id: int, by_id: dict[int, dict[str, Any]]) -> int:
    depth = 0
    cur = dept_id
    seen: set[int] = set()
    while cur and cur not in seen:
        depth += 1
        seen.add(cur)
        parent = by_id.get(cur, {}).get("pid")
        if parent in (None, "", 0):
            break
        cur = int(parent)
    return depth


def pick_led_dept_id(
    user_id: int,
    departments: list[dict[str, Any]],
    *,
    fallback_dept_id: int | None = None,
) -> int:
    """Pick scope root: led parent dept (includes sub-depts on server) or own dept."""
    led = [
        item
        for item in departments
        if int(item.get("leader_id") or 0) == int(user_id)
    ]
    if not led:
        if fallback_dept_id not in (None, ""):
            return int(fallback_dept_id)
        raise ValueError("no department scope for user")

    if len(led) == 1:
        return int(led[0]["id"])

    by_id = _dept_by_id(departments)
    if fallback_dept_id not in (None, ""):
        fallback = int(fallback_dept_id)
        matches = [
            int(item["id"])
            for item in led
            if _is_dept_ancestor(int(item["id"]), fallback, by_id)
        ]
        if matches:
            return max(matches, key=lambda dept_id: _dept_depth(dept_id, by_id))

    return int(sorted(int(item["id"]) for item in led)[0])


def apply_my_team_scope(
    params: dict[str, Any],
    *,
    user_id: int | None,
    fallback_dept_id: int | None,
    fetch_departments: Callable[[], list[dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Apply my_team_scope / team_scope; return (params, scope_meta)."""
    out = dict(params)
    flag = out.pop("my_team_scope", None)
    if flag is None:
        flag = out.pop("team_scope", None)
    if not truthy_team_scope(flag):
        return out, None

    if user_id is None:
        from api_client import ClientError

        raise ClientError("auth_required", "解析「我们组」范围需要登录会话")

    if any(out.get(key) not in (None, "", [], 0) for key in _SCOPE_PARAM_KEYS):
        return out, None

    departments = fetch_departments()
    dept_id = pick_led_dept_id(
        int(user_id),
        departments,
        fallback_dept_id=fallback_dept_id,
    )
    by_id = _dept_by_id(departments)
    title = str((by_id.get(dept_id) or {}).get("title") or "")
    out["dept_id"] = dept_id
    if title:
        out["dept_name"] = title
    meta: dict[str, Any] = {
        "scope": "my_team",
        "dept_id": dept_id,
        "dept_title": title,
        "includes_sub_departments": True,
    }
    led_titles = [
        str(item.get("title") or item.get("id"))
        for item in departments
        if int(item.get("leader_id") or 0) == int(user_id)
    ]
    if led_titles:
        meta["led_departments"] = led_titles
    return out, meta
