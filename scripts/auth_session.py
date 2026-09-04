"""Skill auth — minimal flow for refactor.

Agent responsibilities (outside this script):
  1. Obtain user_access_token for the current Feishu conversation user
  2. Call Feishu APIs → union_id and/or email
  3. Save identity once: auth --param action save-identity ...

This script:
  1. Read saved identity from .feishu_identity.json
  2. GET /manage_api/skill_auth/token (no auth) by union_id
  3. No token → auth_required (user logs in on :771, then retry)
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

SKILL_AUTH_TOKEN_PATH = "/manage_api/skill_auth/token"
IDENTITY_FILE = ".feishu_identity.json"
AUTH_BUSINESS_CODES = frozenset({444})

DEFAULT_OAUTH_AUTHORIZE_URL = "http://cas.51aes.com/oauth/authorize"
DEFAULT_OAUTH_CLIENT_ID = "vtWuKx7A"
DEFAULT_OAUTH_REDIRECT_URI = "http://51pm.51aes.com:771"


class AuthIdentityRequired(Exception):
    def __init__(self, detail: str = "尚未保存飞书用户身份"):
        super().__init__(detail)
        self.detail = detail

    def to_payload(self) -> dict[str, Any]:
        return {
            "error": "identity_required",
            "detail": self.detail,
            "message": (
                "飞书智能体须先用 user_access_token 调飞书 API 获取对话人的 "
                "union_id 或邮箱，保存后再执行业务命令。"
            ),
            "next_step": [
                "1. 用 user_access_token 获取当前对话人信息",
                "2. 调飞书 API 获取 union_id 或邮箱",
                "3. python3 scripts/api_client.py auth --param action save-identity "
                "--param union_id on_xxxxxxxx",
                "4. 重试原业务命令",
            ],
        }


class AuthRequired(Exception):
    def __init__(self, detail: str, *, login_url: str, redirect_uri: str = ""):
        super().__init__(detail)
        self.detail = detail
        self.login_url = login_url
        self.redirect_uri = redirect_uri or DEFAULT_OAUTH_REDIRECT_URI

    def to_payload(self) -> dict[str, Any]:
        return {
            "error": "auth_required",
            "detail": self.detail,
            "login_url": self.login_url,
            "redirect_uri": self.redirect_uri,
            "message": (
                "请打开 51PM：已登录则打开首页即可同步 Token；"
                "未登录请点 login_url 完成 OAuth（授权/同意后回到 51PM）"
            ),
            "next_step": (
                "用户打开 51PM 首页（或 login_url）完成后，重试同一条业务命令；"
                "若仍失败可能是飞书账号未绑定 51PM"
            ),
        }


@dataclass
class AuthConfig:
    oauth_authorize_url: str = DEFAULT_OAUTH_AUTHORIZE_URL
    oauth_client_id: str = DEFAULT_OAUTH_CLIENT_ID
    oauth_redirect_uri: str = DEFAULT_OAUTH_REDIRECT_URI


def _scripts_dir() -> Path:
    return Path(__file__).resolve().parent


def load_auth_config(file_cfg: dict[str, str]) -> AuthConfig:
    redirect_uri = str(
        file_cfg.get("oauth_redirect_uri")
        or os.environ.get("PM_PLATFORM_OAUTH_REDIRECT_URI")
        or file_cfg.get("login_url")
        or os.environ.get("PM_PLATFORM_LOGIN_URL")
        or DEFAULT_OAUTH_REDIRECT_URI
    ).rstrip("/")
    authorize_url = str(
        file_cfg.get("oauth_authorize_url")
        or os.environ.get("PM_PLATFORM_OAUTH_AUTHORIZE_URL")
        or DEFAULT_OAUTH_AUTHORIZE_URL
    ).rstrip("/")
    client_id = str(
        file_cfg.get("oauth_client_id")
        or os.environ.get("PM_PLATFORM_OAUTH_CLIENT_ID")
        or DEFAULT_OAUTH_CLIENT_ID
    ).strip()
    return AuthConfig(
        oauth_authorize_url=authorize_url,
        oauth_client_id=client_id,
        oauth_redirect_uri=redirect_uri,
    )


def build_ecp_login_url(cfg: AuthConfig) -> str:
    redirect = quote(cfg.oauth_redirect_uri, safe="")
    return (
        f"{cfg.oauth_authorize_url}"
        f"?client_id={cfg.oauth_client_id}"
        f"&response_type=code"
        f"&scope=all"
        f"&redirect_uri={redirect}"
    )


def _api_data(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    data = payload.get("data", payload)
    return data if isinstance(data, dict) else {}


def _normalize_identity_value(value: Any) -> str:
    return str(value or "").strip().strip('"').strip("'")


def load_identity() -> dict[str, Any]:
    path = _scripts_dir() / IDENTITY_FILE
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_identity(
    *,
    union_id: str = "",
    email: str = "",
    source: str = "agent",
) -> dict[str, Any]:
    union_id = _normalize_identity_value(union_id)
    email = _normalize_identity_value(email)
    if not union_id and not email:
        raise ValueError("save-identity 需要 union_id 或 email 至少一项")

    existing = load_identity()
    payload: dict[str, Any] = {
        "saved_at": int(time.time()),
        "source": source,
    }
    if union_id:
        payload["feishu_union_id"] = union_id
    elif existing.get("feishu_union_id"):
        payload["feishu_union_id"] = existing["feishu_union_id"]

    if email:
        payload["email"] = email
    elif existing.get("email"):
        payload["email"] = existing["email"]

    (_scripts_dir() / IDENTITY_FILE).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def reject_tampered_identity_params(params: dict[str, Any] | None) -> None:
    """Business commands must not accept identity via CLI params."""
    p = dict(params or {})
    for key in (
        "feishu_union_id",
        "union_id",
        "feishu_open_id",
        "open_id",
        "email",
        "feishu_email",
    ):
        if _normalize_identity_value(p.get(key)):
            raise AuthIdentityRequired(f"禁止通过业务参数传入身份（{key}）")


def lookup_token(
    *,
    union_id: str,
    email: str,
    api_request: Callable[..., Any],
) -> dict[str, Any]:
    union_id = _normalize_identity_value(union_id)
    email = _normalize_identity_value(email)

    if union_id:
        payload = api_request(
            "GET",
            SKILL_AUTH_TOKEN_PATH,
            {"feishu_union_id": union_id},
            anonymous=True,
        )
        if isinstance(payload, dict) and int(payload.get("code", -1)) not in (0, -1):
            return {}
        return _api_data(payload)

    if email:
        # 预留：后端支持按邮箱查 token 后启用
        return {}

    return {}


def _session_from_remote(
    remote: dict[str, Any],
    *,
    identity: dict[str, Any],
) -> dict[str, Any] | None:
    if not remote.get("has_token"):
        return None
    access_token = _normalize_identity_value(remote.get("access_token"))
    if not access_token:
        return None
    user_raw = remote.get("user_info") or {}
    user_info = user_raw if isinstance(user_raw, dict) else {}
    if not user_info.get("nick_name"):
        user_info["nick_name"] = remote.get("nick_name")
    if not user_info.get("user_id"):
        user_info["user_id"] = remote.get("user_id")
    return {
        "access_token": access_token,
        "user_info": user_info,
        "feishu_union_id": identity.get("feishu_union_id", ""),
        "email": identity.get("email", ""),
    }


def ensure_token(
    cfg: AuthConfig,
    *,
    api_request: Callable[..., Any],
) -> dict[str, Any]:
    identity = load_identity()
    union_id = _normalize_identity_value(identity.get("feishu_union_id"))
    email = _normalize_identity_value(identity.get("email"))

    if not union_id and not email:
        raise AuthIdentityRequired()

    if not union_id and email:
        raise AuthIdentityRequired(
            "已保存邮箱但服务端暂仅支持 union_id 查 token，请补充 save-identity --param union_id on_xxx"
        )

    try:
        remote = lookup_token(union_id=union_id, email=email, api_request=api_request)
    except OSError as exc:
        raise AuthRequired(
            f"查询 Token 失败: {exc}",
            login_url=build_ecp_login_url(cfg),
            redirect_uri=cfg.oauth_redirect_uri,
        ) from exc

    session = _session_from_remote(remote, identity=identity)
    if session:
        return session

    raise AuthRequired(
        "尚未登录 51PM，请先完成网页登录",
        login_url=build_ecp_login_url(cfg),
        redirect_uri=cfg.oauth_redirect_uri,
    )


def auth_status_payload(
    cfg: AuthConfig,
    *,
    api_request: Callable[..., Any],
) -> dict[str, Any]:
    identity = load_identity()
    union_id = _normalize_identity_value(identity.get("feishu_union_id"))
    email = _normalize_identity_value(identity.get("email"))
    login_url = build_ecp_login_url(cfg)

    if not union_id and not email:
        payload = AuthIdentityRequired().to_payload()
        payload["authenticated"] = False
        return payload

    if not union_id:
        return {
            "authenticated": False,
            "email": email,
            "login_url": login_url,
            "message": "已保存邮箱，需补充 union_id 后才能查 token",
        }

    try:
        remote = lookup_token(union_id=union_id, email=email, api_request=api_request)
        session = _session_from_remote(remote, identity=identity)
        if session:
            info = session.get("user_info") or {}
            return {
                "authenticated": True,
                "feishu_union_id": union_id,
                "email": email or None,
                "nick_name": info.get("nick_name"),
                "user_id": info.get("user_id") or info.get("id"),
                "message": "已登录",
            }
    except OSError as exc:
        return {
            "authenticated": False,
            "feishu_union_id": union_id,
            "email": email or None,
            "login_url": login_url,
            "message": f"查询 Token 失败: {exc}",
        }

    return {
        "authenticated": False,
        "feishu_union_id": union_id,
        "email": email or None,
        "login_url": login_url,
        "message": "未登录，请把 login_url 发给用户登录后重试业务命令",
    }


def is_auth_business_code(code: Any) -> bool:
    try:
        return int(code) in AUTH_BUSINESS_CODES
    except (TypeError, ValueError):
        return False


def invalidate_session(_cfg: AuthConfig) -> None:
    """No local token cache; server session invalidation is handled on next lookup."""
    return None
