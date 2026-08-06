import json
from unittest.mock import MagicMock, patch


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
        result = api_client.api_request(
            "GET", "/manage_api/user/get_user_info", {"id": 1}
        )
        assert result == {"data": [{"id": 1}]}
        req = m.call_args[0][0]
        assert req.get_method() == "GET"
        assert req.get_header("Authorization") == "Bearer tok"
        assert "id=1" in req.full_url


def test_api_request_http_error(monkeypatch):
    monkeypatch.setenv("PM_PLATFORM_BASE_URL", "https://pm.example.com")
    monkeypatch.setenv("PM_PLATFORM_AUTH_TYPE", "api_key")
    monkeypatch.setenv("PM_PLATFORM_API_KEY", "tok")
    import api_client
    from urllib.error import HTTPError

    err = HTTPError(
        "https://pm.example.com/x", 401, "Unauthorized", hdrs=None, fp=None
    )
    with patch("api_client.urlopen", side_effect=err):
        try:
            api_client.api_request("GET", "/x")
            assert False
        except api_client.ClientError as e:
            assert e.error == "http_error"
            assert e.status == 401


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
    out = api_client.apply_name_resolution(
        {"user_name": "张三", "start_date": "2026-08-01"}
    )
    assert str(out["user_id"]) == "42"
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

    code = api_client.main(
        ["get_work_hours", "--param", "start_date", "2026-08-01"]
    )
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "validation_error"
    assert "end_date" in payload["detail"]
