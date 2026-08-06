# Aily PM Platform Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建可打包的 Aily Skill（`pm-platform-api`），通过 CLI 调用 51PM 工时接口，支持人名/部门名自动解析，并由 SKILL.md 指导 Aily 生成工作总结。

**Architecture:** 单仓库 Skill 包。`api_client.py` 以 OPERATIONS 注册表驱动 HTTP 调用；`get_work_hours` 在请求前自动解析 `user_name`/`dept_name`；成功返回平台原始 JSON，失败返回统一 `error` JSON。Aily 只读 SKILL.md 编排与分析，不在脚本内写总结。

**Tech Stack:** Python 3.10+ 标准库（`urllib`/`json`/`argparse`/`os`/`sys`/`re`），pytest 单测（mock HTTP），无第三方运行时依赖。

## Global Constraints

- 仓库根目录即 Skill 根目录（含 `SKILL.md`），不是嵌套子包名目录。
- 认证仅环境变量：`PM_PLATFORM_BASE_URL`、`PM_PLATFORM_AUTH_TYPE`（固定 `api_key`）、`PM_PLATFORM_API_KEY`。
- 工时真实路径：`GET /manage_api/data_export/get_daily_estimate_list`。
- 用户名解析：`GET /manage_api/user/get_user_info_by_nick_name`。
- 部门名解析：`GET /manage_api/department/get_dept_info_by_dept_name`。
- ID 与名字同时存在时以 ID 为准；解析失败不得调用工时接口。
- 成功 stdout 打印 JSON；失败 stdout 打印含 `error` 的 JSON 且 exit code != 0。
- 首版只实现 `get_work_hours`；结构须便于后续在 OPERATIONS 增项。
- 不修改 `e:\51PM` 与 `e:\AI-Skill-Platform`。
- 提交信息用英文 conventional commits；不 push，除非用户明确要求。

---

## File Structure

| 文件 | 职责 |
|------|------|
| `scripts/api_client.py` | 配置读取、HTTP、名字解析、OPERATIONS、CLI |
| `scripts/package_skill.py` | 校验 Skill 结构并打成 `.skill`（zip） |
| `SKILL.md` | Aily 触发 description + 编排 + 分析框架 |
| `references/api_docs.md` | 真实接口文档 |
| `.env.example` | 环境变量模板 |
| `.gitignore` | 忽略 `.env`、`__pycache__`、`output/`、`.venv/` |
| `README.md` | 本地运行与部署说明 |
| `requirements-dev.txt` | 仅开发依赖：`pytest` |
| `tests/test_api_client.py` | 单元测试（mock HTTP） |
| `tests/conftest.py` | 公共 fixture |

---

### Task 1: 仓库脚手架与测试骨架

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `requirements-dev.txt`
- Create: `tests/conftest.py`
- Create: `tests/test_api_client.py`（先放一个占位失败测试指向尚未存在的模块）
- Create: `README.md`（最小说明，后续任务可补全）

**Interfaces:**
- Consumes: 无
- Produces: 可运行的 pytest 环境；约定包内以 `scripts/` 为脚本目录

- [ ] **Step 1: 写入脚手架文件**

`.gitignore`:

```gitignore
.env
.venv/
__pycache__/
*.pyc
.pytest_cache/
output/
*.skill
```

`.env.example`:

```bash
PM_PLATFORM_BASE_URL=https://pm.example.com
PM_PLATFORM_AUTH_TYPE=api_key
PM_PLATFORM_API_KEY=your_bearer_token_here
```

`requirements-dev.txt`:

```text
pytest>=8.0.0
```

`tests/conftest.py`:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
```

`README.md`（最小）:

```markdown
# pm-platform-api

Aily Skill：对接 51PM 项目管理平台工时 API，用于工作总结生成。

## 快速开始

