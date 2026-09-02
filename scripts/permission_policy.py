"""Role-based permission policy for pm-platform-api Skill.

Skill enforces business rules locally before calling manage_api (backend does not).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


def permission_denied_payload(
    detail: str,
    *,
    operation: str = "",
    role: str = "",
    ctx: "PermissionContext | None" = None,
) -> dict[str, Any]:
    """Structured terminal error — agent must stop immediately."""
    payload: dict[str, Any] = {
        "error": "permission_denied",
        "detail": detail,
        "terminal": True,
        "stop": True,
        "message": "权限不足：请立即停止当前任务，向用户说明原因。",
        "agent_instruction": (
            "禁止继续思考、换参数重试、换接口绕路、search_user/get_department_list 探测、"
            "本地筛选或 skip_permission。直接结束并告知用户无权访问。"
        ),
    }
    if operation:
        payload["operation"] = operation
    if role:
        payload["role"] = role
    if ctx is not None:
        payload["actor"] = actor_payload(ctx)
        title = ctx.role_title or _role_title(ctx.role)
        if ctx.role == "GL":
            payload["agent_instruction"] = (
                f"当前用户是 {title}（GL，四级负责人），不是普通组员或项目技术组员。"
                "向用户说明：本次因目标部门/人员不在其负责或所在部门范围内而拒绝；"
                "禁止把 GL 称为「组员」，禁止换参绕路。"
            )
        elif ctx.is_dept_leader:
            payload["agent_instruction"] = (
                f"当前用户是部门负责人（{title}），不是普通组员。"
                "向用户说明：本次因目标不在其负责部门及子部门范围内而拒绝；禁止换参绕路。"
            )
    return payload


def raise_permission_denied(
    detail: str,
    *,
    operation: str = "",
    role: str = "",
    ctx: "PermissionContext | None" = None,
) -> None:
    import api_client

    raise api_client.ClientError(
        "permission_denied",
        json.dumps(
            permission_denied_payload(
                detail,
                operation=operation,
                role=role,
                ctx=ctx,
            ),
            ensure_ascii=False,
        ),
    )


@dataclass(frozen=True)
class RoleMeta:
    """51PM dev_menu_root（status=1）角色定义。"""

    role_id: int
    code: str
    title: str
    project_root: int
    description: str


# 来源：51PM `dev_menu_root`（root_id = user_info.root_id）
ROLE_CATALOG: dict[int, RoleMeta] = {
    1: RoleMeta(
        1,
        "GHOST",
        "超级员工权限",
        2,
        "系统最高权限，不可修改",
    ),
    2: RoleMeta(
        2,
        "ADMIN",
        "管理员",
        2,
        "全局系统管理（所有的创建的项目加入到项目白名单中）",
    ),
    3: RoleMeta(
        3,
        "PM",
        "项目经理",
        2,
        "审核创建项目、需求、任务等（所有的创建的项目加入到项目白名单中）",
    ),
    4: RoleMeta(
        4,
        "TB",
        "BD/TB",
        1,
        "只能看项目概况和动态",
    ),
    6: RoleMeta(
        6,
        "GL",
        "四级负责人",
        2,
        "可以创建任务，不能创建需求（只有属于他们的项目才添加到 projects）；平台 dev_menu_root 显示名：Builder负责人",
    ),
    7: RoleMeta(
        7,
        "BG",
        "行业运营",
        2,
        "只能看项目概况和动态，无创建项目/需求/任务权限，可以浏览属于他们的 BG 的项目状态和数据",
    ),
    8: RoleMeta(
        8,
        "FA",
        "区域组织中台/财务/采购",
        1,
        "只能看项目概况和动态，无创建项目/需求/任务权限，中台可以看所有项目数据",
    ),
    9: RoleMeta(
        9,
        "Nor",
        "普通成员",
        1,
        "只能看项目概况和动态，项目制作人员（只有属于他们的项目才添加进来）",
    ),
    10: RoleMeta(
        10,
        "RST",
        "受限用户",
        1,
        "受限用户组（只可以编辑跟自己相关的内容）",
    ),
    11: RoleMeta(
        11,
        "HR",
        "人力行政",
        2,
        "导出工时",
    ),
    22: RoleMeta(
        22,
        "TA",
        "项目技术组员（含设计组员）",
        1,
        "自己确认任务开始、完成、进度",
    ),
    23: RoleMeta(
        23,
        "DEV",
        "项目开发组员",
        2,
        "需要：任务开始、编辑、进度更新；不需要：需求编辑权限",
    ),
    24: RoleMeta(
        24,
        "RO",
        "全量只读",
        2,
        "什么都能看到，什么操作都不能做",
    ),
    25: RoleMeta(
        25,
        "SP",
        "工程场景",
        1,
        "自己不能创建任务、开始任务、修改任务状态",
    ),
    26: RoleMeta(
        26,
        "QA",
        "项目测试",
        2,
        "工程测试特殊权限",
    ),
}

ROLE_MAP: dict[int, str] = {rid: meta.code for rid, meta in ROLE_CATALOG.items()}

PRIVILEGED_READ_ROLES = frozenset({"GHOST", "ADMIN", "PM", "RO"})
READONLY_ROLES = frozenset({"RO"})
NO_WRITE_ROLES = frozenset({"BG", "HR", "Nor", "FA", "RST", "Other"})
ENGINEERING_ROLES = frozenset({"GHOST", "ADMIN", "PM", "GL", "TA", "DEV", "SP", "QA"})
PROJECT_OWNER_READ_ROLES = frozenset({"TB", "BG"})

TB_WRITE_OPS = frozenset(
    {"apply_publish", "add_apply_demand", "add_feedback_demand_pool"}
)

HR_READ_OPS = frozenset(
    {
        "get_work_hours",
        "get_work_hour_statistics",
        "get_work_hour_detail_list",
        "search_user",
        "get_department_list",
        "get_dept_members",
    }
)

UTILITY_READ_OPS = frozenset(
    {
        "search_user",
        "get_department_list",
        "get_dept_members",
        "get_bug_const",
        "get_publish_normal_const",
        "get_project_moment_config_list",
        "get_apply_demand_consts",
        "get_ecp_baojia_const",
    }
)

# 不做本地人/部门/项目范围校验，也不裁剪响应（登录即可查任意部门成员）
UNSCOPED_READ_OPS = frozenset({"get_dept_members"})

PRIVILEGED_ONLY_READ_PREFIXES = (
    "get_supplier_",
    "get_outsource_",
    "get_dept_capacity_",
    "get_dept_left_hour_",
    "get_qa_stat_",
    "get_performance_",
    "get_all_times_list",
    "get_employee_estimate_list",
    "get_total_schedule_list",
    "get_employee_project_",
    "get_user_project",
    "get_user_project_panel",
    "get_scene_group_project",
    "get_project_delivery_type_panel",
    "get_ecp_baojia_list",
    "get_project_cost_list",
)

PRIVILEGED_ONLY_READ_EXACT = frozenset(
    {
        "get_project_list",
        "get_project_cost_stat",
        "get_project_cost_stat_list",
        "get_project_cost_by_id",
        "get_demand_pool_list",
    }
)

TB_MASK_FIELD_NAMES = frozenset(
    {
        "consumed",
        "estimate_hour",
        "left_hour",
        "spent_hour",
        "spent_hours",
        "spent_ratio",
        "output_hour",
        "non_output_hour",
        "actual_cost",
        "actual_mandays",
        "actual_date",
        "actual_delivery_time",
        "cost",
        "total_cost",
        "contract_amount",
        "settlement_amount",
        "price",
        "amount",
        "budget_left",
        "ev_left",
    }
)

TB_KEEP_FIELD_HINTS = ("standard", "plan", "initial", "budget_pool", "sj_num", "name", "title", "status")


class DataScope(str, Enum):
    ALL = "all"
    SELF = "self"
    TEAM = "team"
    PARTICIPANT = "participant"
    PROJECT_OWNER = "project_owner"
    HR_WORK_SUMMARY = "hr_work_summary"


@dataclass
class PermissionContext:
    user_id: int
    nick_name: str
    role: str
    role_id: int | None = None
    role_title: str = ""
    role_description: str = ""
    dept_id: int | None = None
    team_user_ids: set[int] = field(default_factory=set)
    team_dept_ids: set[int] = field(default_factory=set)
    is_dept_leader: bool = False
    participant_project_ids: set[int] = field(default_factory=set)
    owner_project_ids: set[int] = field(default_factory=set)
    token: str = ""

    @property
    def is_privileged_read(self) -> bool:
        return self.role in PRIVILEGED_READ_ROLES

    def allowed_user_ids(self) -> set[int] | None:
        if self.is_privileged_read or self.role == "HR":
            return None
        if self.team_user_ids:
            ids = set(self.team_user_ids)
            ids.add(self.user_id)
            return ids
        return {self.user_id}

    def allowed_project_ids(self) -> set[int] | None:
        if self.is_privileged_read:
            return None
        if self.role in PROJECT_OWNER_READ_ROLES:
            # TB/BG：参与项目（main_panel）+ 自己作为 BD/TB 负责的项目
            ids = set(self.participant_project_ids)
            ids.update(self.owner_project_ids)
            return ids
        if self.role == "GL" or self.is_dept_leader:
            ids = set(self.participant_project_ids)
            ids.update(self.owner_project_ids)
            return ids
        return set(self.participant_project_ids)

    def allowed_dept_ids(self) -> set[int] | None:
        if self.is_privileged_read or self.role == "HR":
            return None
        if self.team_dept_ids:
            return set(self.team_dept_ids)
        if self.dept_id is not None:
            return {self.dept_id}
        return set()


@dataclass
class OperationAccess:
    allowed: bool
    reason: str = ""
    read_scope: DataScope | None = None
    mask_tb_fields: bool = False


def role_from_root_id(root_id: Any) -> str:
    meta = role_meta_from_root_id(root_id)
    return meta.code if meta else "Other"


def role_meta_from_root_id(root_id: Any) -> RoleMeta | None:
    try:
        return ROLE_CATALOG.get(int(root_id))
    except (TypeError, ValueError):
        return None


def actor_payload(ctx: PermissionContext) -> dict[str, Any]:
    title = ctx.role_title or _role_title(ctx.role)
    payload: dict[str, Any] = {
        "user_id": ctx.user_id,
        "nick_name": ctx.nick_name,
        "role": ctx.role,
        "role_label": f"{title}（{ctx.role}）",
    }
    if ctx.role_id is not None:
        payload["role_id"] = ctx.role_id
    if ctx.role_title:
        payload["role_title"] = ctx.role_title
    if ctx.role_description:
        payload["role_description"] = ctx.role_description
    if ctx.role == "GL":
        payload["role_note"] = "GL=四级负责人（平台亦称 Builder负责人），不是普通组员或项目技术组员（TA/DEV）"
    if ctx.is_dept_leader:
        payload["is_dept_leader"] = True
    visible = sorted(ctx.team_dept_ids) if ctx.team_dept_ids else []
    if not visible and ctx.dept_id is not None:
        visible = [ctx.dept_id]
    if visible:
        payload["visible_dept_ids"] = visible
    return payload


def classify_read_access(operation: str, role: str) -> OperationAccess:
    if operation in UTILITY_READ_OPS:
        return OperationAccess(True, read_scope=DataScope.SELF)
    if role in PRIVILEGED_READ_ROLES:
        return OperationAccess(True, read_scope=DataScope.ALL)
    if role == "HR":
        if operation in HR_READ_OPS:
            return OperationAccess(True, read_scope=DataScope.HR_WORK_SUMMARY)
        return OperationAccess(False, "人力行政仅可生成/查看全员工作总结（工时相关查询）")
    if role == "BG":
        if operation.startswith("get_") and not _is_privileged_only_read(operation):
            return OperationAccess(True, read_scope=DataScope.PROJECT_OWNER)
        return OperationAccess(False, "行业运营仅可查看与自己相关项目的数据")
    if role == "TB":
        if operation.startswith("get_") and not _is_privileged_only_read(operation):
            return OperationAccess(
                True,
                read_scope=DataScope.PROJECT_OWNER,
                mask_tb_fields=_needs_tb_field_mask(operation),
            )
        return OperationAccess(False, "TB/BD 仅可查看属于自己项目的相关数据")
    if role == "GL":
        if _is_privileged_only_read(operation):
            return OperationAccess(False, "四级负责人无权访问该组织级统计/供应商/外包模块")
        if operation.startswith("get_"):
            return OperationAccess(True, read_scope=DataScope.TEAM)
        return OperationAccess(False, "四级负责人仅可查看权限范围内的数据")
    if _is_privileged_only_read(operation):
        return OperationAccess(False, "该模块仅超管/管理员/项目经理可查询")
    if operation.startswith("get_"):
        return OperationAccess(True, read_scope=DataScope.PARTICIPANT)
    return OperationAccess(False, "无权访问该操作")


def _role_title(code: str) -> str:
    for meta in ROLE_CATALOG.values():
        if meta.code == code:
            return meta.title
    return code


def classify_write_access(operation: str, role: str) -> OperationAccess:
    if role in READONLY_ROLES:
        return OperationAccess(False, "全量只读角色不可执行任何写操作")
    if role == "BG":
        return OperationAccess(False, "行业运营不可执行任何写操作")
    if role == "HR":
        return OperationAccess(False, "人力行政不可执行写操作")
    if role == "TB":
        if operation in TB_WRITE_OPS:
            return OperationAccess(True, read_scope=DataScope.PROJECT_OWNER)
        return OperationAccess(False, "BD/TB 仅可提交自己项目下的制作需求、反馈、递交申请")
    if role in NO_WRITE_ROLES:
        return OperationAccess(False, f"{_role_title(role)}不可执行写操作")
    if role in ENGINEERING_ROLES:
        if role in PRIVILEGED_READ_ROLES:
            return OperationAccess(True, read_scope=DataScope.ALL)
        if role == "GL":
            return OperationAccess(True, read_scope=DataScope.TEAM)
        return OperationAccess(True, read_scope=DataScope.PARTICIPANT)
    return OperationAccess(False, f"角色 {role} 不可执行写操作")


def check_operation_access(
    operation: str,
    meta: dict[str, Any],
    ctx: PermissionContext,
) -> OperationAccess:
    if meta.get("write"):
        return classify_write_access(operation, ctx.role)
    return classify_read_access(operation, ctx.role)


def _is_privileged_only_read(operation: str) -> bool:
    if operation in PRIVILEGED_ONLY_READ_EXACT:
        return True
    return any(operation.startswith(p) for p in PRIVILEGED_ONLY_READ_PREFIXES)


def _needs_tb_field_mask(operation: str) -> bool:
    hints = (
        "work_hour",
        "estimate",
        "cost",
        "quotation",
        "baojia",
        "overview",
        "performance",
        "times_list",
        "project_work",
    )
    return any(h in operation for h in hints)


def _parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_target_user_id(params: dict[str, Any]) -> int | None:
    for key in ("user_id", "user_ids", "pm_user_id", "assigned_to"):
        val = params.get(key)
        if isinstance(val, list) and val:
            return _parse_int(val[0])
        if val not in (None, ""):
            return _parse_int(val)
    return None


def enforce_param_scope(
    operation: str,
    params: dict[str, Any],
    ctx: PermissionContext,
    access: OperationAccess,
) -> None:
    import api_client

    if operation in UNSCOPED_READ_OPS:
        return

    if access.read_scope == DataScope.ALL:
        return

    allowed_users = ctx.allowed_user_ids()
    if allowed_users is not None:
        target = _extract_target_user_id(params)
        for name_key in ("user_name", "assignee_name"):
            name_val = params.get(name_key)
            if name_val and not target:
                target = _parse_int(api_client.resolve_user_id(str(name_val)))
        if params.get("assigned_to_me") and not target:
            target = ctx.user_id
        if target is not None and target not in allowed_users:
            if ctx.role != "HR":
                raise_permission_denied(
                    "仅可查询本人及您负责部门/组内成员的数据，请勿查询他人信息",
                    operation=operation,
                    role=ctx.role,
                    ctx=ctx,
                )

    allowed_depts = ctx.allowed_dept_ids()
    if allowed_depts is not None:
        dept_id = _parse_int(params.get("dept_id"))
        dept_name = params.get("dept_name")
        if dept_name and dept_id is None:
            dept_id = _parse_int(api_client.resolve_dept_id(str(dept_name)))
        if dept_id is not None and dept_id not in allowed_depts:
            title = ctx.role_title or _role_title(ctx.role)
            visible = sorted(allowed_depts)
            target_label = dept_name or dept_id
            raise_permission_denied(
                f"无权查询部门「{target_label}」。当前身份：{title}（{ctx.role}），"
                f"可见部门 id：{visible}。"
                f"GL/四级负责人请查自己负责或所在部门，使用 my_team_scope 1 或正确的 dept_name。",
                operation=operation,
                role=ctx.role,
                ctx=ctx,
            )

    allowed_projects = ctx.allowed_project_ids()
    if allowed_projects is not None and access.read_scope in (
        DataScope.PARTICIPANT,
        DataScope.PROJECT_OWNER,
        DataScope.TEAM,
    ):
        project_keys = (
            "project_id",
            "id",
            "ids",
            "sj_num",
            "project_name",
            "name",
            "opportunity_no",
            "business_no",
        )
        if not any(params.get(k) not in (None, "") for k in project_keys):
            return
        try:
            pid = _parse_int(params.get("project_id"))
            if pid is None and params.get("id") and operation.startswith("get_project"):
                pid = _parse_int(params.get("id"))
            if pid is None:
                pid = _parse_int(api_client.resolve_project_id(params))
            if pid is not None and pid not in allowed_projects:
                raise_permission_denied(
                    "该项目不在您的可见范围内（仅可访问自己相关/参与的项目）",
                    operation=operation,
                    role=ctx.role,
                    ctx=ctx,
                )
        except api_client.ClientError as e:
            if e.error == "permission_denied":
                raise
            # If project cannot be resolved yet, let upstream validation handle it.


_ITEM_PROJECT_KEYS = ("project_id", "pid", "ecp_project_id")
_ITEM_USER_KEYS = (
    "user_id",
    "assigned_to",
    "assigned_user_id",
    "pm_id",
    "pm_user_id",
    "create_user_id",
    "update_user_id",
    "developer_id",
    "tester_id",
    "project_pm",
    "project_develop",
    "project_tester",
    "project_bd_tb",
)


def _extract_item_project_id(item: dict[str, Any]) -> int | None:
    for key in _ITEM_PROJECT_KEYS:
        val = item.get(key)
        if val not in (None, ""):
            pid = _parse_int(val)
            if pid is not None:
                return pid
    if item.get("sj_num") or item.get("opportunity_no"):
        return None
    pid = _parse_int(item.get("id"))
    if pid is not None and any(
        hint in item
        for hint in ("project_name", "sj_num", "opportunity_no", "ecp_kaigong_zhuangtai")
    ):
        return pid
    return None


def _extract_item_user_id(item: dict[str, Any]) -> int | None:
    for key in _ITEM_USER_KEYS:
        val = item.get(key)
        if isinstance(val, list) and val:
            uid = _parse_int(val[0])
            if uid is not None:
                return uid
        if val not in (None, ""):
            uid = _parse_int(val)
            if uid is not None:
                return uid
    return None


def _item_in_read_scope(
    item: dict[str, Any],
    *,
    allowed_projects: set[int] | None,
    allowed_users: set[int] | None,
) -> bool:
    """True when the row/object is visible for the current role scope."""
    pid = _extract_item_project_id(item)
    uid = _extract_item_user_id(item)
    if allowed_projects is not None and pid is not None and pid not in allowed_projects:
        return False
    if allowed_users is not None and uid is not None and uid not in allowed_users:
        return False
    return True


def _locate_response_item_list(payload: dict[str, Any]) -> tuple[list[Any] | None, Any, str | None]:
    data = payload.get("data")
    if isinstance(data, list):
        return data, payload, "data"
    if isinstance(data, dict):
        for key in ("data", "list", "rows"):
            items = data.get(key)
            if isinstance(items, list):
                return items, data, key
    return None, None, None


def _write_response_item_list(
    payload: dict[str, Any],
    holder: Any,
    key: str | None,
    items: list[Any],
) -> None:
    if holder is payload:
        payload["data"] = items
        return
    if isinstance(holder, dict) and key:
        holder[key] = items
        if "total" in holder:
            try:
                holder["total"] = len(items)
            except (TypeError, ValueError):
                pass


def filter_read_response_scope(
    payload: Any,
    ctx: PermissionContext,
    access: OperationAccess,
    *,
    operation: str = "",
) -> Any:
    """Drop rows/objects outside the caller's visible user/project scope.

    Many read APIs are callable for scoped roles (e.g. TB/工程成员); only the
    response is trimmed. Hard ``permission_denied`` is reserved for explicit
    out-of-scope *request parameters* or operations the role may not invoke.
    """
    if operation in UNSCOPED_READ_OPS:
        return payload
    if access.read_scope in (DataScope.ALL, DataScope.HR_WORK_SUMMARY):
        return payload
    if not isinstance(payload, dict):
        return payload

    allowed_projects = ctx.allowed_project_ids()
    allowed_users = ctx.allowed_user_ids()
    if allowed_projects is None and allowed_users is None:
        return payload

    scope_meta: dict[str, Any] = {
        "applied": True,
        "role": ctx.role,
        "read_scope": access.read_scope.value if access.read_scope else "",
    }
    if operation:
        scope_meta["operation"] = operation

    items, holder, key = _locate_response_item_list(payload)
    if items is not None:
        kept = [
            item
            for item in items
            if not isinstance(item, dict)
            or _item_in_read_scope(
                item,
                allowed_projects=allowed_projects,
                allowed_users=allowed_users,
            )
        ]
        removed = len(items) - len(kept)
        if removed > 0:
            _write_response_item_list(payload, holder, key, kept)
            scope_meta["removed_count"] = removed
            scope_meta["kept_count"] = len(kept)
            payload["permission_scope"] = scope_meta
        return payload

    data = payload.get("data")
    if isinstance(data, dict) and not _item_in_read_scope(
        data,
        allowed_projects=allowed_projects,
        allowed_users=allowed_users,
    ):
        out = dict(payload)
        out["data"] = None
        out["permission_scope"] = {
            **scope_meta,
            "filtered": True,
            "reason": "单条结果不在您的可见范围内",
        }
        return out

    return payload


def enforce_write_project_scope(body: dict[str, Any], ctx: PermissionContext) -> None:
    import api_client

    allowed = ctx.allowed_project_ids()
    if allowed is None:
        return
    pid = _parse_int(body.get("project_id"))
    if pid is None and body.get("sj_num"):
        try:
            pid = _parse_int(api_client.resolve_project_id({"sj_num": body.get("sj_num")}))
        except api_client.ClientError:
            pid = None
    if pid is not None and pid not in allowed:
        raise_permission_denied(
            "写操作目标项目不在您的权限范围内",
            role=ctx.role,
            ctx=ctx,
        )


def mask_tb_sensitive_fields(payload: Any) -> Any:
    def _walk(node: Any, parent_key: str = "") -> Any:
        if isinstance(node, dict):
            out: dict[str, Any] = {}
            for k, v in node.items():
                key_lower = str(k).lower()
                if key_lower in TB_MASK_FIELD_NAMES and not any(
                    hint in key_lower for hint in TB_KEEP_FIELD_HINTS
                ):
                    out[k] = None
                    out[f"{k}__masked"] = True
                    continue
                out[k] = _walk(v, key_lower)
            return out
        if isinstance(node, list):
            return [_walk(item, parent_key) for item in node]
        return node

    if isinstance(payload, dict) and "skill_summary" in payload:
        masked = dict(payload)
        masked["data"] = _walk(payload.get("data"))
        masked["tb_field_mask"] = True
        return masked
    result = _walk(payload)
    if isinstance(result, dict):
        result["tb_field_mask"] = True
    return result


def filter_operations_for_context(
    operations: dict[str, dict[str, Any]],
    ctx: PermissionContext,
) -> tuple[list[str], list[dict[str, str]]]:
    allowed: list[str] = []
    denied: list[dict[str, str]] = []
    for name, meta in sorted(operations.items()):
        access = check_operation_access(name, meta, ctx)
        if access.allowed:
            allowed.append(name)
        else:
            denied.append({"operation": name, "reason": access.reason})
    return allowed, denied


def load_permission_context_from_session(
    *,
    user_info: dict[str, Any],
    access_token: str,
    resolve_user_id: Any = None,
    nick_name_fallback: str | None = None,
) -> PermissionContext:
    import api_client

    user_id = _parse_int(user_info.get("id") or user_info.get("user_id"))
    if user_id is None and nick_name_fallback and resolve_user_id is not None:
        user_id = int(resolve_user_id(nick_name_fallback))
    if user_id is None:
        raise api_client.ClientError(
            "auth_required",
            "登录会话缺少 user_id，请让用户重新登录后重试业务命令",
        )
    root_id = user_info.get("root_id")
    meta = role_meta_from_root_id(root_id)
    role_code = meta.code if meta else role_from_root_id(root_id)
    return PermissionContext(
        user_id=user_id,
        nick_name=str(user_info.get("nick_name") or nick_name_fallback or user_id),
        role=role_code,
        role_id=_parse_int(root_id),
        role_title=meta.title if meta else "",
        role_description=meta.description if meta else "",
        dept_id=_parse_int(user_info.get("dept_id")),
        token=access_token,
    )


def enrich_permission_context(
    ctx: PermissionContext,
    *,
    api_request: Callable[..., Any],
    list_items: Callable[[Any], list[Any]],
    fetch_flat_departments: Callable[[], list[dict[str, Any]]],
) -> None:
    if ctx.is_privileged_read:
        return
    _load_participant_projects(ctx, api_request, list_items)
    if ctx.role in PROJECT_OWNER_READ_ROLES:
        _load_owner_projects(ctx, api_request, list_items)
    flat = fetch_flat_departments()
    _load_led_dept_scope(ctx, flat, api_request, list_items)
    if ctx.role == "GL":
        _load_team_scope(ctx, flat, api_request, list_items)


def _load_participant_projects(
    ctx: PermissionContext,
    api_request: Callable[..., Any],
    list_items: Callable[[Any], list[Any]],
) -> None:
    try:
        payload = api_request(
            "GET",
            "/manage_api/main_panel/get_project_list",
            {"page": 1, "limit": 500},
            token=ctx.token,
        )
    except Exception:
        return
    for item in list_items(payload):
        if isinstance(item, dict):
            pid = _parse_int(item.get("id") or item.get("project_id"))
            if pid is not None:
                ctx.participant_project_ids.add(pid)


def _load_owner_projects(
    ctx: PermissionContext,
    api_request: Callable[..., Any],
    list_items: Callable[[Any], list[Any]],
) -> None:
    try:
        payload = api_request(
            "GET",
            "/manage_api/project/get_project_list",
            {"page": 1, "limit": 500, "project_bd_tb": ctx.user_id},
            token=ctx.token,
        )
    except Exception:
        return
    for item in list_items(payload):
        if isinstance(item, dict):
            pid = _parse_int(item.get("id") or item.get("project_id"))
            if pid is not None:
                ctx.owner_project_ids.add(pid)
    ctx.participant_project_ids.update(ctx.owner_project_ids)


def _load_led_dept_scope(
    ctx: PermissionContext,
    flat: list[dict[str, Any]],
    api_request: Callable[..., Any],
    list_items: Callable[[Any], list[Any]],
) -> None:
    led_roots: list[int] = []
    for node in flat:
        if _parse_int(node.get("leader_id")) == ctx.user_id:
            ctx.is_dept_leader = True
            root = _parse_int(node.get("id"))
            if root is not None:
                led_roots.append(root)
    for root in led_roots:
        ctx.team_dept_ids.update(_collect_dept_subtree(root, flat))
    if not ctx.team_dept_ids:
        return
    users_payload = api_request(
        "GET",
        "/manage_api/user/get_user_list",
        {"page": 1, "limit": 500, "get_all": True},
        token=ctx.token,
    )
    for item in list_items(users_payload):
        if not isinstance(item, dict):
            continue
        uid = _parse_int(item.get("id"))
        dept = _parse_int(item.get("dept_id"))
        if uid is not None and dept in ctx.team_dept_ids:
            ctx.team_user_ids.add(uid)


def _load_team_scope(
    ctx: PermissionContext,
    flat: list[dict[str, Any]],
    api_request: Callable[..., Any],
    list_items: Callable[[Any], list[Any]],
) -> None:
    ctx.team_user_ids.add(ctx.user_id)
    if ctx.dept_id is None:
        return
    subtree = _collect_dept_subtree(ctx.dept_id, flat)
    ctx.team_dept_ids.update(subtree)
    users_payload = api_request(
        "GET",
        "/manage_api/user/get_user_list",
        {"page": 1, "limit": 500, "dept_id": ctx.dept_id},
        token=ctx.token,
    )
    for item in list_items(users_payload):
        if not isinstance(item, dict):
            continue
        uid = _parse_int(item.get("id"))
        dept = _parse_int(item.get("dept_id"))
        if uid is not None and dept in subtree:
            ctx.team_user_ids.add(uid)


def _collect_dept_subtree(root_id: int, flat: list[dict[str, Any]]) -> set[int]:
    ids = {root_id}
    changed = True
    while changed:
        changed = False
        for node in flat:
            nid = _parse_int(node.get("id"))
            pid = _parse_int(node.get("pid") or node.get("parent_id"))
            if nid is None or pid is None:
                continue
            if pid in ids and nid not in ids:
                ids.add(nid)
                changed = True
    return ids
