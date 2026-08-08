# pm-fill-hours

Aily Skill：对接 51PM 项目管理平台，支持按会话用户多轮填写项目/非项目工时。

## 结构

```text
pm-fill-hours/
├── SKILL.md
├── references/
│   └── api_docs.md
├── scripts/
│   ├── api_client.py
│   ├── config.example.json
│   └── config.json          # 本地凭证，gitignore
└── tests/
    ├── conftest.py
    └── test_api_client.py
```

## 配置

1. 复制 `scripts/config.example.json` 为 `scripts/config.json`
2. 填入超管 `base_url` / `api_key`（用于 open_id 解析与 impersonate）

示例：

```json
{
  "base_url": "http://51pm.example.com:218",
  "auth_type": "api_key",
  "api_key": "SUPER_USER_BEARER_TOKEN"
}
```

环境变量 `PM_PLATFORM_BASE_URL`、`PM_PLATFORM_API_KEY`、`PM_PLATFORM_AUTH_TYPE` 优先于文件配置。

`scripts/config.json` 含 Token，已加入 `.gitignore`，**不要提交到 Git**。

## 测试

```bash
cd e:\AIly-skill-platform
pytest pm-fill-hours/tests -v
```

## 打包与上传

在仓库根目录执行：

```bash
python scripts/package_skill.py pm-fill-hours ./output
```

生成 `output/pm-fill-hours.skill`（含 `SKILL.md`、`scripts/`、`references/`）。将 `.skill` 文件上传至 Aily 技能市场；上传前在解压后的 `scripts/` 内放置有效的 `config.json`（或通过平台配置环境变量）。

**注意**：打包产物不含 `config.json` 与 `tests/`；根目录查工时 Skill（`pm-platform-api`）与此 Skill 分别打包，勿覆盖根目录 `SKILL.md`。