```bash
pip install -r requirements-dev.txt
export PM_PLATFORM_BASE_URL=...
export PM_PLATFORM_AUTH_TYPE=api_key
export PM_PLATFORM_API_KEY=...
python scripts/api_client.py --list-ops
```
```

- [ ] **Step 2: 写失败测试（模块尚未存在）**

`tests/test_api_client.py`:

```python
def test_load_config_requires_api_key(monkeypatch):
    monkeypatch.delenv("PM_PLATFORM_API_KEY", raising=False)
    monkeypatch.setenv("PM_PLATFORM_BASE_URL", "https://pm.example.com")
    monkeypatch.setenv("PM_PLATFORM_AUTH_TYPE", "api_key")
    import api_client

    try:
        api_client.load_config()
        assert False, "expected ConfigError"
    except api_client.ConfigError as e:
        assert "PM_PLATFORM_API_KEY" in str(e)
```

- [ ] **Step 3: 安装 pytest 并确认测试失败**

Run:

```bash
cd /e/AIly-skill-platform
pip install -r requirements-dev.txt
pytest tests/test_api_client.py::test_load_config_requires_api_key -v
```

Expected: FAIL（`ModuleNotFoundError: api_client` 或类似）

- [ ] **Step 4: Commit**

```bash
git add .gitignore .env.example requirements-dev.txt tests/conftest.py tests/test_api_client.py README.md
git commit -m "chore: scaffold skill repo and test harness"
```

---

### Task 2: 配置加载与统一错误 JSON

**Files:**
- Create: `scripts/api_client.py`
- Modify: `tests/test_api_client.py`

**Interfaces:**
- Consumes: 环境变量 `PM_PLATFORM_*`
- Produces:
  - `class ConfigError(Exception)`
  - `class ClientError(Exception)` — 带 `error` / `detail` / 可选 `status`
  - `def load_config() -> dict` — keys: `base_url`, `auth_type`, `api_key`
  - `def error_payload(error: str, detail: str, status: int | None = None) -> dict`
  - `def emit_error_and_exit(error: str, detail: str, status: int | None = None) -> None` — print JSON + `sys.exit(1)`

- [ ] **Step 1: 扩展测试**

追加到 `tests/test_api_client.py`:

```python
def test_load_config_ok(monkeypatch):
    monkeypatch.setenv("PM_PLATFORM_BASE_URL", "https://pm.example.com/")
    monkeypatch.setenv("PM_PLATFORM_AUTH_TYPE", "api_key")
    monkeypatch.setenv("PM_PLATFORM_API_KEY", "tok")
    import api_client

    cfg = api_client.load_config()
    assert cfg["base_url"] == "https://pm.example.com"
    assert cfg["api_key"] == "tok"
    assert cfg["auth_type"] == "api_key"


def test_error_payload_includes_status():
    import api_client

    p = api_client.error_payload("http_error", "denied", status=401)
    assert p == {"error": "http_error", "detail": "denied", "status": 401}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_api_client.py -v`  
Expected: FAIL（缺 `api_client` 或缺符号）

- [ ] **Step 3: 实现最小 `scripts/api_client.py`**

```python
#!/usr/bin/env python3
"""51PM platform API client for Aily Skill."""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
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


