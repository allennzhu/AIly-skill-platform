"""Two-phase write protocol: dry_run preview → confirm_token → execute."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any

_CONTROL_KEYS = frozenset(
    {
        "dry_run",
        "confirm",
        "confirm_token",
        "force",
        "skip_confirm",
        "fetch_all",
        "auto_paginate",
        "page",
        "limit",
        "page_size",
    }
)


@dataclass
class WriteControl:
    dry_run: bool
    confirm: bool
    confirm_token: str | None
    force: bool


def _truthy(value: Any) -> bool:
    if value is None or value == "":
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "是", "确认")


def extract_write_control(params: dict[str, Any]) -> tuple[dict[str, Any], WriteControl]:
    out = dict(params)
    token = out.pop("confirm_token", None)
    force = _truthy(out.pop("force", None)) or _truthy(out.pop("skip_confirm", None))
    confirm = _truthy(out.pop("confirm", None))
    dry_run = _truthy(out.pop("dry_run", None))
    if not confirm and not dry_run and not force:
        dry_run = True
    return out, WriteControl(
        dry_run=dry_run and not confirm and not force,
        confirm=confirm,
        confirm_token=str(token).strip() if token not in (None, "") else None,
        force=force,
    )


def pick_body(resolved: dict[str, Any], body_keys: list[str]) -> dict[str, Any]:
    body: dict[str, Any] = {}
    for key in body_keys:
        if key not in resolved or resolved[key] in (None, ""):
            continue
        body[key] = resolved[key]
    return body


def _canonical_payload(operation: str, body: dict[str, Any]) -> str:
    return json.dumps(
        {"operation": operation, "body": body},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def create_confirm_token(operation: str, body: dict[str, Any], secret: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        _canonical_payload(operation, body).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:24]


def verify_confirm_token(
    operation: str, body: dict[str, Any], token: str | None, secret: str
) -> None:
    import api_client

    if not token:
        raise api_client.ClientError(
            "validation_error",
            "missing confirm_token; run with dry_run=1 first, then pass confirm_token on confirm",
        )
    expected = create_confirm_token(operation, body, secret)
    if not hmac.compare_digest(expected, token):
        raise api_client.ClientError(
            "validation_error",
            "confirm_token invalid or parameters changed; preview again with dry_run=1",
        )


def validate_required_body(
    body: dict[str, Any], required: list[str], operation: str
) -> list[str]:
    missing = [key for key in required if not body.get(key) and body.get(key) != 0]
    if missing:
        import api_client

        raise api_client.ClientError(
            "validation_error",
            f"{operation} missing required fields: {', '.join(missing)}",
        )
    return missing


def build_dry_run_response(
    operation: str,
    meta: dict[str, Any],
    body: dict[str, Any],
    secret: str,
    *,
    summary: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    from skill_enhancements import build_agent_hints

    token = create_confirm_token(operation, body, secret)
    warning_list = warnings or []
    return {
        "dry_run": True,
        "operation": operation,
        "description": meta.get("description", ""),
        "summary": summary or {},
        "resolved_body": body,
        "will_call": {
            "method": meta.get("method", "POST"),
            "path": meta.get("path", ""),
        },
        "warnings": warning_list,
        "agent_hints": build_agent_hints(warning_list),
        "confirm_token": token,
        "next_step": (
            "向用户展示 summary / resolved_body，确认后使用相同参数并追加 "
            "confirm=1 与 confirm_token（或 CLI --confirm --param confirm_token ...）"
        ),
    }


def _signing_secret() -> str:
    import api_client
    import hashlib

    cfg = api_client.load_config()
    return hashlib.sha256(f"pm-skill-confirm:{cfg['base_url']}".encode()).hexdigest()


def execute_write(
    operation: str,
    meta: dict[str, Any],
    body: dict[str, Any],
    control: WriteControl,
    token: str | None,
    api_request_fn,
) -> Any:
    import api_client

    secret = _signing_secret()

    if control.force:
        validate_required_body(body, meta.get("body_required", []), operation)
        return api_request_fn(
            meta["method"],
            meta["path"],
            json_body=body,
            token=token,
        )

    if control.confirm:
        validate_required_body(body, meta.get("body_required", []), operation)
        verify_confirm_token(operation, body, control.confirm_token, secret)
        payload = api_request_fn(
            meta["method"],
            meta["path"],
            json_body=body,
            token=token,
        )
        return {
            "dry_run": False,
            "operation": operation,
            "executed": True,
            "data": payload,
        }

    summary = meta.get("preview_summary")
    if callable(summary):
        summary = summary(body)
    elif summary is None:
        summary = {k: body.get(k) for k in meta.get("preview_keys", body.keys())}
    warnings_fn = meta.get("preview_warnings")
    warnings = warnings_fn(body) if callable(warnings_fn) else (warnings_fn or [])
    preview_required = meta.get("body_required_preview", meta.get("body_required", []))
    missing = [key for key in preview_required if body.get(key) in (None, "")]
    if missing:
        warnings = list(warnings) + [
            f"预览缺少字段（确认前需补全）: {', '.join(missing)}"
        ]
    return build_dry_run_response(
        operation,
        meta,
        body,
        secret,
        summary=summary,
        warnings=warnings,
    )


def execute_write_batch(
    operation: str,
    meta: dict[str, Any],
    bodies: list[dict[str, Any]],
    control: WriteControl,
    token: str | None,
    api_request_fn,
) -> Any:
    import api_client
    from skill_enhancements import build_agent_hints

    secret = _signing_secret()
    items: list[dict[str, Any]] = []
    for body in bodies:
        summary = meta.get("preview_summary")
        if callable(summary):
            summary = summary(body)
        warnings_fn = meta.get("preview_warnings")
        warnings = warnings_fn(body) if callable(warnings_fn) else (warnings_fn or [])
        preview = build_dry_run_response(
            operation,
            meta,
            body,
            secret,
            summary=summary,
            warnings=warnings,
        )
        preview["agent_hints"] = build_agent_hints(warnings)
        items.append(preview)
    return {
        "dry_run": True,
        "batch": True,
        "operation": operation,
        "count": len(items),
        "items": items,
        "next_step": "逐项向用户确认；每条使用对应 confirm_token 单独 confirm",
    }
