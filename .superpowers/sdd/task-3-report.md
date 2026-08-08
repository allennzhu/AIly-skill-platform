# Task 3 Report — 配置、HTTP、超管请求

**Date:** 2026-08-07  
**Branch:** `feature/pm-platform-api-skill`  
**Status:** ✅ Complete

## Deliverables

| File | Action |
|------|--------|
| `pm-fill-hours/scripts/api_client.py` | Created |
| `pm-fill-hours/tests/test_api_client.py` | Extended (3 new tests) |

## Implemented Interfaces

- **`load_config() -> dict`** — env vars preferred over `scripts/config.json`; raises `ConfigError` when `base_url` or `api_key` missing.
- **`_load_file_config() -> dict`** — reads `scripts/config.json` or parent `config.json`.
- **`api_request(method, path, params=None, token=None, json_body=None) -> Any`**
  - Default auth: super-admin `api_key` from config.
  - `token=` overrides `Authorization: Bearer …`.
  - `json_body=` sends POST with `Content-Type: application/json`.
  - GoFrame: `code != 0` → `ClientError("business_error", msg)`.
  - HTTP/URL/timeout errors → `ClientError("http_error" | "request_failed", …)`.

## Tests (TDD)

```bash
pytest pm-fill-hours/tests -v
```

| Test | Purpose |
|------|---------|
| `test_load_config_requires_api_key` | Config validation (Task 2 placeholder) |
| `test_api_request_uses_override_token` | Token override per brief |
| `test_api_request_post_json_body` | POST JSON for impersonate path |
| `test_api_request_business_error` | GoFrame `code != 0` |

**Result:** 4 passed in ~0.03s

## Commit

```
feat: add fill-hours HTTP client and config
```

## Notes

- Independent copy of HTTP/config pattern from root `scripts/api_client.py`; no cross-import.
- Success responses return full parsed JSON (callers unwrap `data` in later tasks).
- `error_payload` / CLI deferred to later tasks.

## Next (Task 4)

- `resolve_feishu_user`, `impersonate`, `session_user_token`

---

## Review Fix (2026-08-07)

**Status:** ✅ Complete  
**Commit:** `fc05121` — `test: cover default token and env-over-file config for fill-hours`

### Added Tests

| Test | Purpose |
|------|---------|
| `test_api_request_default_super_token` | Without `token=`, `Authorization` uses `Bearer` from `PM_PLATFORM_API_KEY` |
| `test_load_config_env_overrides_file` | Env vars win over `_load_file_config` for `base_url` / `api_key` |

### Test Run

```bash
pytest pm-fill-hours/tests -v
```

**Result:** 6 passed in 0.03s