def load_config() -> dict[str, str]:
    base_url = os.environ.get("PM_PLATFORM_BASE_URL", "").rstrip("/")
    auth_type = os.environ.get("PM_PLATFORM_AUTH_TYPE", "").strip()
    api_key = os.environ.get("PM_PLATFORM_API_KEY", "").strip()
    if not base_url:
        raise ConfigError("PM_PLATFORM_BASE_URL missing")
    if not api_key:
        raise ConfigError("PM_PLATFORM_API_KEY missing")
    if auth_type and auth_type != "api_key":
        raise ConfigError("PM_PLATFORM_AUTH_TYPE must be api_key")
    return {
        "base_url": base_url,
        "auth_type": auth_type or "api_key",
        "api_key": api_key,
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_api_client.py -v`  
Expected: PASS（本 Task 相关用例）

- [ ] **Step 5: Commit**

```bash
git add scripts/api_client.py tests/test_api_client.py
git commit -m "feat: add config loading and error payload helpers"
```

---

### Task 3: HTTP 请求层

**Files:**
- Modify: `scripts/api_client.py`
- Modify: `tests/test_api_client.py`

**Interfaces:**
- Consumes: `load_config()`
- Produces:
  - `def api_request(method: str, path: str, params: dict[str, Any] | None = None, timeout: float = 30.0) -> Any`
  - 行为：拼 `base_url + path`，GET 时 querystring；Header `Authorization: Bearer {api_key}`、`Accept: application/json`
  - HTTPError → 抛 `ClientError("http_error", body_or_reason, status=code)`
  - URLError/超时 → 抛 `ClientError("request_failed", str(e))`
  - 响应非 JSON → 抛 `ClientError("request_failed", "invalid json response")`

- [ ] **Step 1: 写失败测试（mock urlopen）**

```python
from unittest.mock import MagicMock, patch
import json


def test_api_request_get_success(monkeypatch):
    monkeypatch.setenv("PM_PLATFORM_BASE_URL", "https://pm.example.com")
    monkeypatch.setenv("PM_PLATFORM_AUTH_TYPE", "api_key")
    monkeypatch.setenv("PM_PLATFORM_API_KEY", "tok")
    import api_client

    body = json.dumps({"data": [{"id": 1}]}).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    with patch("api_client.urlopen", return_value=mock_resp) as m:
        result = api_client.api_request("GET", "/manage_api/user/get_user_info", {"id": 1})
        assert result == {"data": [{"id": 1}]}
        req = m.call_args[0][0]
        assert req.get_method() == "GET"
        assert "Authorization" in req.headers
        assert req.headers["Authorization"] == "Bearer tok"
        assert "id=1" in req.full_url


def test_api_request_http_error(monkeypatch):
    monkeypatch.setenv("PM_PLATFORM_BASE_URL", "https://pm.example.com")
    monkeypatch.setenv("PM_PLATFORM_AUTH_TYPE", "api_key")
    monkeypatch.setenv("PM_PLATFORM_API_KEY", "tok")
    import api_client
    from urllib.error import HTTPError

    err = HTTPError("https://pm.example.com/x", 401, "Unauthorized", hdrs=None, fp=None)
    with patch("api_client.urlopen", side_effect=err):
        try:
            api_client.api_request("GET", "/x")
            assert False
        except api_client.ClientError as e:
            assert e.error == "http_error"
            assert e.status == 401
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_api_client.py::test_api_request_get_success tests/test_api_client.py::test_api_request_http_error -v`  
Expected: FAIL（`api_request` 不存在）

- [ ] **Step 3: 实现 `api_request`**

追加到 `scripts/api_client.py`:

```python
def api_request(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> Any:
    cfg = load_config()
    # path must start with /
    clean_params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
    url = cfg["base_url"] + path
    if clean_params and method.upper() == "GET":
        url = url + "?" + urlencode(clean_params, doseq=True)
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Accept": "application/json",
    }
    data = None
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
        raise ClientError("request_failed", str(e.reason if hasattr(e, "reason") else e)) from e
    except TimeoutError as e:
        raise ClientError("request_failed", "timeout") from e
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError as e:
        raise ClientError("request_failed", "invalid json response") from e
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_api_client.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/api_client.py tests/test_api_client.py
git commit -m "feat: add authenticated HTTP request helper"
```

---

### Task 4: 人名/部门名解析

**Files:**
- Modify: `scripts/api_client.py`
- Modify: `tests/test_api_client.py`

**Interfaces:**
- Consumes: `api_request`
- Produces:
  - `def resolve_user_id(user_name: str) -> str` — 调 `/manage_api/user/get_user_info_by_nick_name`，从返回 `data.id`（或平台实际字段）取 ID；失败抛 `ClientError("resolve_failed", ...)`
  - `def resolve_dept_id(dept_name: str) -> int` — 调 `/manage_api/department/get_dept_info_by_dept_name`，从 `data.id` 取 ID
  - `def apply_name_resolution(params: dict[str, Any]) -> dict[str, Any]` — 输入可含 `user_name`/`dept_name`/`user_id`/`dept_id`；输出供工时接口使用的参数（去掉 name 键，填入 id）；ID 优先

**平台字段约定（实现时按此取，若结构不同在测试里固定 mock）：**

- 用户：响应 `{"data": {"id": 123, "nick_name": "张三", ...}}`
- 部门：响应 `{"data": {"id": 10, "title": "研发部", ...}}`

- [ ] **Step 1: 写测试**

```python
def test_apply_name_resolution_user_name(monkeypatch):
    monkeypatch.setenv("PM_PLATFORM_BASE_URL", "https://pm.example.com")
    monkeypatch.setenv("PM_PLATFORM_AUTH_TYPE", "api_key")
    monkeypatch.setenv("PM_PLATFORM_API_KEY", "tok")
    import api_client

    def fake_request(method, path, params=None, timeout=30.0):
        assert path == "/manage_api/user/get_user_info_by_nick_name"
        assert params["nick_name"] == "张三"
        return {"data": {"id": 42, "nick_name": "张三"}}

    monkeypatch.setattr(api_client, "api_request", fake_request)
    out = api_client.apply_name_resolution({"user_name": "张三", "start_date": "2026-08-01"})
    assert out["user_id"] == "42" or out["user_id"] == 42
    assert "user_name" not in out
    assert out["start_date"] == "2026-08-01"


def test_apply_name_resolution_id_wins(monkeypatch):
    monkeypatch.setenv("PM_PLATFORM_BASE_URL", "https://pm.example.com")
    monkeypatch.setenv("PM_PLATFORM_AUTH_TYPE", "api_key")
    monkeypatch.setenv("PM_PLATFORM_API_KEY", "tok")
    import api_client

    called = {"n": 0}

    def fake_request(*args, **kwargs):
        called["n"] += 1
        return {"data": {"id": 99}}

    monkeypatch.setattr(api_client, "api_request", fake_request)
    out = api_client.apply_name_resolution({"user_id": "7", "user_name": "张三"})
    assert str(out["user_id"]) == "7"
    assert called["n"] == 0


def test_resolve_user_not_found(monkeypatch):
    monkeypatch.setenv("PM_PLATFORM_BASE_URL", "https://pm.example.com")
    monkeypatch.setenv("PM_PLATFORM_AUTH_TYPE", "api_key")
    monkeypatch.setenv("PM_PLATFORM_API_KEY", "tok")
    import api_client

    monkeypatch.setattr(api_client, "api_request", lambda *a, **k: {"data": None})
    try:
        api_client.resolve_user_id("不存在")
        assert False
    except api_client.ClientError as e:
        assert e.error == "resolve_failed"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_api_client.py -k resolution -v` 与 `pytest tests/test_api_client.py::test_resolve_user_not_found -v`  
Expected: FAIL

- [ ] **Step 3: 实现解析函数**

```python
def _extract_id(payload: Any, label: str) -> Any:
    data = payload.get("data") if isinstance(payload, dict) else None
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
        "/manage_api/department/get_dept_info_by_dept_name",
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
```

- [ ] **Step 4: 运行全量单测**

Run: `pytest tests/test_api_client.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/api_client.py tests/test_api_client.py
git commit -m "feat: auto-resolve user and department names to ids"
```

---

### Task 5: OPERATIONS 注册表 + `get_work_hours` + CLI

**Files:**
- Modify: `scripts/api_client.py`
- Modify: `tests/test_api_client.py`

**Interfaces:**
- Consumes: `api_request`, `apply_name_resolution`, `error_payload`
- Produces:
  - `OPERATIONS: dict[str, dict]` — 至少含 `get_work_hours`
  - `def run_operation(name: str, params: dict[str, Any]) -> Any`
  - `def list_operations() -> list[dict]`
  - `def main(argv: list[str] | None = None) -> int` — argparse：`--list-ops`；`op --param k v` 可重复；成功 print JSON return 0；捕获 `ConfigError`/`ClientError` print error JSON return 1

`get_work_hours` 定义：

```python
OPERATIONS = {
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
            "page_size",
        ],
        "required": ["start_date", "end_date"],
        "resolve_names": True,
    },
}
```

`run_operation` 逻辑：
1. 未知 op → `ClientError("unknown_operation", name)`
2. 校验 required
3. 若 `resolve_names`：`params = apply_name_resolution(params)`
4. 只把平台认识的 query 传给 `api_request`（`start_date,end_date,user_id,dept_id,page,page_size`），默认 `page=1`、`page_size=500`
5. 返回响应

- [ ] **Step 1: 写测试**

```python
def test_run_get_work_hours_resolves_and_calls(monkeypatch):
    monkeypatch.setenv("PM_PLATFORM_BASE_URL", "https://pm.example.com")
    monkeypatch.setenv("PM_PLATFORM_AUTH_TYPE", "api_key")
    monkeypatch.setenv("PM_PLATFORM_API_KEY", "tok")
    import api_client

    calls = []

    def fake_request(method, path, params=None, timeout=30.0):
        calls.append((method, path, params))
        if "get_user_info_by_nick_name" in path:
            return {"data": {"id": 5}}
        return {"data": [{"task_name": "开发", "consumed": 2}]}

    monkeypatch.setattr(api_client, "api_request", fake_request)
    result = api_client.run_operation(
        "get_work_hours",
        {
            "start_date": "2026-08-01",
            "end_date": "2026-08-06",
            "user_name": "张三",
        },
    )
    assert result["data"][0]["consumed"] == 2
    assert any("get_daily_estimate_list" in c[1] for c in calls)
    final = [c for c in calls if "get_daily_estimate_list" in c[1]][0]
    assert str(final[2]["user_id"]) == "5"
    assert "user_name" not in final[2]


