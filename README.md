# pm-platform-api

Aily Skill：对接 51PM 项目管理平台工时 API，用于查询工时并生成工作总结。

## 结构

```text
.
├── SKILL.md
├── scripts/
│   ├── api_client.py          # CLI 入口
│   ├── auth_session.py        # union_id / token 鉴权
│   ├── permission_policy.py   # 本地权限预检与结果过滤
│   ├── operations_*.py        # 各域操作定义
│   └── package_skill.py
└── references/
    ├── api_docs.md
    ├── permission_matrix.md
    └── auth_flow_design.md
```

## 在飞书 Aily 中配置

1. 飞书智能体用 `user_access_token` 获取对话人 `union_id`，执行一次：
   `python3 scripts/api_client.py auth --param action save-identity --param union_id on_xxx`
2. 可选：复制 `scripts/config.example.json` 为 `scripts/config.json` 覆盖 `base_url` / `login_url`
3. 打包：`python scripts/package_skill.py . ./output`
4. 在 Aily 市场更新 `pm-platform-api.skill`

`scripts/.feishu_identity.json` 与 `scripts/config.json` 已加入 `.gitignore`。

## 本地使用

```bash
python scripts/api_client.py auth --param action save-identity --param union_id on_xxx

python scripts/api_client.py get_work_hours \
  --param start_date 2026-08-03 \
  --param end_date 2026-08-06 \
  --param user_name 张三
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
