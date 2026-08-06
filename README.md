# pm-platform-api

Aily Skill：对接 51PM 项目管理平台工时 API，用于查询工时并生成工作总结。

## 结构

```text
.
├── SKILL.md
├── scripts/
│   ├── api_client.py
│   └── package_skill.py
└── references/
    └── api_docs.md
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `PM_PLATFORM_BASE_URL` | 平台 API 根地址，如 `https://pm.example.com` |
| `PM_PLATFORM_AUTH_TYPE` | 固定 `api_key` |
| `PM_PLATFORM_API_KEY` | Bearer Token |

可参考 `.env.example`。不要把真实 Token 提交到仓库。

## 本地使用

```bash
pip install -r requirements-dev.txt

# Windows PowerShell
$env:PM_PLATFORM_BASE_URL="https://your-pm-host"
$env:PM_PLATFORM_AUTH_TYPE="api_key"
$env:PM_PLATFORM_API_KEY="your_token"

python scripts/api_client.py --list-ops

python scripts/api_client.py get_work_hours `
  --param start_date 2026-08-03 `
  --param end_date 2026-08-06 `
  --param user_name 张三
```

## 测试

```bash
pytest tests/ -v
```

## 打包与部署

```bash
python scripts/package_skill.py . ./output
# 生成 output/pm-platform-api.skill

# 上传到 SkillHub（需已安装 aily-cli）
# aily-cli skillhub upload --file output/pm-platform-api.skill
# aily-cli skillhub install pm-platform-api
```

## 扩展新接口

同步更新三处：

1. `scripts/api_client.py` 的 `OPERATIONS`
2. `references/api_docs.md`
3. `SKILL.md` 的意图映射与 frontmatter `description`
