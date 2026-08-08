### Task 2: Skill 脚手架

**Files:**
- Create: `e:\AIly-skill-platform\pm-fill-hours\scripts\config.example.json`
- Create: `e:\AIly-skill-platform\pm-fill-hours\tests\conftest.py`
- Create: `e:\AIly-skill-platform\pm-fill-hours\tests\test_api_client.py`
- Create: `e:\AIly-skill-platform\pm-fill-hours\README.md`
- Modify: `e:\AIly-skill-platform\.gitignore`（确保 `pm-fill-hours/scripts/config.json` 忽略）

**Interfaces:**
- Produces: 可运行的 pytest 路径；`sys.path` 含 `pm-fill-hours/scripts`

- [ ] **Step 1: 创建目录与示例配置**

`config.example.json`:

```json
{
  "base_url": "http://51pm.51aes.com:218",
  "auth_type": "api_key",
  "api_key": "SUPER_USER_BEARER_TOKEN"
}
```

`tests/conftest.py`:

```python
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
```

- [ ] **Step 2: 写失败测试占位**

```python
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
```

- [ ] **Step 3: pytest 确认失败**

```bash
cd /e/AIly-skill-platform
pytest pm-fill-hours/tests/test_api_client.py::test_load_config_requires_api_key -v
```

Expected: FAIL（无模块）

- [ ] **Step 4: Commit**

```bash
git add pm-fill-hours .gitignore
git commit -m "chore: scaffold pm-fill-hours skill"
```

---
