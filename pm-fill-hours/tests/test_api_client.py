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