def test_list_ops_contains_get_work_hours():
    import api_client

    names = [o["name"] for o in api_client.list_operations()]
    assert "get_work_hours" in names


def test_main_list_ops(capsys, monkeypatch):
    monkeypatch.setenv("PM_PLATFORM_BASE_URL", "https://pm.example.com")
    monkeypatch.setenv("PM_PLATFORM_AUTH_TYPE", "api_key")
    monkeypatch.setenv("PM_PLATFORM_API_KEY", "tok")
    import api_client

    code = api_client.main(["--list-ops"])
    assert code == 0
    out = capsys.readouterr().out
    assert "get_work_hours" in out


def test_main_missing_required(capsys, monkeypatch):
    monkeypatch.setenv("PM_PLATFORM_BASE_URL", "https://pm.example.com")
    monkeypatch.setenv("PM_PLATFORM_AUTH_TYPE", "api_key")
    monkeypatch.setenv("PM_PLATFORM_API_KEY", "tok")
    import api_client

    code = api_client.main(["get_work_hours", "--param", "start_date", "2026-08-01"])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] in ("validation_error", "request_failed", "unknown_operation") or "end_date" in payload["detail"]
```

校验缺参时建议使用 `ClientError("validation_error", "missing required param: end_date")`。

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_api_client.py -k "work_hours or list_ops or main_" -v`  
Expected: FAIL

