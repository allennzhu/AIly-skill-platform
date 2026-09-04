# Skill 鉴权流程（飞书 Aily）

## 分工

| 步骤 | 执行方 | 动作 |
|------|--------|------|
| 1 | **飞书智能体** | 用 `user_access_token` 获取当前对话人信息 |
| 2 | **飞书智能体** | 调飞书 API 获取 `union_id` 或邮箱 |
| 3 | **飞书智能体** | 执行 `auth save-identity` 永久保存身份（仅首次） |
| 4 | **Skill 脚本** | 读本地身份 → `GET /skill_auth/token`（免鉴权） |
| 5 | **用户** | 若无 token → 打开 51PM（已登录打开首页即可；未登录走 OAuth）→ 重试业务命令 |

Skill **不**扫描环境变量、**不**调飞书 API、**不**手填 Token。

本地 IDE（Cursor / VS Code / Copilot 等）请使用 **51PM_CLI**（`51pm login --browser`），不在本仓库做浏览器落 Token。

## 保存身份（智能体执行，仅首次）

```bash
python3 scripts/api_client.py auth \
  --param action save-identity \
  --param union_id on_xxxxxxxx
```

写入 `scripts/.feishu_identity.json`，后续会话自动复用。

## 业务调用

```bash
python3 scripts/api_client.py get_task_list --param assignee_name 张三 ...
```

- `auth_required` → 引导打开 51PM（已登录打开首页即可同步 Token；未登录用 OAuth `login_url`），完成后重试
- `identity_required` → 智能体先完成 save-identity

## 51PM 后端

- `GET /manage_api/skill_auth/token?feishu_union_id=on_xxx`（免鉴权）查 Redis 缓存
- `POST /manage_api/skill_auth/sync`（需 Bearer）：按当前用户 `feishu_union_id` 写入当前 Token（已登录直进时由前端调用）
- OAuth `CheckUser` 成功时仍会 `SaveUnionToken`
- 未绑定飞书 `union_id` 时无法写入缓存
