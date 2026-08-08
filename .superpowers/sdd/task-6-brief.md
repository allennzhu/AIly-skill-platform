### Task 6: Skill — fill_hours_step + CLI

**Files:**
- Modify: `pm-fill-hours/scripts/api_client.py`
- Modify: `pm-fill-hours/tests/test_api_client.py`

**Interfaces:**
- Produces:
  - `fill_hours_step(params: dict) -> dict`（规格中的 JSON 形状）
  - `main(argv) -> int`：`--list-ops`；`fill_hours_step --param k v`

逻辑：
1. 校验 `feishu_open_id`
2. `session_user_token`
3. `date` 默认今天
4. 收集 `task_id/task_kind/date/consumed/remark`；缺则 `status=need_input`
5. 缺 `task_id`：拉 `task_options`，`next_question` 选任务
6. 齐：`submit_estimate`，`status=submitted`

- [ ] **Step 1: 测试缺任务返回 options**

```python
def test_fill_hours_step_need_task(monkeypatch):
    import api_client
    monkeypatch.setattr(api_client, "session_user_token", lambda oid: ({"user_id": 1, "nick_name": "A"}, "tok"))
    monkeypatch.setattr(
        api_client,
        "list_doing_tasks",
        lambda tok, kind=None: [{"task_id": 9, "name": "开发", "project_name": "P", "task_kind": "project"}],
    )
    out = api_client.fill_hours_step({"feishu_open_id": "ou_x", "consumed": "2", "remark": "联调"})
    assert out["status"] == "need_input"
    assert "task_id" in out["missing_fields"]
    assert out["task_options"][0]["task_id"] == 9
```

- [ ] **Step 2: 测试齐参提交**

```python
def test_fill_hours_step_submit(monkeypatch):
    import api_client
    monkeypatch.setattr(api_client, "session_user_token", lambda oid: ({"user_id": 1, "nick_name": "A"}, "tok"))
    monkeypatch.setattr(api_client, "submit_estimate", lambda *a, **k: {"code": 0, "data": {}})
    out = api_client.fill_hours_step({
        "feishu_open_id": "ou_x",
        "task_id": "9",
        "task_kind": "project",
        "date": "2026-08-07",
        "consumed": "2",
        "remark": "联调",
    })
    assert out["status"] == "submitted"
```

- [ ] **Step 3: 实现 fill_hours_step + argparse main**

- [ ] **Step 4: 全量 pytest**

```bash
pytest pm-fill-hours/tests -v
```

- [ ] **Step 5: Commit**

```bash
git commit -am "feat: add fill_hours_step orchestration and CLI"
```

---
