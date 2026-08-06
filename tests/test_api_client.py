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
