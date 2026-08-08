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
