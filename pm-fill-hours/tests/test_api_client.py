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
