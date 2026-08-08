# Task 5 Report: list_doing_tasks + submit_estimate

## Status

**COMPLETE** — all 14 tests pass; implementation committed on `feature/pm-platform-api-skill`.

## TDD Evidence

### RED (pre-implementation)

Three tests failed with `AttributeError`:

```
tests/test_api_client.py::test_list_doing_tasks_merges FAILED
  AttributeError: module 'api_client' has no attribute 'list_doing_tasks'

tests/test_api_client.py::test_list_doing_tasks_filters_by_kind FAILED
  AttributeError: module 'api_client' has no attribute 'list_doing_tasks'

tests/test_api_client.py::test_submit_estimate_routes_by_task_kind FAILED
  AttributeError: module 'api_client' has no attribute 'submit_estimate'
```

(11 existing tests passed.)

### GREEN (post-implementation)

```
pytest pm-fill-hours/tests -v
============================= 14 passed in 0.03s ==============================
```

## Implementation Summary

### `list_doing_tasks(user_token, task_kind)`

- `task_kind=None`: merges project + not-project lists (project first).
- `task_kind="project"`: `GET /manage_api/main_panel/get_task_list`.
- `task_kind="not_project"`: `GET /manage_api/main_panel/get_not_task_list`.
- Params: `{"status": ["doing"]}`, auth via `token=user_token`.
- Unwraps GoFrame `{code, data: {data: [...]}}` via `_unwrap_data`.
- Normalizes each item to `{task_id, name, project_name, task_kind}`.

### `submit_estimate(user_token, task_kind, task_id, date, consumed, remark)`

- `project` → `POST /manage_api/project_task_estimate/add`
- `not_project` → `POST /manage_api/project_not_task_estimate/add`
- JSON body: `{task_id, date, consumed, remark}`

## Commit

```
feat: list doing tasks and submit project/not-project estimates
```

Files: `pm-fill-hours/scripts/api_client.py`, `pm-fill-hours/tests/test_api_client.py`

## Concerns

- No live API integration test; behavior validated via monkeypatched unit tests only.
- Unknown `task_kind` on submit raises `ClientError` — not covered by tests but defensive.
- List order when merging: project tasks before not-project tasks (matches test expectations).
