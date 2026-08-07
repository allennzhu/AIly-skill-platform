#!/usr/bin/env python3
"""51PM platform API client for pm-fill-hours skill."""

from __future__ import annotations

import json
import os
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
