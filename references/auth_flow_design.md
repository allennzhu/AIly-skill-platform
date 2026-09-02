# Skill 鉴权流程（重构版）

## 分工

| 步骤 | 执行方 | 动作 |
|------|--------|------|
| 1 | **飞书智能体** | 用 `user_access_token` 获取当前对话人信息 |
| 2 | **飞书智能体** | 调飞书 API 获取 `union_id` 或邮箱 |
| 3 | **飞书智能体** | 执行 `auth save-identity` 永久保存身份（仅首次） |
| 4 | **Skill 脚本** | 读本地身份 → `GET /skill_auth/token`（免鉴权） |
| 5 | **用户** | 若无 token → 登录 51PM（:771）→ 重试业务命令 |

Skill **不**扫描环境变量、**不**调飞书 API、**不**手填 Token。

## 保存身份（智能体执行，仅首次）

```bash
python3 scripts/api_client.py auth \
  --param action save-identity \
  --param union_id on_xxxxxxxx

# 或同时保存邮箱（后端按邮箱查 token 待支持）
python3 scripts/api_client.py auth \
  --param action save-identity \
  --param union_id on_xxxxxxxx \
  --param email user@example.com
```

写入 `scripts/.feishu_identity.json`，后续会话自动复用。

## 业务调用

```bash
python3 scripts/api_client.py get_task_list --param assignee_name 张三 ...
```

- `auth_required` → 发 `login_url`，用户登录后重试
- `identity_required` → 智能体先完成 save-identity

## 51PM 后端

- `GET /manage_api/skill_auth/token?feishu_union_id=on_xxx`（免鉴权）
- 用户网页登录后 `CheckUser` 按 union_id 写入 Redis 缓存
