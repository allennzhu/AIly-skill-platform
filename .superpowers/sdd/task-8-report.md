# Task 8 Report — 联调验收

## Status: DONE_WITH_CONCERNS（阻塞项在 51PM 部署）

## Verified locally

- `pytest pm-fill-hours/tests` → **16 passed**
- `python scripts/package_skill.py pm-fill-hours ./output` → `output/pm-fill-hours.skill`（已排除 `__pycache__`）
- CLI `--list-ops` / `fill_hours_step` 可运行
- 已复制 `pm-fill-hours/scripts/config.json`（gitignore）供本地调用

## Smoke against http://51pm.51aes.com:218

```
GET /manage_api/qiye_user/get_user_by_feishu_open_id → HTTP 404 Not Found
fill_hours_step(feishu_open_id=ou_test_smoke) → {"error":"http_error","status":404}
```

**原因：** Task 1 接口仅在本地分支 `feature/get-user-by-feishu-open-id`（commit `ce08f4f`），**尚未部署到 51pm.51aes.com:218**。

## Blockers for full E2E

1. **部署 51PM** `get_user_by_feishu_open_id` 到可访问环境
2. **config.json 使用超级用户 Token**（当前可能是普通用户；`impersonate_user` 需要超管）
3. **真实飞书 `open_id`**，且已在 `dev_qiye_user` 绑定 `yunwei_id`
4. Aily 上传 `output/pm-fill-hours.skill` 并对话验收

## Not done in this task

- 真实提交一条项目/非项目工时（依赖上述 1–3）
- Aily 端对话验收（依赖打包上传 + 接口可用）