- [ ] **Step 3: 实现 OPERATIONS / run_operation / CLI**

在 `api_client.py` 追加完整实现（要点）：

```python
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
            "page_size",
        ],
        "required": ["start_date", "end_date"],
        "resolve_names": True,
        "upstream_params": [
            "start_date",
            "end_date",
            "user_id",
            "dept_id",
            "page",
            "page_size",
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
    if "page_size" not in resolved or resolved["page_size"] in (None, ""):
        resolved["page_size"] = 500
    query = {k: resolved[k] for k in meta["upstream_params"] if k in resolved and resolved[k] not in (None, "")}
    return api_request(meta["method"], meta["path"], query)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="51PM API client for Aily Skill")
    parser.add_argument("operation", nargs="?", help="operation name")
    parser.add_argument("--list-ops", action="store_true")
    parser.add_argument("--param", nargs=2, action="append", default=[], metavar=("KEY", "VALUE"))
    args = parser.parse_args(argv)
    try:
        if args.list_ops:
            print(json.dumps(list_operations(), ensure_ascii=False, indent=2))
            return 0
        if not args.operation:
            raise ClientError("validation_error", "operation name required (or use --list-ops)")
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
```

- [ ] **Step 4: 运行全量单测**

Run: `pytest tests/ -v`  
Expected: PASS

