import json
from unittest.mock import MagicMock, patch


def test_load_config_requires_api_key(monkeypatch):
    monkeypatch.delenv("PM_PLATFORM_API_KEY", raising=False)
    monkeypatch.delenv("PM_PLATFORM_BASE_URL", raising=False)
    import api_client

    monkeypatch.setattr(api_client, "_load_file_config", lambda: {})
    try:
        api_client.load_config()
        assert False
    except api_client.ConfigError as e:
        assert "API_KEY" in str(e) or "missing" in str(e).lower()


def test_api_request_default_super_token(monkeypatch):
    monkeypatch.setenv("PM_PLATFORM_BASE_URL", "https://pm.example.com")
    monkeypatch.setenv("PM_PLATFORM_API_KEY", "super")
    import api_client

    body = json.dumps({"code": 0, "data": {"ok": 1}}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    with patch("api_client.urlopen", return_value=mock_resp) as m:
        api_client.api_request("GET", "/x")
        req = m.call_args[0][0]
        assert req.get_header("Authorization") == "Bearer super"


def test_load_config_env_overrides_file(monkeypatch):
    monkeypatch.setenv("PM_PLATFORM_BASE_URL", "https://env.example.com")
    monkeypatch.setenv("PM_PLATFORM_API_KEY", "env-key")
    import api_client

    monkeypatch.setattr(
        api_client,
        "_load_file_config",
        lambda: {
            "base_url": "https://file.example.com",
            "api_key": "file-key",
            "auth_type": "",
        },
    )
    cfg = api_client.load_config()
    assert cfg["base_url"] == "https://env.example.com"
    assert cfg["api_key"] == "env-key"


def test_api_request_uses_override_token(monkeypatch):
    monkeypatch.setenv("PM_PLATFORM_BASE_URL", "https://pm.example.com")
    monkeypatch.setenv("PM_PLATFORM_API_KEY", "super")
    import api_client

    body = json.dumps({"code": 0, "data": {"ok": 1}}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    with patch("api_client.urlopen", return_value=mock_resp) as m:
        api_client.api_request("GET", "/x", token="user-tok")
        req = m.call_args[0][0]
        assert req.get_header("Authorization") == "Bearer user-tok"


def test_api_request_post_json_body(monkeypatch):
    monkeypatch.setenv("PM_PLATFORM_BASE_URL", "https://pm.example.com")
    monkeypatch.setenv("PM_PLATFORM_API_KEY", "super")
    import api_client

    body = json.dumps({"code": 0, "data": {"token": "abc"}}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    with patch("api_client.urlopen", return_value=mock_resp) as m:
        api_client.api_request(
            "POST",
            "/manage_api/user/impersonate_user",
            json_body={"target_user_id": 42},
        )
        req = m.call_args[0][0]
        assert req.get_method() == "POST"
        assert req.get_header("Content-type") == "application/json"
        assert json.loads(req.data.decode()) == {"target_user_id": 42}


def test_unwrap_data_extracts_goframe_envelope():
    import api_client

    assert api_client._unwrap_data({"code": 0, "data": {"user_id": 1}}) == {"user_id": 1}
    assert api_client._unwrap_data({"user_id": 1}) == {"user_id": 1}


def test_extract_access_token_from_token_info():
    import api_client

    payload = {"code": 0, "data": {"token_info": {"access_token": "u-token"}}}
    assert api_client._extract_access_token(payload) == "u-token"


def test_resolve_feishu_user(monkeypatch):
    import api_client

    def fake(method, path, params=None, token=None, json_body=None):
        assert method == "GET"
        assert path == "/manage_api/qiye_user/get_user_by_feishu_union_id"
        assert params == {"feishu_union_id": "on_1"}
        return {"code": 0, "data": {"user_id": 474, "nick_name": "朱晓辉"}}

    monkeypatch.setattr(api_client, "api_request", fake)
    user = api_client.resolve_feishu_user("on_1")
    assert user["user_id"] == 474
    assert user["nick_name"] == "朱晓辉"


def test_impersonate(monkeypatch):
    import api_client

    def fake(method, path, params=None, token=None, json_body=None):
        assert method == "POST"
        assert path == "/manage_api/user/impersonate_user"
        assert json_body == {"target_user_id": 474}
        return {"code": 0, "data": {"token_info": {"access_token": "u-token"}}}

    monkeypatch.setattr(api_client, "api_request", fake)
    assert api_client.impersonate(474) == "u-token"


def test_session_user_token(monkeypatch):
    import api_client

    def fake(method, path, params=None, token=None, json_body=None):
        if "get_user_by_feishu_union_id" in path:
            return {"code": 0, "data": {"user_id": 474, "nick_name": "朱晓辉"}}
        if "impersonate_user" in path:
            return {"code": 0, "data": {"token_info": {"access_token": "u-token"}}}
        raise AssertionError(path)

    monkeypatch.setattr(api_client, "api_request", fake)
    user, tok = api_client.session_user_token("on_1")
    assert user["user_id"] == 474
    assert tok == "u-token"


def test_list_doing_tasks_merges(monkeypatch):
    import api_client

    calls = []

    def fake(method, path, params=None, token=None, json_body=None):
        calls.append(path)
        if "get_not_task_list" in path:
            return {
                "code": 0,
                "data": {
                    "data": [{"id": 2, "name": "会议", "project_name": ""}],
                },
            }
        return {
            "code": 0,
            "data": {"data": [{"id": 1, "name": "开发", "project_name": "51PM"}]},
        }

    monkeypatch.setattr(api_client, "api_request", fake)
    opts = api_client.list_doing_tasks("u", None)
    assert {o["task_kind"] for o in opts} == {"project", "not_project"}
    assert len(opts) == 2
    assert opts[0]["task_id"] == 1
    assert opts[0]["name"] == "开发"
    assert opts[0]["project_name"] == "51PM"
    assert opts[1]["task_id"] == 2
    assert opts[1]["name"] == "会议"
    assert "/manage_api/main_panel/get_task_list" in calls
    assert "/manage_api/main_panel/get_not_task_list" in calls


def test_list_doing_tasks_filters_by_kind(monkeypatch):
    import api_client

    def fake(method, path, params=None, token=None, json_body=None):
        assert params == {"status": ["doing"]}
        assert token == "u"
        return {"code": 0, "data": {"data": [{"id": 1, "name": "开发", "project_name": "51PM"}]}}

    monkeypatch.setattr(api_client, "api_request", fake)
    opts = api_client.list_doing_tasks("u", "project")
    assert len(opts) == 1
    assert opts[0]["task_kind"] == "project"


def test_submit_estimate_routes_by_task_kind(monkeypatch):
    import api_client

    calls = []

    def fake(method, path, params=None, token=None, json_body=None):
        calls.append((method, path, token, json_body))
        return {"code": 0, "data": {}}

    monkeypatch.setattr(api_client, "api_request", fake)
    api_client.submit_estimate("tok", "project", 1, "2026-08-07", 2.0, "done")
    api_client.submit_estimate("tok", "not_project", 2, "2026-08-07", 1.0, "meeting")
    assert calls[0] == (
        "POST",
        "/manage_api/project_task_estimate/add",
        "tok",
        {"task_id": 1, "date": "2026-08-07", "consumed": 2.0, "remark": "done"},
    )
    assert calls[1] == (
        "POST",
        "/manage_api/project_not_task_estimate/add",
        "tok",
        {"task_id": 2, "date": "2026-08-07", "consumed": 1.0, "remark": "meeting"},
    )


def test_fill_hours_step_need_task(monkeypatch):
    import api_client

    monkeypatch.setattr(
        api_client,
        "session_user_token",
        lambda oid: ({"user_id": 1, "nick_name": "A"}, "tok"),
    )
    monkeypatch.setattr(
        api_client,
        "list_doing_tasks",
        lambda tok, kind=None: [
            {
                "task_id": 9,
                "name": "开发",
                "project_name": "P",
                "task_kind": "project",
            }
        ],
    )
    out = api_client.fill_hours_step(
        {"feishu_union_id": "on_x", "consumed": "2", "remark": "联调"}
    )
    assert out["status"] == "need_input"
    assert "task_id" in out["missing_fields"]
    assert out["task_options"][0]["task_id"] == 9


def test_fill_hours_step_submit(monkeypatch):
    import api_client

    monkeypatch.setattr(
        api_client,
        "session_user_token",
        lambda oid: ({"user_id": 1, "nick_name": "A"}, "tok"),
    )
    monkeypatch.setattr(
        api_client, "submit_estimate", lambda *a, **k: {"code": 0, "data": {}}
    )
    out = api_client.fill_hours_step(
        {
            "feishu_union_id": "on_x",
            "task_id": "9",
            "task_kind": "project",
            "date": "2026-08-07",
            "consumed": "2",
            "remark": "联调",
        }
    )
    assert out["status"] == "submitted"


def test_api_request_business_error(monkeypatch):
    monkeypatch.setenv("PM_PLATFORM_BASE_URL", "https://pm.example.com")
    monkeypatch.setenv("PM_PLATFORM_API_KEY", "super")
    import api_client

    body = json.dumps({"code": 1, "msg": "not allowed"}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    with patch("api_client.urlopen", return_value=mock_resp):
        try:
            api_client.api_request("GET", "/x")
            assert False
        except api_client.ClientError as e:
            assert e.error == "business_error"
            assert e.detail == "not allowed"
