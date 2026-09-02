# Skill 权限矩阵（业务规则）

**后端接口不做业务权限校验时，由 Skill 在调用前本地强制执行下列规则。**

登录用户身份来自：`auth save-identity` → `/skill_auth/token` → `get_user_info`（`root_id` → 角色，见 `references/role_catalog.md`）。

## 角色目录（`dev_menu_root`）

完整 id / 名称 / 平台描述见 **`references/role_catalog.md`**。下表为 Skill 层读写的摘要映射。

| id | code | 平台名称 | Skill 查询范围 | Skill 写操作 |
|----|------|----------|----------------|--------------|
| 1 | GHOST | 超级员工权限 | 全模块、全员、全项目 | 工程写（全范围） |
| 2 | ADMIN | 管理员 | 同 GHOST | 同 GHOST |
| 3 | PM | 项目经理 | 同 GHOST | 工程写（全范围） |
| 24 | RO | 全量只读 | 同 GHOST（全量只读） | **禁止** |
| 11 | HR | 人力行政 | 仅工时/工作总结类（可查任何人） | **禁止** |
| 6 | GL | 四级负责人 | 本人 + 负责部门/组 + 子部门；项目=参与范围 | 工程写（范围内） |
| — | `leader_id` | 部门负责人（非角色表） | 同 GL 的人员/部门范围 | 按用户角色写规则 |
| 4 | TB | BD/TB | 参与 + BD/TB 负责项目；工时脱敏 | **仅** 3 类写操作 |
| 7 | BG | 行业运营 | 自己相关项目（全字段） | **禁止** |
| 22/23/25/26 | TA/DEV/SP/QA | 工程组员/场景/测试 | 本人 + 参与项目 | 工程写（范围内） |
| 9 | Nor | 普通成员 | 本人 + 参与项目 | **禁止** |
| 8 | FA | 区域组织中台/财务/采购 | 本人 + 参与项目（概况/动态类；中台全项目数据由平台控制） | **禁止** |
| 10 | RST | 受限用户 | 本人 + 参与项目 | **禁止** |

## 本地校验点（四层 + 脱敏）

| 层级 | 函数 | 行为 | 典型场景 |
|------|------|------|----------|
| **操作级** | `check_operation_access` | **拒绝调用** | HR 不能调 `get_bug_list`；非 PM 不能调 `get_qa_stat_*` |
| **参数级** | `enforce_param_scope` | **拒绝调用**（`permission_denied`） | 明确指定了无权访问的 `dept_name` / `user_name` / `project_name` |
| **结果级** | `filter_read_response_scope` | **允许调用，裁剪响应** | TB/工程成员调列表接口，只保留可见项目/用户行 |
| **写入级** | `enforce_write_project_scope` | **拒绝写入** | 写操作目标项目不在范围内 |
| **字段级** | `mask_tb_sensitive_fields` | **允许调用，脱敏字段** | BD/TB 看工时/成本时隐藏实际花费 |

### 操作拒绝 vs 结果过滤

- **不是**所有接口都一刀切禁止。例如 **BD/TB 可以**调用 `get_project_info`、`get_bug_list` 等（不在组织级特权名单内）。
- 对 TB/BG/工程成员/GL：**接口照常请求**，返回按可见用户/项目集过滤。
- **参数级拒绝**：请求里显式带了越界的人/部门/项目 → `permission_denied` + `terminal: true`。
- **结果过滤**：空列表/裁剪后是正常成功响应。

## 数据范围原则

1. 非 GHOST/ADMIN/PM/RO：**不能**在参数里指定别的部门（`dept_name` 须在本人或 `leader_id` 负责部门及子部门内）
2. 非特权角色：**不能**在参数里指定他人（`user_name` 须在允许用户集合内）
3. 非特权角色：**不能**在参数里指定未参与/未负责的项目；未带项目参数的列表则**结果过滤**
4. 组织级模块（`get_qa_stat_*`、`get_dept_*`、供应商/外包、全公司 `get_project_list` 等）：**仅 GHOST/ADMIN/PM/RO（只读）**
5. **`get_dept_members`**：登录即可查任意部门成员，无本地范围限制

## BD/TB 唯一允许的写操作

| 操作 | 说明 |
|------|------|
| `apply_publish` | 递交申请 |
| `add_apply_demand` | 制作需求申请 |
| `add_feedback_demand_pool` | 反馈需求池 |

## 权限拒绝时（立即终止）

```json
{
  "error": "permission_denied",
  "terminal": true,
  "stop": true,
  "detail": "无权查询该部门数据…"
}
```

Agent **必须立即停止**，向用户说明当前角色（`actor.role_title`）与限制。

## CLI 示例

```bash
python3 scripts/api_client.py auth --param action save-identity --param union_id on_xxx
python3 scripts/api_client.py --list-ops-grouped

python3 scripts/api_client.py get_work_hours \
  --param my_team_scope 1 \
  --param start_date 2026-09-01 --param end_date 2026-09-07
```