- [ ] **Step 5: 手工烟雾（无真实 Token 时可跳过，在 README 标注）**

```bash
python scripts/api_client.py --list-ops
```

Expected: JSON 含 `get_work_hours`

- [ ] **Step 6: Commit**

```bash
git add scripts/api_client.py tests/test_api_client.py
git commit -m "feat: add get_work_hours operation and CLI"
```

---

### Task 6: SKILL.md + api_docs.md

**Files:**
- Create: `SKILL.md`
- Create: `references/api_docs.md`
- Modify: `README.md`（补部署与场景说明）

**Interfaces:**
- Consumes: Task 5 CLI 行为
- Produces: Aily 可读说明书与接口参考

- [ ] **Step 1: 写 `SKILL.md`**

内容必须包含：

1. YAML frontmatter（`name: pm-platform-api`，description 覆盖工时/工作总结关键词，见设计文档）
2. 意图→操作映射表（工作总结、查工时）
3. 编排步骤（抽日期/人名/部门名；优先 name；示例 CLI）
4. 错误处理（见 `error` 字段）
5. 工作总结输出结构（概览 / 按项目 / 按日期 / 风险）

- [ ] **Step 2: 写 `references/api_docs.md`**

文档化：

- `get_work_hours` 对应上游路径与参数
- 内部解析接口路径与查询参数
- 响应关键字段列表（`date,task_name,consumed,user_name,name,sj_num,remark,task_process,confirm_status,dept_name`）
- 错误 JSON 形状

- [ ] **Step 3: 更新 README**

补充：环境变量表、CLI 示例（含 `user_name`）、打包与上传步骤摘要、扩展 OPERATIONS 的三处同步更新说明。

- [ ] **Step 4: Commit**

```bash
git add SKILL.md references/api_docs.md README.md
git commit -m "docs: add SKILL.md and API reference for work hours"
```

---

### Task 7: package_skill.py

**Files:**
- Create: `scripts/package_skill.py`
- Create: `tests/test_package_skill.py`

**Interfaces:**
- Consumes: Skill 根目录文件
- Produces: `def package_skill(src_dir: Path, out_dir: Path) -> Path` — 校验后写出 `{name}.skill`（zip）；校验：存在 `SKILL.md`、含 `name:` frontmatter、存在 `scripts/api_client.py`

- [ ] **Step 1: 写测试**

```python
from pathlib import Path
import zipfile


def test_package_skill_creates_archive(tmp_path, monkeypatch):
    import sys
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    import package_skill

    src = tmp_path / "skill"
    (src / "scripts").mkdir(parents=True)
    (src / "references").mkdir()
    (src / "SKILL.md").write_text(
        "---\nname: pm-platform-api\nlabel: test\ndescription: d\n---\n\nbody\n",
        encoding="utf-8",
    )
    (src / "scripts" / "api_client.py").write_text("# x\n", encoding="utf-8")
    (src / "references" / "api_docs.md").write_text("# docs\n", encoding="utf-8")
    out = tmp_path / "out"
    path = package_skill.package_skill(src, out)
    assert path.exists()
    assert path.suffix == ".skill"
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        assert any(n.endswith("SKILL.md") for n in names)
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_package_skill.py -v`  
Expected: FAIL

