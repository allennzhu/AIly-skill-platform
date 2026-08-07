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

## 在飞书 Aily 中配置凭证

当前 Aily「编辑信息」只有名称/描述，**没有环境变量入口**。请用配置文件：

1. 复制 `scripts/config.example.json` 为 `scripts/config.json`
2. 填入真实 `base_url` / `api_key`
3. 重新打包：`python scripts/package_skill.py . ./output`
4. 在 Aily 市场 → 技能 → 我创建的 → 项目管理平台API → **更新技能文件**，上传新的 `pm-platform-api.skill`

本地调试仍可用环境变量（优先级高于 config.json）。

`scripts/config.json` 含 Token，已加入 `.gitignore`，不要提交到 Git。

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
