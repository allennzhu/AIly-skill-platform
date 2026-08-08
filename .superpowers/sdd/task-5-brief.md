### Task 5: Skill — list_doing_tasks + submit_estimate

**Files:**
- Modify: `pm-fill-hours/scripts/api_client.py`
- Modify: `pm-fill-hours/tests/test_api_client.py`

**Interfaces:**
- Produces:
  - `list_doing_tasks(user_token: str, task_kind: str | None) -> list[dict]`
    - 每项：`task_id`,`name`,`project_name`,`task_kind`（`project`|`not_project`）
  - `submit_estimate(user_token, task_kind, task_id, date, consumed, remark) -> Any`

路径：
- 项目列表：`GET /manage_api/main_panel/get_task_list` params `status=doing`（数组按平台习惯传，如重复 key 或 JSON；实现时与前端一致，必要时 `status[]=doing`）
- 非项目：`GET /manage_api/main_panel/get_not_task_list`
- 提交项目：`POST /manage_api/project_task_estimate/add`
- 提交非项目：`POST /manage_api/project_not_task_estimate/add`

- [ ] **Step 1: 单测 list 合并与 submit 路由**

```python
def test_list_doing_tasks_merges(monkeypatch):
    import api_client
    calls = []
    def fake(method, path, params=None, token=None, json_body=None):
        calls.append(path)
        if "get_not_task_list" in path:
            return {"code": 0, "data": {"data": [{"id": 2, "name": "会议", "project_name": ""}]}}
        return {"code": 0, "data": {"data": [{"id": 1, "name": "开发", "project_name": "51PM"}]}}
    monkeypatch.setattr(api_client, "api_request", fake)
    opts = api_client.list_doing_tasks("u", None)
    assert {o["task_kind"] for o in opts} == {"project", "not_project"}
    assert len(opts) == 2
```

- [ ] **Step 2: 实现 list + submit**

- [ ] **Step 3: pytest 通过**

- [ ] **Step 4: Commit**

```bash
git commit -am "feat: list doing tasks and submit project/not-project estimates"
```

---
