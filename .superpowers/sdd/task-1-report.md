# Task 1 Report: 51PM — open_id 解析 API

## Status

**DONE**

## Summary

Implemented `GET /manage_api/qiye_user/get_user_by_feishu_open_id` across all four GoFrame layers (api → service → controller → logic). The endpoint maps a Feishu `open_id` to a 51PM `user_id` (yunwei_id) via `dev_qiye_user`, returning nickname and mobile phone when a binding exists.

## Commit

| SHA | Subject |
|-----|---------|
| `ce08f4f` | feat: resolve 51PM user by feishu open_id |

Branch: `feature/get-user-by-feishu-open-id`

## Files Changed

| Layer | File | Change |
|-------|------|--------|
| API | `api/manage_api/qiye_user/qiye_user.go` | Added `GetUserByFeishuOpenIdReq` / `GetUserByFeishuOpenIdRes` |
| Service | `internal/service/qiye_user.go` | Added `GetUserByFeishuOpenId` to `IQiyeUser` |
| Controller | `internal/controller/qiye_user/qiye_user.go` | Added forwarder on `cQiyeUser` |
| Logic | `internal/logic/qiye_user/qiye_user.go` | DAO lookup by `FeishuOpenId`, business error when unbound |

Router: no change required — `internal/cmd/router.go` already binds `qiye_user.QiyeUser` under `/qiye_user`.

## API Contract

**Request**

```
GET /manage_api/qiye_user/get_user_by_feishu_open_id?feishu_open_id=ou_xxx
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `feishu_open_id` | string | yes | Feishu open_id |

**Success response** (`code=0`)

```json
{
  "user_id": 123,
  "nick_name": "张三",
  "mobile_phone": "13800138000"
}
```

**Business error** (no binding or `yunwei_id=0`)

```
未找到飞书用户绑定，请先同步/绑定飞书账号
```

## Logic Details

- Query: `dao.DevQiyeUser.Ctx(ctx).Where(FeishuOpenId, req.FeishuOpenId).Scan(&row)`
- Returns error when `row == nil` or `row.YunweiId == 0`
- Maps `YunweiId → user_id`, `NickName → nick_name`, `MobilePhone → mobile_phone`
- Uses `gerror.New` for business errors (consistent with other logic modules)

## Verification

### Build

```powershell
cd e:\51PM
go build -o nul .
```

**Result:** exit code 0 — success.

### Manual smoke (not run)

Requires a valid Bearer token and a known `feishu_open_id` in `dev_qiye_user`. Example:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://51pm.51aes.com:218/manage_api/qiye_user/get_user_by_feishu_open_id?feishu_open_id=ou_xxx"
```

Expected: `code=0` with `user_id`, or business error when unbound.

## Self-Review

| Check | Result |
|-------|--------|
| All 4 layers implemented | ✅ |
| Signatures match task brief verbatim | ✅ |
| Path/method/tags match spec | ✅ |
| DAO columns match entity (`FeishuOpenId`, `YunweiId`, `NickName`, `MobilePhone`) | ✅ |
| Error message matches brief | ✅ |
| Controller struct name follows existing `cQiyeUser` | ✅ |
| Router auto-bind via existing group | ✅ |
| No unrelated changes | ✅ |
| `go build` passes | ✅ |

### Notes / Concerns

1. **Manual smoke not executed** — no `$TOKEN` or test `open_id` available in this environment. Build verification only.
2. **Multiple rows with same `feishu_open_id`** — logic uses `Scan` into a single pointer; if duplicates exist, GoFrame returns the first match. This matches brief spec; dedup is a data hygiene concern outside this task.
3. **`main.exe~` untracked** — pre-existing build artifact, not committed.

## Next Steps (for downstream tasks)

Task 2+ can call this endpoint from the Aily Skill Python client to resolve Feishu `open_id` → 51PM `user_id` before impersonation and fill-hours flows.
