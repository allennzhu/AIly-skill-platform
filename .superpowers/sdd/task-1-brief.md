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
