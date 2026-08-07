# PM Fill Hours Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 51PM 新增飞书 open_id 用户解析接口，并交付独立 Aily Skill `pm-fill-hours`，支持按会话用户多轮填写项目/非项目工时。

**Architecture:** 超管 Token 解析 open_id → impersonate 换用户 Token → `fill_hours_step` 返回缺参/任务选项或提交工时。Skill 与查工时包并列，独立打包。

**Tech Stack:** GoFrame（51PM api/service/controller/logic）；Python 3.10+ 标准库 + pytest（Skill）；复用现有 impersonate / main_panel / estimate 接口。

## Global Constraints

- 规格：`docs/superpowers/specs/2026-08-07-pm-fill-hours-skill-design.md`
- 新增接口：`GET /manage_api/qiye_user/get_user_by_feishu_open_id`
- 鉴权：超管 Token + `POST /manage_api/user/impersonate_user`
- 提交：`project_task_estimate/add` 与 `project_not_task_estimate/add`；必填 `task_id/date/consumed/remark`
- 任务列表：`main_panel/get_task_list` 与 `get_not_task_list`，`status=doing`
- Skill 目录：`e:\AIly-skill-platform\pm-fill-hours\`（独立打包，不覆盖根目录查工时 Skill）
- 凭证：`scripts/config.json`（gitignore）；环境变量优先
- `fill_hours_step` 为主入口；无服务端会话 DB
- 不实现改/删工时、附件、关联人
- 51PM 改动按 `.cursor/skills/51pm-new-api/SKILL.md` 四层补齐
- 提交信息英文 conventional commits；不 push 除非用户要求

---

## File Structure

### 51PM

| 文件 | 职责 |
|------|------|
| `api/manage_api/qiye_user/qiye_user.go` | Req/Res 定义 |
| `internal/service/qiye_user.go` | 接口方法签名 |
| `internal/controller/qiye_user/*.go` | 转发 |
| `internal/logic/qiye_user/qiye_user.go` | 查 `dev_qiye_user` |

### Skill（`e:\AIly-skill-platform\pm-fill-hours\`）

| 文件 | 职责 |
|------|------|
| `scripts/api_client.py` | HTTP、impersonate、fill_hours_step、CLI |
| `scripts/config.example.json` | 配置模板 |
| `SKILL.md` | 多轮编排 |
| `references/api_docs.md` | 接口文档 |
| `tests/test_api_client.py` | 单测 |
| `tests/conftest.py` | path setup |

---

### Task 1: 51PM — open_id 解析 API

**Files:**
- Modify: `e:\51PM\api\manage_api\qiye_user\qiye_user.go`
- Modify: `e:\51PM\internal\service\qiye_user.go`
- Modify: `e:\51PM\internal\controller\qiye_user\`（与现有 controller 文件一致）
- Modify: `e:\51PM\internal\logic\qiye_user\qiye_user.go`

**Interfaces:**
- Consumes: `dao.DevQiyeUser`，列 `FeishuOpenId` / `YunweiId` / `NickName`
- Produces: `GetUserByFeishuOpenId(ctx, req) (*GetUserByFeishuOpenIdRes, error)`

- [ ] **Step 1: 在 api 层追加 Req/Res**

```go
type GetUserByFeishuOpenIdReq struct {
	g.Meta        `path:"/get_user_by_feishu_open_id" method:"get" summary:"根据飞书open_id获取绑定的51PM用户" tags:"企微用户"`
	FeishuOpenId  string `json:"feishu_open_id" v:"required#请传入飞书open_id" dc:"飞书 open_id"`
}

type GetUserByFeishuOpenIdRes struct {
	UserId   int    `json:"user_id" dc:"51PM用户ID(yunwei_id)"`
	NickName string `json:"nick_name" dc:"昵称"`
	MobilePhone string `json:"mobile_phone" dc:"手机号"`
}
```

- [ ] **Step 2: service 接口增加方法**

在 `IQiyeUser` 增加：

```go
GetUserByFeishuOpenId(ctx context.Context, req *qiyeuser.GetUserByFeishuOpenIdReq) (res *qiyeuser.GetUserByFeishuOpenIdRes, err error)
```

- [ ] **Step 3: controller 转发**

```go
func (c *cQiyeUser) GetUserByFeishuOpenId(ctx context.Context, req *qiyeuser.GetUserByFeishuOpenIdReq) (res *qiyeuser.GetUserByFeishuOpenIdRes, err error) {
	return service.QiyeUser().GetUserByFeishuOpenId(ctx, req)
}
```

（结构体名以现有 controller 为准。）

- [ ] **Step 4: logic 实现**

```go
func (s *sQiyeUser) GetUserByFeishuOpenId(ctx context.Context, req *qiyeuser.GetUserByFeishuOpenIdReq) (res *qiyeuser.GetUserByFeishuOpenIdRes, err error) {
	res = &qiyeuser.GetUserByFeishuOpenIdRes{}
	var row *entity.DevQiyeUser
	err = dao.DevQiyeUser.Ctx(ctx).
		Where(dao.DevQiyeUser.Columns().FeishuOpenId, req.FeishuOpenId).
		Scan(&row)
	if err != nil {
		return nil, err
	}
	if row == nil || row.YunweiId == 0 {
		return nil, gerror.New("未找到飞书用户绑定，请先同步/绑定飞书账号")
	}
	res.UserId = row.YunweiId
	res.NickName = row.NickName
	res.MobilePhone = row.MobilePhone
	return res, nil
}
```

（错误包导入与项目现有风格一致。）

- [ ] **Step 5: 确认 router 已 Bind qiye_user**

`internal/cmd/router.go` 中 `/qiye_user` 组已 Bind 整个 Department/QiyeUser 时，新方法会自动挂上；若是显式逐个 Bind，补上 `GetUserByFeishuOpenId`。

- [ ] **Step 6: 本地编译**

```bash
cd /e/51PM
go build -o nul .
```

Expected: 成功

- [ ] **Step 7: 手工冒烟（有 Token 时）**

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://51pm.51aes.com:218/manage_api/qiye_user/get_user_by_feishu_open_id?feishu_open_id=ou_xxx"
```

Expected: `code=0` 且含 `user_id`，或业务错误「未找到绑定」

- [ ] **Step 8: Commit（在 51PM 仓库）**

```bash
cd /e/51PM
git add api/manage_api/qiye_user/qiye_user.go internal/service/qiye_user.go internal/controller/qiye_user internal/logic/qiye_user/qiye_user.go
git commit -m "feat: resolve 51PM user by feishu open_id"
```

---

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

### Task 3: Skill — 配置、HTTP、超管请求

**Files:**
- Create: `pm-fill-hours/scripts/api_client.py`
- Modify: `pm-fill-hours/tests/test_api_client.py`

**Interfaces:**
- Produces:
  - `load_config() -> dict`
  - `api_request(method, path, params=None, token=None, json_body=None) -> Any`
  - 默认用超管 Token；`token=` 可覆盖为用户 Token
  - GoFrame 解包：`code != 0` → `ClientError("business_error", msg)`

可从根目录查工时 `scripts/api_client.py` 复制 HTTP/config 模式，但**独立文件**，避免互相耦合。

- [ ] **Step 1: 测试 `api_request` 带自定义 token**

```python
def test_api_request_uses_override_token(monkeypatch):
    monkeypatch.setenv("PM_PLATFORM_BASE_URL", "https://pm.example.com")
    monkeypatch.setenv("PM_PLATFORM_API_KEY", "super")
    import api_client
    from unittest.mock import MagicMock, patch
    import json
    body = json.dumps({"code": 0, "data": {"ok": 1}}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    with patch("api_client.urlopen", return_value=mock_resp) as m:
        api_client.api_request("GET", "/x", token="user-tok")
        req = m.call_args[0][0]
        assert req.get_header("Authorization") == "Bearer user-tok"
```

- [ ] **Step 2: 实现最小 config + api_request（含 POST JSON）**

- [ ] **Step 3: pytest 通过**

- [ ] **Step 4: Commit**

```bash
git commit -am "feat: add fill-hours HTTP client and config"
```

---

### Task 4: Skill — resolve + impersonate

**Files:**
- Modify: `pm-fill-hours/scripts/api_client.py`
- Modify: `pm-fill-hours/tests/test_api_client.py`

**Interfaces:**
- Produces:
  - `resolve_feishu_user(open_id: str) -> dict` → `{user_id, nick_name, ...}`
  - `impersonate(user_id: int) -> str` → 用户 access token 字符串
  - `session_user_token(open_id: str) -> tuple[dict, str]` → (user, token)

`resolve` 调：`GET /manage_api/qiye_user/get_user_by_feishu_open_id`  
`impersonate` 调：`POST /manage_api/user/impersonate_user` body `{"target_user_id": N}`  
Token 字段从返回 `data.token_info` / `token_info.access_token` 等按实际响应解析（实现时对真实响应做一次探测并固定路径；单测用 mock）。

- [ ] **Step 1: 写测试（mock api_request）**

```python
def test_session_user_token(monkeypatch):
    import api_client
    def fake(method, path, params=None, token=None, json_body=None):
        if "get_user_by_feishu_open_id" in path:
            return {"code": 0, "data": {"user_id": 474, "nick_name": "朱晓辉"}}
        if "impersonate_user" in path:
            return {"code": 0, "data": {"token_info": {"access_token": "u-token"}}}
        raise AssertionError(path)
    monkeypatch.setattr(api_client, "api_request", fake)
    # 若业务数据在 data 内，resolve 需解包
    user, tok = api_client.session_user_token("ou_1")
    assert user["user_id"] == 474
    assert tok == "u-token"
```

（按最终解包辅助函数调整断言。）

- [ ] **Step 2: 实现 resolve / impersonate / session_user_token**

- [ ] **Step 3: pytest 通过**

- [ ] **Step 4: Commit**

```bash
git commit -am "feat: resolve feishu user and impersonate for fill-hours"
```

---

### Task 5: Skill — list_doing_tasks + submit_estimate

**Files:**
- Modify: `pm-fill-hours/scripts/api_client.py`
- Modify: `pm-fill-hours/tests/test_api_client.py`

**Interfaces:**
- Produces:
  - `list_doing_tasks(user_token: str, task_kind: str | None) -> list[dict]`
    - 每项：`task_id`,`name`,`project_name`,`task_kind`（`project`|`not_project`）
  - `submit_estimate(user_token, task_kind, task_id, date, consumed, remark) -> Any`

路径：
- 项目列表：`GET /manage_api/main_panel/get_task_list` params `status=doing`（数组按平台习惯传，如重复 key 或 JSON；实现时与前端一致，必要时 `status[]=doing`）
- 非项目：`GET /manage_api/main_panel/get_not_task_list`
- 提交项目：`POST /manage_api/project_task_estimate/add`
- 提交非项目：`POST /manage_api/project_not_task_estimate/add`

- [ ] **Step 1: 单测 list 合并与 submit 路由**

```python
def test_list_doing_tasks_merges(monkeypatch):
    import api_client
    calls = []
    def fake(method, path, params=None, token=None, json_body=None):
        calls.append(path)
        if "get_not_task_list" in path:
            return {"code": 0, "data": {"data": [{"id": 2, "name": "会议", "project_name": ""}]}}
        return {"code": 0, "data": {"data": [{"id": 1, "name": "开发", "project_name": "51PM"}]}}
    monkeypatch.setattr(api_client, "api_request", fake)
    opts = api_client.list_doing_tasks("u", None)
    assert {o["task_kind"] for o in opts} == {"project", "not_project"}
    assert len(opts) == 2
```

- [ ] **Step 2: 实现 list + submit**

- [ ] **Step 3: pytest 通过**

- [ ] **Step 4: Commit**

```bash
git commit -am "feat: list doing tasks and submit project/not-project estimates"
```

---

### Task 6: Skill — fill_hours_step + CLI

**Files:**
- Modify: `pm-fill-hours/scripts/api_client.py`
- Modify: `pm-fill-hours/tests/test_api_client.py`

**Interfaces:**
- Produces:
  - `fill_hours_step(params: dict) -> dict`（规格中的 JSON 形状）
  - `main(argv) -> int`：`--list-ops`；`fill_hours_step --param k v`

逻辑：
1. 校验 `feishu_open_id`
2. `session_user_token`
3. `date` 默认今天
4. 收集 `task_id/task_kind/date/consumed/remark`；缺则 `status=need_input`
5. 缺 `task_id`：拉 `task_options`，`next_question` 选任务
6. 齐：`submit_estimate`，`status=submitted`

- [ ] **Step 1: 测试缺任务返回 options**

```python
def test_fill_hours_step_need_task(monkeypatch):
    import api_client
    monkeypatch.setattr(api_client, "session_user_token", lambda oid: ({"user_id": 1, "nick_name": "A"}, "tok"))
    monkeypatch.setattr(
        api_client,
        "list_doing_tasks",
        lambda tok, kind=None: [{"task_id": 9, "name": "开发", "project_name": "P", "task_kind": "project"}],
    )
    out = api_client.fill_hours_step({"feishu_open_id": "ou_x", "consumed": "2", "remark": "联调"})
    assert out["status"] == "need_input"
    assert "task_id" in out["missing_fields"]
    assert out["task_options"][0]["task_id"] == 9
```

- [ ] **Step 2: 测试齐参提交**

```python
def test_fill_hours_step_submit(monkeypatch):
    import api_client
    monkeypatch.setattr(api_client, "session_user_token", lambda oid: ({"user_id": 1, "nick_name": "A"}, "tok"))
    monkeypatch.setattr(api_client, "submit_estimate", lambda *a, **k: {"code": 0, "data": {}})
    out = api_client.fill_hours_step({
        "feishu_open_id": "ou_x",
        "task_id": "9",
        "task_kind": "project",
        "date": "2026-08-07",
        "consumed": "2",
        "remark": "联调",
    })
    assert out["status"] == "submitted"
```

- [ ] **Step 3: 实现 fill_hours_step + argparse main**

- [ ] **Step 4: 全量 pytest**

```bash
pytest pm-fill-hours/tests -v
```

- [ ] **Step 5: Commit**

```bash
git commit -am "feat: add fill_hours_step orchestration and CLI"
```

---

### Task 7: SKILL.md + api_docs + 打包

**Files:**
- Create: `pm-fill-hours/SKILL.md`
- Create: `pm-fill-hours/references/api_docs.md`
- Modify: `pm-fill-hours/README.md`
- Reuse: 根目录 `scripts/package_skill.py`（对 `pm-fill-hours` 目录打包）或复制一份到子目录

- [ ] **Step 1: 写 SKILL.md**

Frontmatter `name: pm-fill-hours`；description 含填工时/报工；body 写：取 open_id → 调 `fill_hours_step` → 按 status 追问/展示选项/确认成功。

- [ ] **Step 2: 写 api_docs.md**（操作、缺参 JSON、51PM 路径）

- [ ] **Step 3: 打包**

```bash
python scripts/package_skill.py pm-fill-hours ./output
# 或调整 package 脚本支持子目录 src
```

Expected: `output/pm-fill-hours.skill` 存在

- [ ] **Step 4: Commit**

```bash
git add pm-fill-hours
git commit -m "docs: add pm-fill-hours SKILL.md and API reference"
```

---

### Task 8: 联调验收

**Files:** 无代码或仅修小问题

- [ ] **Step 1: 确认 51PM 新接口已部署/本地可访问**

- [ ] **Step 2: 写入 `pm-fill-hours/scripts/config.json`（超管 Token）**

- [ ] **Step 3: CLI 冒烟**

```bash
python pm-fill-hours/scripts/api_client.py fill_hours_step \
  --param feishu_open_id ou_真实 \
  --param consumed 1 \
  --param remark 测试
```

Expected: `need_input` + `task_options` 或 `resolve_failed`

- [ ] **Step 4: 补齐 task 后提交一条项目或非项目工时**

- [ ] **Step 5: 更新 Aily 技能文件并对话验收**

- [ ] **Step 6: 若有修复则 commit**

---

## Self-Review

1. **Spec coverage:** open_id API、impersonate、两类任务/提交、fill_hours_step、SKILL 多轮、config.json、验收均有 Task。
2. **Placeholder scan:** 无 TBD；`status` 数组传参与 impersonate token 字段路径要求实现时对照真实响应固定（Task 4/5 明确）。
3. **Type consistency:** `task_kind` 取值 `project`|`not_project`；`fill_hours_step` 响应字段与规格一致。
4. **Subsystem order:** Task 1（51PM）必须先于 Task 4+ 真实联调；Skill 单测可不依赖 51PM。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-07-pm-fill-hours-skill.md`.

**Two execution options:**

1. **Subagent-Driven（推荐）** — 每 Task 独立 subagent + 审查  
2. **Inline Execution** — 本会话按 executing-plans 连续执行  

选哪种？
