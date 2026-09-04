#!/usr/bin/env python3
"""51PM platform API client for Aily Skill."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "http://51pm.51aes.com:218"
DEFAULT_LOGIN_URL = "http://51pm.51aes.com:771"


class ConfigError(Exception):
    pass


class ClientError(Exception):
    def __init__(self, error: str, detail: str, status: int | None = None):
        super().__init__(detail)
        self.error = error
        self.detail = detail
        self.status = status


def error_payload(error: str, detail: str, status: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"error": error, "detail": detail}
    if status is not None:
        payload["status"] = status
    return payload


def emit_error_and_exit(error: str, detail: str, status: int | None = None) -> None:
    print(json.dumps(error_payload(error, detail, status), ensure_ascii=False))
    sys.exit(1)


def _load_file_config() -> dict[str, str]:
    """Aily 市场页通常没有环境变量入口，因此支持 scripts/config.json。"""
    here = Path(__file__).resolve().parent
    for path in (here / "config.json", here.parent / "config.json"):
        if not path.is_file():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise ConfigError(f"invalid config file {path}: {e}") from e
        if not isinstance(raw, dict):
            raise ConfigError(f"invalid config file {path}: must be a JSON object")
        return {
            "base_url": str(
                raw.get("base_url") or raw.get("PM_PLATFORM_BASE_URL") or ""
            ).rstrip("/"),
            "login_url": str(
                raw.get("login_url") or raw.get("PM_PLATFORM_LOGIN_URL") or ""
            ).rstrip("/"),
            "oauth_authorize_url": str(raw.get("oauth_authorize_url") or "").strip(),
            "oauth_client_id": str(raw.get("oauth_client_id") or "").strip(),
            "oauth_redirect_uri": str(raw.get("oauth_redirect_uri") or "").strip(),
        }
    return {}


def _load_example_config() -> dict[str, str]:
    here = Path(__file__).resolve().parent
    path = here / "config.example.json"
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {
        "base_url": str(raw.get("base_url") or "").rstrip("/"),
        "login_url": str(raw.get("login_url") or "").rstrip("/"),
    }


def load_config() -> dict[str, str]:
    file_cfg = _load_file_config()
    base_url = (
        os.environ.get("PM_PLATFORM_BASE_URL") or file_cfg.get("base_url") or ""
    ).rstrip("/")
    if not base_url:
        example_cfg = _load_example_config()
        base_url = (example_cfg.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
    if not base_url:
        base_url = DEFAULT_BASE_URL
    login_url = (
        os.environ.get("PM_PLATFORM_LOGIN_URL")
        or file_cfg.get("login_url")
        or ""
    ).rstrip("/")
    if not login_url:
        example_cfg = _load_example_config()
        login_url = (example_cfg.get("login_url") or DEFAULT_LOGIN_URL).rstrip("/")
    if not login_url:
        login_url = DEFAULT_LOGIN_URL
    return {
        "base_url": base_url,
        "login_url": login_url,
    }


def get_login_url() -> str:
    """51PM 网页登录入口（与 API base_url 端口可能不同）。"""
    return load_config()["login_url"]


_AUTH_RUNTIME: dict[str, Any] = {}


def _set_auth_runtime(auth_cfg: Any, access_token: str = "") -> None:
    _AUTH_RUNTIME["auth_cfg"] = auth_cfg
    token = str(access_token or "").strip()
    if token:
        _AUTH_RUNTIME["access_token"] = token


def _runtime_access_token() -> str | None:
    token = str(_AUTH_RUNTIME.get("access_token") or "").strip()
    return token or None


def _request_with_session(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    *,
    json_body: dict[str, Any] | None = None,
) -> Any:
    token = _runtime_access_token()
    return api_request(
        method,
        path,
        params,
        token=token,
        json_body=json_body,
        auth_sensitive=bool(token),
    )


def _clear_auth_runtime() -> None:
    _AUTH_RUNTIME.clear()


def _invalidate_auth_cache() -> None:
    from auth_session import invalidate_session

    auth_cfg = _AUTH_RUNTIME.get("auth_cfg")
    if auth_cfg is not None:
        invalidate_session(auth_cfg)


def _auth_required_payload(detail: str, login_url: str = "") -> dict[str, Any]:
    from auth_session import AuthRequired, build_ecp_login_url, load_auth_config

    if not login_url:
        auth_cfg = _AUTH_RUNTIME.get("auth_cfg")
        if auth_cfg is None:
            auth_cfg = load_auth_config(_load_file_config())
        login_url = build_ecp_login_url(auth_cfg)
    return AuthRequired(detail, login_url=login_url).to_payload()


def api_request(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    token: str | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: float = 30.0,
    *,
    anonymous: bool = False,
    auth_sensitive: bool = False,
) -> Any:
    cfg = load_config()
    clean_params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
    url = cfg["base_url"] + path
    if clean_params and method.upper() == "GET":
        url = url + "?" + urlencode(clean_params, doseq=True)
    headers = {
        "Accept": "application/json",
    }
    if not anonymous:
        bearer = token if token not in (None, "") else _runtime_access_token()
        if not bearer:
            raise ClientError(
                "auth_required",
                json.dumps(
                    _auth_required_payload("缺少登录 Token，请先完成 save-identity 与 51PM 登录"),
                    ensure_ascii=False,
                ),
            )
        headers["Authorization"] = f"Bearer {bearer}"
        # 使用会话 Token 时，业务码 444 / HTTP 401 应按登录失效处理
        if token in (None, ""):
            auth_sensitive = True
    data: bytes | None = None
    if json_body is not None:
        data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif clean_params and method.upper() != "GET":
        data = urlencode(clean_params, doseq=True).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except HTTPError as e:
        detail = e.reason or str(e)
        try:
            if e.fp is not None:
                detail = e.fp.read().decode("utf-8") or detail
        except Exception:
            pass
        if auth_sensitive and e.code in (401, 444):
            _invalidate_auth_cache()
            msg = "登录已失效（Token 过期），请重新登录 51PM" if e.code == 444 else "登录已失效（HTTP 401），请重新登录 51PM"
            raise ClientError(
                "auth_required",
                json.dumps(_auth_required_payload(msg)),
            ) from e
        raise ClientError("http_error", detail, status=e.code) from e
    except URLError as e:
        reason = e.reason if hasattr(e, "reason") else e
        raise ClientError("request_failed", str(reason)) from e
    except TimeoutError as e:
        raise ClientError("request_failed", "timeout") from e
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError as e:
        raise ClientError("request_failed", "invalid json response") from e
    if auth_sensitive and isinstance(payload, dict):
        from auth_session import is_auth_business_code

        if is_auth_business_code(payload.get("code")):
            _invalidate_auth_cache()
            msg = str(payload.get("msg") or "登录已失效，请重新登录 51PM")
            raise ClientError(
                "auth_required",
                json.dumps(_auth_required_payload(msg)),
            )
    return payload


def _filename_from_disposition(header: str) -> str:
    import re

    if not header:
        return ""
    match = re.search(r"filename\*=UTF-8''([^;]+)", header, re.I)
    if match:
        return match.group(1).strip()
    match = re.search(r'filename="?([^";]+)"?', header, re.I)
    return match.group(1).strip() if match else ""


def download_binary(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: float = 180.0,
    *,
    output_name: str = "",
) -> dict[str, Any]:
    """Download binary response (Excel export) and save under scripts/exports/."""
    cfg = load_config()
    clean_params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
    url = cfg["base_url"] + path
    if clean_params and method.upper() == "GET":
        url = url + "?" + urlencode(clean_params, doseq=True)
    headers = {"Accept": "*/*"}
    bearer = token if token not in (None, "") else _runtime_access_token()
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    elif token is None:
        raise ClientError(
            "auth_required",
            json.dumps(
                _auth_required_payload(
                    "缺少登录 Token，请先完成 save-identity 与 51PM 登录"
                ),
                ensure_ascii=False,
            ),
        )
    req = Request(url, headers=headers, method=method.upper())
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            content_type = resp.headers.get("Content-Type", "")
            disposition = resp.headers.get("Content-Disposition", "")
    except HTTPError as e:
        detail = e.reason or str(e)
        try:
            if e.fp is not None:
                detail = e.fp.read().decode("utf-8", errors="replace") or detail
        except Exception:
            pass
        raise ClientError("http_error", detail, status=e.code) from e
    except URLError as e:
        raise ClientError("request_failed", str(e)) from e
    except TimeoutError as e:
        raise ClientError("request_failed", "timeout") from e

    if not data:
        raise ClientError("export_failed", "导出文件为空")

    export_dir = Path(__file__).resolve().parent / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    file_name = (
        str(output_name or "").strip()
        or _filename_from_disposition(disposition)
        or "export_estimate_hour.xls"
    )
    if not file_name.lower().endswith((".xls", ".xlsx")):
        file_name += ".xls"
    file_path = export_dir / file_name
    file_path.write_bytes(data)
    return {
        "ok": True,
        "file_name": file_name,
        "file_path": str(file_path),
        "relative_path": f"scripts/exports/{file_name}",
        "size_bytes": len(data),
        "content_type": content_type,
        "message": "Excel 已导出，请将文件提供给用户下载",
    }


def _business_data(payload: Any) -> Any:
    """Unwrap GoFrame {code,msg,data} and nested Res.data when present."""
    if not isinstance(payload, dict):
        return None
    if _AUTH_RUNTIME:
        from auth_session import is_auth_business_code

        if is_auth_business_code(payload.get("code")):
            _invalidate_auth_cache()
            msg = str(payload.get("msg") or "登录已失效，请重新登录 51PM")
            raise ClientError(
                "auth_required",
                json.dumps(_auth_required_payload(msg)),
            )
    if "code" in payload and payload.get("code") not in (0, "0", None, ""):
        msg = payload.get("msg") or f"business code {payload.get('code')}"
        raise ClientError("resolve_failed", str(msg))
    data = payload.get("data", payload)
    # Res itself often has a nested "data" field (no top-level id)
    if isinstance(data, dict) and "data" in data and "id" not in data:
        return data.get("data")
    return data


def _extract_id(payload: Any, label: str) -> Any:
    data = _business_data(payload)
    if not data:
        raise ClientError("resolve_failed", f"{label} not found")
    if isinstance(data, list):
        if not data:
            raise ClientError("resolve_failed", f"{label} not found")
        data = data[0]
    item_id = data.get("id") if isinstance(data, dict) else None
    if item_id is None or item_id == "":
        raise ClientError("resolve_failed", f"{label} not found")
    return item_id


def resolve_user_id(user_name: str) -> str:
    try:
        payload = _request_with_session(
            "GET",
            "/manage_api/user/get_user_info_by_nick_name",
            {"nick_name": user_name},
        )
    except ClientError as e:
        if e.error == "auth_required":
            raise
        detail = str(e.detail or "")
        if "用户不存在" in detail:
            raise ClientError(
                "resolve_failed",
                f"未找到昵称「{user_name}」对应的 51PM 用户；请先 search_user 确认准确昵称",
            ) from e
        raise
    return str(_extract_id(payload, f"user: {user_name}"))


def resolve_dept_id(dept_name: str) -> int:
    payload = _request_with_session(
        "GET",
        "/manage_api/menu_department/get_dept_info_by_dept_name",
        {"dept_name": dept_name},
    )
    return int(_extract_id(payload, f"dept: {dept_name}"))


def _fetch_flat_departments() -> list[dict[str, Any]]:
    from team_scope import flatten_department_tree

    payload = _request_with_session(
        "GET",
        "/manage_api/menu_department/get_dept_list",
        {},
    )
    data: Any = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(data, list):
        data = []
    return flatten_department_tree(data)


def apply_name_resolution(params: dict[str, Any]) -> dict[str, Any]:
    out = dict(params)
    user_id = out.get("user_id")
    user_name = out.pop("user_name", None)
    if (user_id is None or user_id == "") and user_name:
        out["user_id"] = resolve_user_id(str(user_name))
    dept_id = out.get("dept_id")
    dept_name = out.pop("dept_name", None)
    if (dept_id is None or dept_id == "") and dept_name:
        out["dept_id"] = resolve_dept_id(str(dept_name))
    return out


_ROLE_NAME_FIELDS = {
    "pm_name": "project_pm",
    "develop_name": "project_develop",
    "tester_name": "project_tester",
    "bd_name": "project_bd_tb",
    "ui_name": "project_ui",
    "scene_duty_name": "project_scene_duty",
    "tech_name": "project_tech",
    "web_dev_name": "web_developer",
}

# 友好别名 → 平台字段（仅当目标字段未设置时生效）
_PROJECT_STRING_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("project_name",),
    "sj_num": ("opportunity_no", "business_no"),
    "ecp_qu_yu_tuan_dui": (
        "group_name",
        "team_name",
        "region_team",
        "qu_yu_tuan_dui",
        "ecp_group",
        "make_team",
    ),
    "kaigong_date_start": ("kaigong_start", "start_kaigong_date"),
    "kaigong_date_end": ("kaigong_end", "end_kaigong_date"),
    "ecp_kaigong_ling_shi_jian": (
        "ecp_kaigong_date",
        "kaigong_ling_date",
        "kaigong_ling_shi_jian",
    ),
    "income_date": ("revenue_date", "yinshou_date"),
    "ecp_shi_ye_bu": ("business_unit", "shi_ye_bu", "ecp_business_unit"),
    "ecp_shang_ji_hang_ye_lei_xing": (
        "industry_type",
        "hang_ye_lei_xing",
        "ecp_industry",
        "shang_ji_hang_ye",
    ),
    "project_scene": ("scene", "make_group", "project_scene_name", "scene_name"),
    "project_dta": ("dta", "dta_asset"),
    "ecp_stage": ("stage", "project_stage", "project_status", "status"),
    "project_process": ("process", "progress", "project_progress"),
    "risk_level": ("risk", "risk_level_name"),
}

_MY_PROJECTS_STRING_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("project_name",),
    "sj_num": ("opportunity_no", "business_no"),
    "ecp_stage": ("stage", "project_stage", "project_status", "status"),
    "kaigong_date_start": ("kaigong_start", "start_kaigong_date"),
    "kaigong_date_end": ("kaigong_end", "end_kaigong_date"),
}

_PROJECT_INT_ALIASES: dict[str, tuple[str, ...]] = {
    "is_income": ("income_status", "revenue_status", "yinshou_status"),
    "only_lizhi": ("only_resigned", "resigned_only"),
}


def _apply_field_aliases(
    out: dict[str, Any], aliases: dict[str, tuple[str, ...]]
) -> dict[str, Any]:
    for target, sources in aliases.items():
        if out.get(target) not in (None, ""):
            for src in sources:
                out.pop(src, None)
            continue
        for src in sources:
            val = out.pop(src, None)
            if val not in (None, ""):
                out[target] = val
                break
        else:
            for src in sources:
                out.pop(src, None)
    return out


def _apply_int_aliases(
    out: dict[str, Any], aliases: dict[str, tuple[str, ...]]
) -> dict[str, Any]:
    for target, sources in aliases.items():
        if out.get(target) not in (None, ""):
            for src in sources:
                out.pop(src, None)
            continue
        for src in sources:
            val = out.pop(src, None)
            if val in (None, ""):
                continue
            try:
                out[target] = int(val)
            except (TypeError, ValueError) as e:
                raise ClientError(
                    "validation_error", f"invalid integer for {target}: {val}"
                ) from e
            break
        else:
            for src in sources:
                out.pop(src, None)
    return out


def apply_project_param_resolution(params: dict[str, Any]) -> dict[str, Any]:
    """将用户友好参数转为 51PM get_project_list 所需字段。"""
    out = dict(params)
    out = _apply_field_aliases(out, _PROJECT_STRING_ALIASES)
    out = _apply_int_aliases(out, _PROJECT_INT_ALIASES)
    for name_key, id_key in _ROLE_NAME_FIELDS.items():
        role_name = out.pop(name_key, None)
        if role_name and not out.get(id_key):
            out[id_key] = resolve_user_id(str(role_name))
    return out


def apply_my_projects_param_resolution(params: dict[str, Any]) -> dict[str, Any]:
    """将用户友好参数转为 51PM main_panel/get_project_list 所需字段。"""
    out = dict(params)
    return _apply_field_aliases(out, _MY_PROJECTS_STRING_ALIASES)


_WORK_HOUR_STRING_ALIASES: dict[str, tuple[str, ...]] = {
    "start_date": ("date_start", "from_date"),
    "end_date": ("date_end", "to_date"),
    "project_type": ("type", "kind", "hour_type"),
    "output_type": ("output", "output_kind"),
    "estimate_type": ("leave_type",),
    "category_keyword": ("category", "not_project_keyword"),
}

_PROJECT_TYPE_MAP = {
    "all": "all",
    "全部": "all",
    "project": "project",
    "项目": "project",
    "not_project": "not_project",
    "非项目": "not_project",
}

_OUTPUT_TYPE_MAP = {
    "all": "all",
    "全部": "all",
    "output": "output",
    "产出": "output",
    "non_output": "non_output",
    "非产出": "non_output",
}

_CONFIRM_STATUS_MAP = {
    "all": -1,
    "全部": -1,
    "-1": -1,
    "pending": 0,
    "待确认": 0,
    "0": 0,
    "confirmed": 1,
    "已确认": 1,
    "1": 1,
}


def _parse_int_list(value: Any) -> list[int]:
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        items = [part.strip() for part in value.split(",") if part.strip()]
    else:
        items = [value]
    out: list[int] = []
    for item in items:
        try:
            out.append(int(item))
        except (TypeError, ValueError) as e:
            raise ClientError("validation_error", f"invalid integer list item: {item}") from e
    return out


def _normalize_enum(value: Any, mapping: dict[str, Any], default: Any = None) -> Any:
    if value in (None, ""):
        return default
    key = str(value).strip()
    if key in mapping:
        return mapping[key]
    lowered = key.lower()
    if lowered in mapping:
        return mapping[lowered]
    return key


def apply_work_hour_param_resolution(
    params: dict[str, Any], *, project_target: str = "ids"
) -> dict[str, Any]:
    """将用户友好参数转为工时统计/明细接口所需字段。"""
    out = dict(params)
    out = _apply_field_aliases(out, _WORK_HOUR_STRING_ALIASES)
    out = _apply_field_aliases(
        out,
        {
            "project_name": ("name",),
            "sj_num": ("opportunity_no", "business_no"),
        },
    )

    user_name = out.pop("user_name", None)
    if user_name and not out.get("user_ids"):
        out["user_ids"] = [int(resolve_user_id(str(user_name)))]
    dept_name = out.pop("dept_name", None)
    if dept_name and not out.get("dept_id"):
        out["dept_id"] = resolve_dept_id(str(dept_name))

    has_project_hint = any(
        out.get(key) not in (None, "")
        for key in ("project_name", "sj_num", "name", "opportunity_no", "business_no")
    )
    if has_project_hint:
        if project_target == "id" and not out.get("project_id"):
            out["project_id"] = resolve_project_id(out)
        elif project_target != "id" and not out.get("project_ids"):
            pid = out.get("project_id") or resolve_project_id(out)
            out["project_ids"] = _parse_int_list(pid)
        out.pop("project_name", None)
        out.pop("name", None)
        out.pop("sj_num", None)
        out.pop("opportunity_no", None)
        out.pop("business_no", None)
        if project_target == "id":
            out.pop("project_ids", None)

    if project_target != "id":
        project_id = out.get("project_id")
        if project_id not in (None, "") and not out.get("project_ids"):
            out["project_ids"] = _parse_int_list(project_id)
            out.pop("project_id", None)

    if out.get("user_ids") not in (None, "") and not isinstance(out.get("user_ids"), list):
        out["user_ids"] = _parse_int_list(out["user_ids"])
    if out.get("project_ids") not in (None, "") and not isinstance(out.get("project_ids"), list):
        out["project_ids"] = _parse_int_list(out["project_ids"])

    if "confirm_status" in out:
        mapped = _normalize_enum(out["confirm_status"], _CONFIRM_STATUS_MAP)
        if mapped is not None:
            out["confirm_status"] = mapped
    if "project_type" in out:
        mapped = _normalize_enum(out["project_type"], _PROJECT_TYPE_MAP, "all")
        if mapped is not None:
            out["project_type"] = mapped
    if "output_type" in out:
        mapped = _normalize_enum(out["output_type"], _OUTPUT_TYPE_MAP, "all")
        if mapped is not None:
            out["output_type"] = mapped
    return out


def build_upstream_query(
    resolved: dict[str, Any],
    upstream_params: list[str],
    array_params: list[str] | None = None,
) -> dict[str, Any]:
    array_params = array_params or []
    query: dict[str, Any] = {}
    for key in upstream_params:
        if key not in resolved or resolved[key] in (None, ""):
            continue
        value = resolved[key]
        if key in array_params:
            value = _parse_int_list(value)
            if not value:
                continue
        query[key] = value
    return query


def _list_items_from_response(payload: Any) -> list[dict[str, Any]]:
    data = _business_data(payload)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        items = data.get("data")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def resolve_project_id(params: dict[str, Any]) -> str:
    pid = params.get("id") or params.get("project_id")
    if pid not in (None, ""):
        return str(pid)
    sj_num = params.get("sj_num")
    project_name = params.get("project_name") or params.get("name")
    if not sj_num and project_name and str(project_name).upper().startswith("SJ"):
        sj_num = str(project_name)
        project_name = None
    search: dict[str, Any] = {"page": 1, "limit": 1}
    if sj_num:
        search["sj_num"] = sj_num
    elif project_name:
        search["name"] = project_name
    else:
        raise ClientError(
            "validation_error",
            "missing id/project_id or resolvable project_name/sj_num",
        )
    payload = _request_with_session(
        "GET",
        "/manage_api/project/get_project_list",
        search,
    )
    items = _list_items_from_response(payload)
    label = sj_num or project_name or "project"
    if not items:
        raise ClientError("resolve_failed", f"project: {label} not found")
    item_id = items[0].get("id")
    if item_id is None or item_id == "":
        raise ClientError("resolve_failed", f"project: {label} not found")
    return str(item_id)


_PROJECT_LIST_UPSTREAM = [
    "name",
    "sj_num",
    "kaigong_date_start",
    "kaigong_date_end",
    "ecp_kaigong_ling_shi_jian",
    "income_date",
    "is_income",
    "ecp_stage",
    "project_process",
    "risk_level",
    "ecp_shi_ye_bu",
    "ecp_shang_ji_hang_ye_lei_xing",
    "project_scene",
    "project_pm",
    "project_scene_duty",
    "project_develop",
    "project_tester",
    "project_bd_tb",
    "web_developer",
    "project_tech",
    "project_dta",
    "project_ui",
    "ecp_qu_yu_tuan_dui",
    "only_lizhi",
    "page",
    "limit",
]

_PROJECT_LIST_PARAMS = _PROJECT_LIST_UPSTREAM + [
    "page_size",
    # 角色昵称别名
    "pm_name",
    "develop_name",
    "tester_name",
    "bd_name",
    "ui_name",
    "scene_duty_name",
    "tech_name",
    "web_dev_name",
    # 字符串友好别名
    "project_name",
    "opportunity_no",
    "business_no",
    "group_name",
    "team_name",
    "region_team",
    "qu_yu_tuan_dui",
    "ecp_group",
    "make_team",
    "kaigong_start",
    "kaigong_end",
    "start_kaigong_date",
    "end_kaigong_date",
    "ecp_kaigong_date",
    "kaigong_ling_date",
    "kaigong_ling_shi_jian",
    "revenue_date",
    "yinshou_date",
    "business_unit",
    "shi_ye_bu",
    "ecp_business_unit",
    "industry_type",
    "hang_ye_lei_xing",
    "ecp_industry",
    "shang_ji_hang_ye",
    "scene",
    "make_group",
    "project_scene_name",
    "scene_name",
    "dta",
    "dta_asset",
    "stage",
    "project_stage",
    "project_status",
    "status",
    "process",
    "progress",
    "project_progress",
    "risk",
    "risk_level_name",
    # 整型友好别名
    "income_status",
    "revenue_status",
    "yinshou_status",
    "only_resigned",
    "resigned_only",
]

_MY_PROJECTS_UPSTREAM = [
    "name",
    "sj_num",
    "ecp_stage",
    "kaigong_date_start",
    "kaigong_date_end",
    "page",
    "limit",
]

_MY_PROJECTS_PARAMS = _MY_PROJECTS_UPSTREAM + [
    "page_size",
    "user_name",
    "project_name",
    "opportunity_no",
    "business_no",
    "stage",
    "project_stage",
    "project_status",
    "status",
    "kaigong_start",
    "kaigong_end",
    "start_kaigong_date",
    "end_kaigong_date",
]

_PROJECT_INFO_PARAMS = [
    "id",
    "project_id",
    "project_name",
    "name",
    "sj_num",
    "opportunity_no",
    "business_no",
]

_WORK_HOUR_COMMON_PARAMS = [
    "start_date",
    "end_date",
    "date_start",
    "date_end",
    "from_date",
    "to_date",
    "user_id",
    "user_ids",
    "user_name",
    "dept_id",
    "dept_name",
    "confirm_status",
    "project_type",
    "type",
    "kind",
    "hour_type",
    "project_id",
    "project_ids",
    "project_name",
    "name",
    "sj_num",
    "opportunity_no",
    "business_no",
    "page",
    "limit",
    "page_size",
]

_WORK_HOUR_STATISTICS_UPSTREAM = [
    "start_date",
    "end_date",
    "user_ids",
    "dept_id",
    "confirm_status",
    "project_type",
    "project_ids",
]

_WORK_HOUR_DETAIL_UPSTREAM = _WORK_HOUR_STATISTICS_UPSTREAM + [
    "output_type",
    "option_id",
    "estimate_type",
    "category_keyword",
    "page",
    "limit",
]

_PROJECT_WORK_HOURS_PARAMS = [
    "project_id",
    "project_name",
    "name",
    "sj_num",
    "opportunity_no",
    "business_no",
    "start_date",
    "end_date",
    "date_start",
    "date_end",
    "from_date",
    "to_date",
    "page",
    "limit",
    "page_size",
]

_PROJECT_WORK_HOURS_UPSTREAM = [
    "project_id",
    "start_date",
    "end_date",
    "page",
    "limit",
]

OPERATIONS: dict[str, dict[str, Any]] = {
    "get_work_hours": {
        "description": "获取工时记录（支持 user_name/dept_name 自动解析）",
        "method": "GET",
        "path": "/manage_api/data_export/get_daily_estimate_list",
        "params": [
            "start_date",
            "end_date",
            "user_id",
            "user_name",
            "dept_id",
            "dept_name",
            "page",
            "limit",
            "page_size",  # alias → limit
        ],
        "required": ["start_date", "end_date"],
        "resolve_names": True,
        "summarize": True,
        "upstream_params": [
            "start_date",
            "end_date",
            "user_id",
            "dept_id",
            "page",
            "limit",
        ],
    },
    "get_project_list": {
        "description": "查询项目列表（支持 pm_name/group_name 等友好参数自动解析）",
        "method": "GET",
        "path": "/manage_api/project/get_project_list",
        "params": _PROJECT_LIST_PARAMS,
        "resolve_project_filters": True,
        "upstream_params": _PROJECT_LIST_UPSTREAM,
    },
    "get_my_projects": {
        "description": "查询我参与的项目（当前登录用户；查他人项目请用 get_project_list）",
        "method": "GET",
        "path": "/manage_api/main_panel/get_project_list",
        "params": _MY_PROJECTS_PARAMS,
        "resolve_my_projects_filters": True,
        "upstream_params": _MY_PROJECTS_UPSTREAM,
    },
    "get_project_info": {
        "description": "查询项目详情（支持 project_name/sj_num 自动解析为 ID）",
        "method": "GET",
        "path": "/manage_api/project/get_project_info",
        "params": _PROJECT_INFO_PARAMS,
        "resolve_project_id": True,
        "resolve_project_info_aliases": True,
        "upstream_params": ["id"],
    },
    "get_project_work_hours": {
        "description": "查询某项目下的工时花费列表（支持 project_name/sj_num 自动解析）",
        "method": "GET",
        "path": "/manage_api/project_task_estimate/get_estimate_list_by_project_id",
        "params": _PROJECT_WORK_HOURS_PARAMS,
        "required": ["project_id", "project_name", "name", "sj_num", "opportunity_no", "business_no"],
        "required_any": True,
        "resolve_work_hour_filters": True,
        "project_id_target": "id",
        "resolve_project_id_field": "project_id",
        "upstream_params": _PROJECT_WORK_HOURS_UPSTREAM,
    },
    "get_work_hour_statistics": {
        "description": "工时数据总览（可按项目/人员/部门/时间范围统计）",
        "method": "GET",
        "path": "/manage_api/data_export/get_work_hour_statistics",
        "params": _WORK_HOUR_COMMON_PARAMS,
        "required": ["start_date", "end_date"],
        "resolve_work_hour_filters": True,
        "summarize": True,
        "upstream_params": _WORK_HOUR_STATISTICS_UPSTREAM,
        "array_params": ["user_ids", "project_ids"],
        "default_limit": 20,
    },
    "get_work_hour_detail_list": {
        "description": "工时下钻明细列表（可按项目/人员/部门/产出类型筛选）",
        "method": "GET",
        "path": "/manage_api/data_export/get_work_hour_detail_list",
        "params": _WORK_HOUR_COMMON_PARAMS
        + [
            "output_type",
            "output",
            "output_kind",
            "option_id",
            "estimate_type",
            "leave_type",
            "category_keyword",
            "category",
            "not_project_keyword",
        ],
        "required": ["start_date", "end_date"],
        "resolve_work_hour_filters": True,
        "upstream_params": _WORK_HOUR_DETAIL_UPSTREAM,
        "array_params": ["user_ids", "project_ids"],
        "default_limit": 20,
    },
}

from operations_extended import (
    _PROJECT_HINT_KEYS,
    build_extended_operations,
    resolve_extended,
)
from operations_domains import DOMAIN_OPERATIONS, DOMAIN_RESOLVE_MODES, resolve_domains
from operations_read_enhanced import (
    READ_ENHANCED_OPERATIONS,
    READ_ENHANCED_RESOLVE_MODES,
    resolve_read_enhanced,
)
from operations_write import (
    WRITE_OPERATIONS,
    resolve_write,
    enforce_unique_task_estimate,
    enforce_estimate_date_in_task_range,
    enforce_estimate_modifiable,
)
from operations_export import EXPORT_OPERATIONS, EXPORT_RESOLVE_MODES, resolve_export
from skill_enhancements import (
    apply_period_natural_language,
    attach_skill_summary,
    extract_page_items,
    infer_operation_group,
    inject_merged_items,
)
from write_protocol import execute_write, execute_write_batch, extract_write_control, pick_body
from permission_policy import (
    check_operation_access,
    enrich_permission_context,
    enforce_param_scope,
    enforce_write_project_scope,
    filter_operations_for_context,
    filter_read_response_scope,
    load_permission_context_from_session,
    mask_tb_sensitive_fields,
    permission_denied_payload,
    actor_payload,
)
from need_input import build_need_input_payload, collect_missing_required
from team_scope import apply_my_team_scope
from auth_session import (
    AuthIdentityRequired,
    AuthRequired,
    auth_status_payload,
    build_ecp_login_url,
    ensure_token,
    invalidate_session,
    load_auth_config,
    reject_tampered_identity_params,
    save_identity,
)

OPERATIONS.update(build_extended_operations(_PROJECT_LIST_PARAMS))
OPERATIONS.update(DOMAIN_OPERATIONS)
OPERATIONS.update(READ_ENHANCED_OPERATIONS)
OPERATIONS.update(WRITE_OPERATIONS)
OPERATIONS.update(EXPORT_OPERATIONS)

_NOT_PROJECT_HINT_KEYS = (
    "not_project_id",
    "not_project_name",
    "name",
    "project_id",
)


def _validate_operation_params(
    operation: str, meta: dict[str, Any], params: dict[str, Any]
) -> None:
    missing, one_of_failed = collect_missing_required(meta, params)
    if not missing and not one_of_failed:
        return
    if one_of_failed:
        payload = build_need_input_payload(
            operation,
            meta,
            missing_fields=[],
            provided=params,
            one_of_groups=one_of_failed,
            message="请向用户确认以下信息（任选其一或多项）",
        )
    else:
        payload = build_need_input_payload(
            operation,
            meta,
            missing_fields=missing,
            provided=params,
        )
    raise ClientError("need_input", json.dumps(payload, ensure_ascii=False))


def list_operations(grouped: bool = False, ctx: Any = None) -> Any:
    operations = OPERATIONS
    denied_meta: list[dict[str, str]] = []
    if ctx is not None:
        allowed_names, denied_meta = filter_operations_for_context(OPERATIONS, ctx)
        operations = {k: v for k, v in OPERATIONS.items() if k in allowed_names}
    items = []
    for name, meta in operations.items():
        group = infer_operation_group(name, meta)
        entry: dict[str, Any] = {
            "name": name,
            "description": meta["description"],
            "params": meta["params"],
            "group": group,
        }
        if meta.get("write"):
            entry["write"] = True
        items.append(entry)
    if ctx is not None and not grouped:
        payload: dict[str, Any] = {
            "actor": actor_payload(ctx),
            "operations": items,
        }
        if denied_meta:
            payload["denied_operations"] = denied_meta
        return payload
    if not grouped:
        return items
    buckets: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        buckets.setdefault(item["group"], []).append(item)
    if ctx is not None:
        result: dict[str, Any] = {
            "actor": actor_payload(ctx),
            "groups": buckets,
        }
        if denied_meta:
            result["denied_operations"] = denied_meta
        return result
    return buckets


def _resolve_permission_context(params: dict[str, Any]) -> Any:
    work = dict(params)
    reject_tampered_identity_params(work)

    file_cfg = _load_file_config()
    auth_cfg = load_auth_config(file_cfg)
    _set_auth_runtime(auth_cfg)

    try:
        session = ensure_token(
            auth_cfg,
            api_request=api_request,
        )
    except AuthRequired as e:
        invalidate_session(auth_cfg)
        raise ClientError("auth_required", json.dumps(e.to_payload(), ensure_ascii=False))
    except AuthIdentityRequired as e:
        raise ClientError("identity_required", json.dumps(e.to_payload(), ensure_ascii=False))
    _set_auth_runtime(auth_cfg, str(session["access_token"]))
    user_info = session.get("user_info") or {}
    nick_fallback = str(user_info.get("nick_name") or "")
    ctx = load_permission_context_from_session(
        user_info=user_info,
        access_token=str(session["access_token"]),
        resolve_user_id=resolve_user_id,
        nick_name_fallback=nick_fallback,
    )
    enrich_permission_context(
        ctx,
        api_request=api_request,
        list_items=_list_items_from_response,
        fetch_flat_departments=_fetch_flat_departments,
    )
    return ctx, ctx.nick_name


def run_auth_command(action: str, params: dict[str, Any]) -> Any:
    file_cfg = _load_file_config()
    auth_cfg = load_auth_config(file_cfg)

    if action == "save-identity":
        union_id = str(params.get("union_id") or params.get("feishu_union_id") or "")
        email = str(params.get("email") or params.get("feishu_email") or "")
        try:
            saved = save_identity(union_id=union_id, email=email, source="agent")
        except ValueError as e:
            raise ClientError("auth_error", str(e)) from e
        return {
            "ok": True,
            "identity": saved,
            "message": "身份已保存，请重试原业务命令",
        }

    if action == "status":
        return auth_status_payload(
            auth_cfg,
            api_request=api_request,
        )

    raise ClientError(
        "auth_error",
        "可用: auth --param action status | auth --param action save-identity "
        "--param union_id on_xxx [--param email user@example.com]",
    )


def _should_fetch_all(params: dict[str, Any], meta: dict[str, Any]) -> bool:
    flag = params.pop("fetch_all", None)
    if flag is None:
        flag = params.pop("auto_paginate", None)
    if flag is None:
        return False
    return str(flag).strip().lower() in ("1", "true", "yes", "是")


def _execute_operation(
    meta: dict[str, Any],
    query: dict[str, Any],
    token: str | None,
    fetch_all: bool,
    *,
    auth_sensitive: bool = False,
) -> Any:
    if not fetch_all or not meta.get("paginated", True):
        return api_request(
            meta["method"],
            meta["path"],
            query,
            token=token,
            auth_sensitive=auth_sensitive,
        )

    all_items: list[Any] = []
    last_payload: Any = None
    limit = int(query.get("limit") or meta.get("default_limit", 20))
    page = 1
    while page <= 50:
        page_query = dict(query)
        page_query["page"] = page
        page_query["limit"] = limit
        payload = api_request(
            meta["method"],
            meta["path"],
            page_query,
            token=token,
            auth_sensitive=auth_sensitive,
        )
        last_payload = payload
        items, total = extract_page_items(payload)
        if not items:
            break
        all_items.extend(items)
        if total is not None and len(all_items) >= total:
            break
        if len(items) < limit:
            break
        page += 1
    if last_payload is None:
        return {"data": []}
    return inject_merged_items(last_payload, all_items)


def run_operation(name: str, params: dict[str, Any]) -> Any:
    if name not in OPERATIONS:
        raise ClientError("unknown_operation", name)
    meta = OPERATIONS[name]
    work_params = dict(params)
    team_scope_meta: dict[str, Any] | None = None
    try:
        ctx, _act_as = _resolve_permission_context(work_params)
        token = ctx.token if ctx else None
        if ctx is not None:
            work_params, team_scope_meta = apply_my_team_scope(
                work_params,
                user_id=ctx.user_id,
                fallback_dept_id=ctx.dept_id,
                fetch_departments=_fetch_flat_departments,
            )

        _validate_operation_params(name, meta, work_params)
        access: Any = None
        if ctx is not None:
            access = check_operation_access(name, meta, ctx)
            if not access.allowed:
                raise ClientError(
                    "permission_denied",
                    json.dumps(
                        permission_denied_payload(
                            access.reason,
                            operation=name,
                            role=ctx.role,
                        ),
                        ensure_ascii=False,
                    ),
                )
        if meta.get("write"):
            wparams, control = extract_write_control(dict(work_params))
            resolve_mode = meta.get("write_resolve_mode")
            resolved = resolve_write(resolve_mode, wparams) if resolve_mode else wparams
            batch_ids = resolved.pop("_batch_ids", None)
            body_keys = meta.get("body_params", [])
            if batch_ids and not control.confirm and not control.force:
                bodies = []
                for eid in batch_ids:
                    item = dict(resolved)
                    item["id"] = eid
                    bodies.append(pick_body(item, body_keys))
                return execute_write_batch(
                    name, meta, bodies, control, token, api_request
                )
            body = pick_body(resolved, body_keys)
            if ctx is not None:
                enforce_write_project_scope(body, ctx)
            if ctx is not None:
                enforce_estimate_date_in_task_range(
                    name,
                    body,
                    token=token,
                    api_request_fn=api_request,
                )
                enforce_estimate_modifiable(
                    name,
                    body,
                    token=token,
                    api_request_fn=api_request,
                )
                enforce_unique_task_estimate(
                    name,
                    body,
                    token=token,
                    api_request_fn=api_request,
                    actor_user_id=ctx.user_id,
                )
            else:
                enforce_estimate_date_in_task_range(
                    name,
                    body,
                    token=token,
                    api_request_fn=api_request,
                )
                enforce_estimate_modifiable(
                    name,
                    body,
                    token=token,
                    api_request_fn=api_request,
                )
                enforce_unique_task_estimate(
                    name,
                    body,
                    token=token,
                    api_request_fn=api_request,
                )
            return execute_write(name, meta, body, control, token, api_request)
        resolved = dict(work_params)
        summarize = _should_summarize(resolved, meta)
        fetch_all = _should_fetch_all(resolved, meta)
        resolved = apply_period_natural_language(resolved)
        if meta.get("resolve_names"):
            resolved = apply_name_resolution(resolved)
        if meta.get("resolve_project_filters"):
            resolved = apply_project_param_resolution(resolved)
        if meta.get("resolve_my_projects_filters"):
            resolved = apply_my_projects_param_resolution(resolved)
        if meta.get("resolve_work_hour_filters"):
            resolved = apply_work_hour_param_resolution(
                resolved, project_target=meta.get("project_id_target", "ids")
            )
        resolve_mode = meta.get("resolve_mode")
        if resolve_mode:
            if resolve_mode in EXPORT_RESOLVE_MODES:
                resolved = resolve_export(resolve_mode, resolved)
            elif resolve_mode in READ_ENHANCED_RESOLVE_MODES:
                resolved = resolve_read_enhanced(resolve_mode, resolved)
            elif resolve_mode in DOMAIN_RESOLVE_MODES:
                resolved = resolve_domains(resolve_mode, resolved)
            else:
                resolved = resolve_extended(resolve_mode, resolved)
        if name == "get_task_list" and ctx is not None:
            if resolved.get("assigned_to_me"):
                resolved["assigned_to"] = [int(ctx.user_id)]
            resolved.pop("assigned_to_me", None)
            resolved.pop("done_by_me", None)
        if name == "get_project_demand_list" and ctx is not None:
            if resolved.get("assigned_to_me") and not resolved.get("assigned_to"):
                resolved["assigned_to"] = int(ctx.user_id)
            resolved.pop("assigned_to_me", None)
        if meta.get("resolve_project_info_aliases"):
            resolved = _apply_field_aliases(
                resolved,
                {
                    "project_name": ("name",),
                    "sj_num": ("opportunity_no", "business_no"),
                },
            )
            if resolved.get("name") and not resolved.get("project_name"):
                resolved["project_name"] = resolved.pop("name")
        token = ctx.token if ctx else token
        if meta.get("resolve_project_id"):
            resolved["id"] = resolve_project_id(resolved)
            resolved.pop("project_id", None)
            resolved.pop("project_name", None)
            resolved.pop("name", None)
            resolved.pop("sj_num", None)
            resolved.pop("opportunity_no", None)
            resolved.pop("business_no", None)
        project_id_field = meta.get("resolve_project_id_field")
        if project_id_field and not resolved.get(project_id_field):
            resolved[project_id_field] = resolve_project_id(resolved)
            resolved.pop("project_name", None)
            resolved.pop("name", None)
            resolved.pop("sj_num", None)
            resolved.pop("opportunity_no", None)
            resolved.pop("business_no", None)
        if not resolved.get("id") and resolved.get("moment_id"):
            resolved["id"] = resolved.pop("moment_id")
        if not resolved.get("id") and resolved.get("bug_id"):
            resolved["id"] = resolved.pop("bug_id")
        if not resolved.get("id") and resolved.get("publish_id"):
            resolved["id"] = resolved.pop("publish_id")
        if not resolved.get("id") and resolved.get("task_id"):
            resolved["id"] = resolved.pop("task_id")
        for alias in meta.get("id_aliases", ()):
            if not resolved.get(alias) and resolved.get("id"):
                resolved[alias] = resolved["id"]
            elif not resolved.get("id") and resolved.get(alias):
                resolved["id"] = resolved.pop(alias)
        if ctx is not None and access is not None:
            enforce_param_scope(name, resolved, ctx, access)
        if resolved.get("cost_type") and not resolved.get("type"):
            resolved["type"] = resolved.pop("cost_type")
        output_name = str(resolved.pop("output_name", "") or "").strip()
        if meta.get("binary_export"):
            query = build_upstream_query(
                resolved,
                meta["upstream_params"],
                meta.get("array_params", []),
            )
            result = download_binary(
                meta["method"],
                meta["path"],
                query,
                token=token,
                output_name=output_name,
            )
            if ctx:
                result["actor"] = actor_payload(ctx)
            return result
        if "page" not in resolved or resolved["page"] in (None, ""):
            resolved["page"] = 1
        if (resolved.get("limit") in (None, "")) and resolved.get("page_size") not in (
            None,
            "",
        ):
            resolved["limit"] = resolved["page_size"]
        if "limit" not in resolved or resolved["limit"] in (None, ""):
            resolved["limit"] = meta.get("default_limit", 500)
        resolved.pop("page_size", None)
        query = build_upstream_query(
            resolved,
            meta["upstream_params"],
            meta.get("array_params", []),
        )
        auth_sensitive = ctx is not None
        result = attach_skill_summary(
            name,
            _execute_operation(meta, query, token, fetch_all, auth_sensitive=auth_sensitive),
            summarize,
        )
        if ctx is not None and access is not None:
            result = filter_read_response_scope(
                result,
                ctx,
                access,
                operation=name,
            )
        if ctx is not None and access is not None and access.mask_tb_fields:
            result = mask_tb_sensitive_fields(result)
        if ctx:
            if isinstance(result, dict):
                result.setdefault("actor", actor_payload(ctx))
            else:
                result = {
                    "data": result,
                    "actor": actor_payload(ctx),
                }
        if team_scope_meta and isinstance(result, dict):
            result["team_scope"] = team_scope_meta
        return result
    finally:
        _clear_auth_runtime()


def _should_summarize(params: dict[str, Any], meta: dict[str, Any]) -> bool:
    flag = params.pop("summarize", None)
    if flag is None:
        return bool(meta.get("summarize"))
    return str(flag).strip().lower() in ("1", "true", "yes", "是")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="51PM API client for Aily Skill")
    parser.add_argument("operation", nargs="?", help="operation name")
    parser.add_argument("--list-ops", action="store_true")
    parser.add_argument("--list-ops-grouped", action="store_true")
    parser.add_argument("--fetch-all", action="store_true", help="auto paginate and merge all pages")
    parser.add_argument("--dry-run", action="store_true", help="write op: preview only (default for writes)")
    parser.add_argument("--confirm", action="store_true", help="write op: execute after dry_run preview")
    parser.add_argument("--summarize", action="store_true", help="attach skill_summary for supported read ops")
    parser.add_argument(
        "--param",
        nargs=2,
        action="append",
        default=[],
        metavar=("KEY", "VALUE"),
    )
    args = parser.parse_args(argv)
    try:
        param_map = {k: v for k, v in args.param}

        if args.operation == "auth":
            auth_params = dict(param_map)
            auth_action = auth_params.pop("action", None) or auth_params.pop("subcommand", None)
            if not auth_action:
                raise ClientError(
                    "validation_error",
                    "auth 用法: auth --param action status | "
                    "auth --param action save-identity --param union_id on_xxx",
                )
            print(json.dumps(run_auth_command(str(auth_action), auth_params), ensure_ascii=False))
            return 0

        reject_tampered_identity_params(param_map)
        ctx = None
        try:
            ctx, _actor = _resolve_permission_context(param_map)
        except ClientError as e:
            if e.error not in ("auth_required", "identity_required") or args.list_ops or args.list_ops_grouped:
                raise
        if args.list_ops or args.list_ops_grouped:
            print(
                json.dumps(
                    list_operations(grouped=args.list_ops_grouped, ctx=ctx),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        if not args.operation:
            raise ClientError(
                "validation_error",
                "operation name required (or use --list-ops)",
            )
        params = dict(param_map)
        if args.fetch_all:
            params["fetch_all"] = "1"
        if args.dry_run:
            params["dry_run"] = "1"
        if args.confirm:
            params["confirm"] = "1"
        if args.summarize:
            params["summarize"] = "1"
        result = run_operation(args.operation, params)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except ConfigError as e:
        print(json.dumps(error_payload("config_error", str(e)), ensure_ascii=False))
        return 1
    except ClientError as e:
        if e.error in (
            "auth_required",
            "need_input",
            "identity_required",
            "permission_denied",
            "duplicate_estimate",
            "estimate_date_out_of_range",
            "estimate_confirmed_immutable",
            "estimate_historical_immutable",
        ):
            try:
                payload = json.loads(e.detail)
                print(json.dumps(payload, ensure_ascii=False))
            except json.JSONDecodeError:
                print(json.dumps(error_payload(e.error, e.detail, e.status), ensure_ascii=False))
        else:
            print(json.dumps(error_payload(e.error, e.detail, e.status), ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
