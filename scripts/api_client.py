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
            "auth_type": str(
                raw.get("auth_type") or raw.get("PM_PLATFORM_AUTH_TYPE") or ""
            ).strip(),
            "api_key": str(
                raw.get("api_key") or raw.get("PM_PLATFORM_API_KEY") or ""
            ).strip(),
        }
    return {}


def load_config() -> dict[str, str]:
    file_cfg = _load_file_config()
    # 环境变量优先，其次 config.json（适配 Aily 无环境变量 UI 的情况）
    base_url = (
        os.environ.get("PM_PLATFORM_BASE_URL") or file_cfg.get("base_url") or ""
    ).rstrip("/")
    auth_type = (
        os.environ.get("PM_PLATFORM_AUTH_TYPE") or file_cfg.get("auth_type") or ""
    ).strip()
    api_key = (
        os.environ.get("PM_PLATFORM_API_KEY") or file_cfg.get("api_key") or ""
    ).strip()
    if not base_url:
        raise ConfigError(
            "PM_PLATFORM_BASE_URL missing (set env or scripts/config.json)"
        )
    if not api_key:
        raise ConfigError(
            "PM_PLATFORM_API_KEY missing (set env or scripts/config.json)"
        )
    if auth_type and auth_type != "api_key":
        raise ConfigError("PM_PLATFORM_AUTH_TYPE must be api_key")
    return {
        "base_url": base_url,
        "auth_type": auth_type or "api_key",
        "api_key": api_key,
    }


def api_request(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> Any:
    cfg = load_config()
    clean_params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
    url = cfg["base_url"] + path
    if clean_params and method.upper() == "GET":
        url = url + "?" + urlencode(clean_params, doseq=True)
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Accept": "application/json",
    }
    req = Request(url, data=None, headers=headers, method=method.upper())
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
        raise ClientError("http_error", detail, status=e.code) from e
    except URLError as e:
        reason = e.reason if hasattr(e, "reason") else e
        raise ClientError("request_failed", str(reason)) from e
    except TimeoutError as e:
        raise ClientError("request_failed", "timeout") from e
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError as e:
        raise ClientError("request_failed", "invalid json response") from e


def _business_data(payload: Any) -> Any:
    """Unwrap GoFrame {code,msg,data} and nested Res.data when present."""
    if not isinstance(payload, dict):
        return None
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
    payload = api_request(
        "GET",
        "/manage_api/user/get_user_info_by_nick_name",
        {"nick_name": user_name},
    )
    return str(_extract_id(payload, f"user: {user_name}"))


def resolve_dept_id(dept_name: str) -> int:
    payload = api_request(
        "GET",
        "/manage_api/menu_department/get_dept_info_by_dept_name",
        {"dept_name": dept_name},
    )
    return int(_extract_id(payload, f"dept: {dept_name}"))


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
        "upstream_params": [
            "start_date",
            "end_date",
            "user_id",
            "dept_id",
            "page",
            "limit",
        ],
    },
}


def list_operations() -> list[dict[str, Any]]:
    return [
        {"name": name, "description": meta["description"], "params": meta["params"]}
        for name, meta in OPERATIONS.items()
    ]


def run_operation(name: str, params: dict[str, Any]) -> Any:
    if name not in OPERATIONS:
        raise ClientError("unknown_operation", name)
    meta = OPERATIONS[name]
    for key in meta.get("required", []):
        if not params.get(key):
            raise ClientError("validation_error", f"missing required param: {key}")
    resolved = apply_name_resolution(params) if meta.get("resolve_names") else dict(params)
    if "page" not in resolved or resolved["page"] in (None, ""):
        resolved["page"] = 1
    # 51PM PaginationReq uses `limit`; accept page_size as alias
    if (resolved.get("limit") in (None, "")) and resolved.get("page_size") not in (None, ""):
        resolved["limit"] = resolved["page_size"]
    if "limit" not in resolved or resolved["limit"] in (None, ""):
        resolved["limit"] = 500
    resolved.pop("page_size", None)
    query = {
        k: resolved[k]
        for k in meta["upstream_params"]
        if k in resolved and resolved[k] not in (None, "")
    }
    return api_request(meta["method"], meta["path"], query)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="51PM API client for Aily Skill")
    parser.add_argument("operation", nargs="?", help="operation name")
    parser.add_argument("--list-ops", action="store_true")
    parser.add_argument(
        "--param",
        nargs=2,
        action="append",
        default=[],
        metavar=("KEY", "VALUE"),
    )
    args = parser.parse_args(argv)
    try:
        if args.list_ops:
            print(json.dumps(list_operations(), ensure_ascii=False, indent=2))
            return 0
        if not args.operation:
            raise ClientError(
                "validation_error",
                "operation name required (or use --list-ops)",
            )
        params = {k: v for k, v in args.param}
        result = run_operation(args.operation, params)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except ConfigError as e:
        print(json.dumps(error_payload("config_error", str(e)), ensure_ascii=False))
        return 1
    except ClientError as e:
        print(json.dumps(error_payload(e.error, e.detail, e.status), ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
