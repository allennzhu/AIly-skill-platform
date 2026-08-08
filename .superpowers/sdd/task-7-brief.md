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
