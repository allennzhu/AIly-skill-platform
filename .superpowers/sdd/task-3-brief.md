### Task 3: Skill — 配置、HTTP、超管请求

**Files:**
- Create: `pm-fill-hours/scripts/api_client.py`
- Modify: `pm-fill-hours/tests/test_api_client.py`

**Interfaces:**
- Produces:
  - `load_config() -> dict`
  - `api_request(method, path, params=None, token=None, json_body=None) -> Any`
  - 默认用超管 Token；`token=` 可覆盖为用户 Token
  - GoFrame 解包：`code != 0` → `ClientError("business_error", msg)`

可从根目录查工时 `scripts/api_client.py` 复制 HTTP/config 模式，但**独立文件**，避免互相耦合。

- [ ] **Step 1: 测试 `api_request` 带自定义 token**

```python
def test_api_request_uses_override_token(monkeypatch):
    monkeypatch.setenv("PM_PLATFORM_BASE_URL", "https://pm.example.com")
    monkeypatch.setenv("PM_PLATFORM_API_KEY", "super")
    import api_client
    from unittest.mock import MagicMock, patch
    import json
    body = json.dumps({"code": 0, "data": {"ok": 1}}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    with patch("api_client.urlopen", return_value=mock_resp) as m:
        api_client.api_request("GET", "/x", token="user-tok")
        req = m.call_args[0][0]
        assert req.get_header("Authorization") == "Bearer user-tok"
```

- [ ] **Step 2: 实现最小 config + api_request（含 POST JSON）**

- [ ] **Step 3: pytest 通过**

- [ ] **Step 4: Commit**

```bash
git commit -am "feat: add fill-hours HTTP client and config"
```

---
