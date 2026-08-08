#!/usr/bin/env python3
"""51PM platform API client for pm-fill-hours skill."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date as calendar_date
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


def _check_business_code(payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    code = payload.get("code")
    if code not in (0, "0", None, ""):
        msg = payload.get("msg") or f"business code {code}"
        raise ClientError("business_error", str(msg))


def api_request(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    token: str | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> Any:
    cfg = load_config()
    clean_params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
    url = cfg["base_url"] + path
    if clean_params and method.upper() == "GET":
        url = url + "?" + urlencode(clean_params, doseq=True)
    bearer = token if token is not None else cfg["api_key"]
    headers = {
        "Authorization": f"Bearer {bearer}",
        "Accept": "application/json",
    }
    data: bytes | None = None
    if json_body is not None:
        data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
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
    _check_business_code(payload)
    return payload


def _unwrap_data(payload: Any) -> Any:
    """Extract business payload from GoFrame {code, data, msg} envelope."""
    if isinstance(payload, dict) and "data" in payload:
        inner = payload["data"]
        if inner is not None:
            return inner
    return payload


def _extract_access_token(payload: Any) -> str:
    """Extract user access token from impersonate response (data.token_info.access_token)."""
    data = _unwrap_data(payload)
    if not isinstance(data, dict):
        raise ClientError("business_error", "missing token_info in impersonate response")
    token_info = data.get("token_info") or data.get("TokenInfo") or {}
    if not isinstance(token_info, dict):
        raise ClientError("business_error", "missing token_info in impersonate response")
    token = (
        token_info.get("access_token")
        or token_info.get("token")
        or token_info.get("Token")
    )
    if not token:
        raise ClientError("business_error", "missing access_token in impersonate response")
    return str(token)


def resolve_feishu_user(union_id: str) -> dict:
    payload = api_request(
        "GET",
        "/manage_api/qiye_user/get_user_by_feishu_union_id",
        params={"feishu_union_id": union_id},
    )
    data = _unwrap_data(payload)
    if not isinstance(data, dict):
        raise ClientError("business_error", "invalid user response")
    return data


def impersonate(user_id: int) -> str:
    payload = api_request(
        "POST",
        "/manage_api/user/impersonate_user",
        json_body={"target_user_id": user_id},
    )
    return _extract_access_token(payload)


def session_user_token(union_id: str) -> tuple[dict, str]:
    user = resolve_feishu_user(union_id)
    user_id = user.get("user_id")
    if user_id is None:
        raise ClientError("business_error", "missing user_id in feishu user response")
    token = impersonate(int(user_id))
    return user, token


def _normalize_task_item(item: dict, task_kind: str) -> dict:
    return {
        "task_id": item.get("id") or item.get("task_id"),
        "name": item.get("name", ""),
        "project_name": item.get("project_name", ""),
        "task_kind": task_kind,
    }


def _fetch_doing_tasks(user_token: str, path: str, task_kind: str) -> list[dict]:
    payload = api_request(
        "GET",
        path,
        params={"status": ["doing"]},
        token=user_token,
    )
    data = _unwrap_data(payload)
    if isinstance(data, dict):
        items = data.get("data") or []
    elif isinstance(data, list):
        items = data
    else:
        items = []
    return [_normalize_task_item(item, task_kind) for item in items if isinstance(item, dict)]


def list_doing_tasks(user_token: str, task_kind: str | None) -> list[dict]:
    if task_kind == "project":
        return _fetch_doing_tasks(
            user_token, "/manage_api/main_panel/get_task_list", "project"
        )
    if task_kind == "not_project":
        return _fetch_doing_tasks(
            user_token, "/manage_api/main_panel/get_not_task_list", "not_project"
        )
    project_tasks = _fetch_doing_tasks(
        user_token, "/manage_api/main_panel/get_task_list", "project"
    )
    not_project_tasks = _fetch_doing_tasks(
        user_token, "/manage_api/main_panel/get_not_task_list", "not_project"
    )
    return project_tasks + not_project_tasks


def submit_estimate(
    user_token: str,
    task_kind: str,
    task_id: int,
    date: str,
    consumed: float,
    remark: str,
) -> Any:
    if task_kind == "project":
        path = "/manage_api/project_task_estimate/add"
    elif task_kind == "not_project":
        path = "/manage_api/project_not_task_estimate/add"
    else:
        raise ClientError("business_error", f"unknown task_kind: {task_kind}")
    return api_request(
        "POST",
        path,
        token=user_token,
        json_body={
            "task_id": task_id,
            "date": date,
            "consumed": consumed,
            "remark": remark,
        },
    )


def _step_response(
    status: str,
    user: dict | None,
    collected: dict[str, Any],
    missing_fields: list[str] | None = None,
    next_question: str | None = None,
    task_options: list[dict] | None = None,
    result: Any = None,
) -> dict:
    return {
        "status": status,
        "user": user,
        "collected": collected,
        "missing_fields": missing_fields or [],
        "next_question": next_question,
        "task_options": task_options or [],
        "result": result,
    }


def _missing_question(field: str) -> str:
    questions = {
        "task_kind": "请选择任务类型（project 或 not_project）",
        "consumed": "请输入本次填写的工时（正数）",
        "remark": "请输入工时备注",
    }
    return questions[field]


def fill_hours_step(params: dict) -> dict:
    """Collect one fill-hours turn or submit a completed estimate."""
    union_id = str(params.get("feishu_union_id") or "").strip()
    if not union_id:
        raise ClientError("validation_error", "missing required param: feishu_union_id")

    collected = {
        "task_id": params.get("task_id") or None,
        "task_kind": params.get("task_kind") or None,
        "date": params.get("date") or calendar_date.today().isoformat(),
        "consumed": params.get("consumed") or None,
        "remark": params.get("remark") or None,
    }
    user, user_token = session_user_token(union_id)
    missing_fields = [
        field
        for field in ("task_id", "task_kind", "consumed", "remark")
        if collected[field] in (None, "")
    ]
    if missing_fields:
        if "task_id" in missing_fields:
            options = list_doing_tasks(user_token, collected["task_kind"])
            task_options = [
                {"index": index, **task} for index, task in enumerate(options, start=1)
            ]
            return _step_response(
                "need_input",
                user,
                collected,
                missing_fields,
                "请选择要填工时的任务（回复序号或任务名）",
                task_options,
            )
        return _step_response(
            "need_input",
            user,
            collected,
            missing_fields,
            _missing_question(missing_fields[0]),
        )

    try:
        task_id = int(collected["task_id"])
    except (TypeError, ValueError) as e:
        raise ClientError("validation_error", "task_id must be an integer") from e
    try:
        consumed = float(collected["consumed"])
    except (TypeError, ValueError) as e:
        raise ClientError("validation_error", "consumed must be a positive number") from e
    if consumed <= 0:
        raise ClientError("validation_error", "consumed must be a positive number")
    if collected["task_kind"] not in {"project", "not_project"}:
        raise ClientError(
            "validation_error", "task_kind must be project or not_project"
        )

    result = submit_estimate(
        user_token,
        collected["task_kind"],
        task_id,
        str(collected["date"]),
        consumed,
        str(collected["remark"]),
    )
    return _step_response("submitted", user, collected, result=result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="51PM fill-hours API client")
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
            print(json.dumps(["fill_hours_step"], ensure_ascii=False, indent=2))
            return 0
        if args.operation != "fill_hours_step":
            raise ClientError(
                "unknown_operation",
                args.operation or "operation name required (or use --list-ops)",
            )
        params = {key: value for key, value in args.param}
        print(json.dumps(fill_hours_step(params), ensure_ascii=False))
        return 0
    except ConfigError as e:
        print(json.dumps({"error": "config_error", "detail": str(e)}, ensure_ascii=False))
        return 1
    except ClientError as e:
        payload = {"error": e.error, "detail": e.detail}
        if e.status is not None:
            payload["status"] = e.status
        print(json.dumps(payload, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
