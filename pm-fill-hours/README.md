# pm-fill-hours

Aily Skill：对接 51PM 项目管理平台，支持按会话用户多轮填写项目/非项目工时。

## 结构

```text
pm-fill-hours/
├── scripts/
│   └── config.example.json
└── tests/
    ├── conftest.py
    └── test_api_client.py
```

## 配置

1. 复制 `scripts/config.example.json` 为 `scripts/config.json`
2. 填入超管 `base_url` / `api_key`（用于 open_id 解析与 impersonate）

`scripts/config.json` 含 Token，已加入 `.gitignore`，不要提交到 Git。

## 测试

```bash
cd e:\AIly-skill-platform
pytest pm-fill-hours/tests -v
```
