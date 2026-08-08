### Task 4: Skill — resolve + impersonate

**Files:**
- Modify: `pm-fill-hours/scripts/api_client.py`
- Modify: `pm-fill-hours/tests/test_api_client.py`

**Interfaces:**
- Produces:
  - `resolve_feishu_user(open_id: str) -> dict` → `{user_id, nick_name, ...}`
  - `impersonate(user_id: int) -> str` → 用户 access token 字符串
  - `session_user_token(open_id: str) -> tuple[dict, str]` → (user, token)

`resolve` 调：`GET /manage_api/qiye_user/get_user_by_feishu_open_id`  
`impersonate` 调：`POST /manage_api/user/impersonate_user` body `{"target_user_id": N}`  
Token 字段从返回 `data.token_info` / `token_info.access_token` 等按实际响应解析（实现时对真实响应做一次探测并固定路径；单测用 mock）。

- [ ] **Step 1: 写测试（mock api_request）**

```python
def test_session_user_token(monkeypatch):
    import api_client
    def fake(method, path, params=None, token=None, json_body=None):
        if "get_user_by_feishu_open_id" in path:
            return {"code": 0, "data": {"user_id": 474, "nick_name": "朱晓辉"}}
        if "impersonate_user" in path:
            return {"code": 0, "data": {"token_info": {"access_token": "u-token"}}}
        raise AssertionError(path)
    monkeypatch.setattr(api_client, "api_request", fake)
    # 若业务数据在 data 内，resolve 需解包
    user, tok = api_client.session_user_token("ou_1")
    assert user["user_id"] == 474
    assert tok == "u-token"
```

（按最终解包辅助函数调整断言。）

- [ ] **Step 2: 实现 resolve / impersonate / session_user_token**

- [ ] **Step 3: pytest 通过**

- [ ] **Step 4: Commit**

```bash
git commit -am "feat: resolve feishu user and impersonate for fill-hours"
```

---