- [ ] **Step 3: 实现 `scripts/package_skill.py`**

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path


def _read_skill_name(skill_md: Path) -> str:
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        raise ValueError("SKILL.md missing YAML frontmatter")
    name_m = re.search(r"^name:\s*[\"']?([^\"'\n]+)[\"']?\s*$", m.group(1), re.M)
    if not name_m:
        raise ValueError("SKILL.md frontmatter missing name")
    return name_m.group(1).strip()


def package_skill(src_dir: Path, out_dir: Path) -> Path:
    src_dir = src_dir.resolve()
    skill_md = src_dir / "SKILL.md"
    client = src_dir / "scripts" / "api_client.py"
    if not skill_md.is_file():
        raise FileNotFoundError("SKILL.md not found")
    if not client.is_file():
        raise FileNotFoundError("scripts/api_client.py not found")
    name = _read_skill_name(skill_md)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{name}.skill"
    include_dirs = ["scripts", "references"]
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(skill_md, arcname="SKILL.md")
        for d in include_dirs:
            base = src_dir / d
            if not base.exists():
                continue
            for path in base.rglob("*"):
                if path.is_file():
                    zf.write(path, arcname=str(path.relative_to(src_dir)).replace("\\", "/"))
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("src_dir")
    parser.add_argument("out_dir")
    args = parser.parse_args(argv)
    try:
        path = package_skill(Path(args.src_dir), Path(args.out_dir))
        print(path)
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 运行测试并手工打包**

```bash
pytest tests/ -v
python scripts/package_skill.py . ./output
```

Expected: `output/pm-platform-api.skill` 存在；全量测试 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/package_skill.py tests/test_package_skill.py
git commit -m "feat: add skill packaging script"
```

---

### Task 8: 端到端核对与 README 收尾

**Files:**
- Modify: `README.md`（若需）
- Verify: 设计文档要求全部落地

- [ ] **Step 1: 对照设计文档逐项核对**

核对清单：

- [ ] OPERATIONS 仅对外 `get_work_hours`（解析为内部）
- [ ] 环境变量三件套
- [ ] 错误码：`config_error` / `resolve_failed` / `http_error` / `request_failed` / `unknown_operation`（及 `validation_error`）
- [ ] SKILL description 覆盖工时/总结
- [ ] 打包脚本可用
- [ ] `.env` 被 gitignore

- [ ] **Step 2: 全量测试**

```bash
pytest tests/ -v
python scripts/api_client.py --list-ops
python scripts/package_skill.py . ./output
```

Expected: 全部成功

- [ ] **Step 3: 最终 commit（若有文档修正）**

```bash
git add -A
git status
git commit -m "docs: finalize README and verify skill deliverables"
```

（无变更则跳过 commit）

---

## Self-Review

1. **Spec coverage:** 架构/认证/get_work_hours/名字解析/SKILL/api_docs/错误处理/打包/扩展约定均有对应 Task。
2. **Placeholder scan:** 无 TBD；测试与实现代码均已写出。
3. **Type consistency:** `ClientError(error, detail, status)`、`apply_name_resolution`、`run_operation`、`main` 在各 Task 一致；工时上游参数键名与设计一致。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-06-aily-pm-platform-skill.md`.

**Two execution options:**

1. **Subagent-Driven（推荐）** — 每个 Task 派一个新 subagent，Task 间做审查，迭代快  
2. **Inline Execution** — 本会话按 executing-plans 逐项执行，带检查点

选哪种？
