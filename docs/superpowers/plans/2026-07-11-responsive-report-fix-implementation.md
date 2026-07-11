# 响应式报告修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将优势与风险改成左侧色条样式，并消除看板和30份报告在390px、768px、1280px下的页面级横向溢出。

**Architecture:** 报告升级脚本统一注入 B 样式和响应式补丁，报告生成模板内置同一规则，避免后续生成回退。看板样式只修移动端导航与收缩边界；浏览器批量审计所有当前链接。

**Tech Stack:** Python 3.12、unittest、静态 HTML/CSS、浏览器 DOM 宽度审计、GitHub Pages。

## Global Constraints

- 不改变旧版电脑看板整体布局。
- 当前发布集合继续为15家公司。
- 不修改周调度、企业池、Sites或V2。
- 页面整体不得横向滚动；只有宽表格区域允许内部滚动。

---

### Task 1: 响应式与 B 样式测试

**Files:**
- Modify: `tests/test_report_upgrade.py`
- Create: `tests/test_responsive_contract.py`

**Interfaces:**
- Produces: 对 `.conclusion-row`、`min-width:0`、`overflow-wrap:anywhere`、移动目录和表格局部滚动的静态合同测试。

- [ ] 写失败测试，断言升级后的快速看懂使用纵向 `.conclusion-row advantage/risk`，不再使用双列结论卡。
- [ ] 写失败测试，断言报告包含网格子项收缩、长文本断行、移动目录和表格滚动规则。
- [ ] 运行 `.venv/bin/python -m unittest discover -s tests -p 'test_*responsive*.py' -v`，确认因规则缺失失败。

### Task 2: 模板与当前报告升级

**Files:**
- Modify: `scripts/upgrade_current_reports.py`
- Modify: `scripts/generate_skill_structured_reports.py`
- Modify: `companies/*/reports/*overview*.html`
- Modify: `companies/*/reports/*research*.html`
- Modify: `dashboard/reports.js`

**Interfaces:**
- Produces: `responsive_css() -> str` 和 B 样式结论模块。

- [ ] 将快速看懂总结改为纵向左侧色条，每项保留标题和正文。
- [ ] 注入统一响应式规则：网格子项 `min-width:0`、长文本安全断行、媒体和交互不超过容器、手机目录横向滚动、手机表格局部滚动。
- [ ] 在报告生成模板加入同一规则，防止后续周调度生成旧样式。
- [ ] 重新运行升级脚本，生成15组新版本报告并更新映射。
- [ ] 运行报告测试和质量门，确认全部通过。

### Task 3: 看板移动端修复

**Files:**
- Modify: `mobile/styles.css`
- Modify: `dashboard/styles.css`

**Interfaces:**
- Produces: 可完整滚动到末项的 `.board-nav` 和全局安全换行规则。

- [ ] 为导航增加末端空间、滚动条隐藏和右侧渐隐提示。
- [ ] 为卡片、公司名、按钮和文本容器增加收缩与安全换行边界。
- [ ] 保持桌面端卡片结构和断点不变。

### Task 4: 批量浏览器验收与发布

**Files:**
- Modify: `publish/ipo-watch-dashboard/**`（构建生成）

**Interfaces:**
- Consumes: `dashboard/reports.js` 中30个报告链接。
- Produces: 32个页面乘3档视口的宽度审计结果。

- [ ] 构建 GitHub Pages 发布包。
- [ ] 在390px、768px、1280px下检查电脑版看板、手机版看板和30份报告，断言页面 `scrollWidth <= clientWidth`。
- [ ] 检查所有表格超宽只发生在表格自身，导航最后一项可滚动到可视区域。
- [ ] 运行21项以上完整测试、质量门和 `git diff --check`。
- [ ] 提交并推送现有 GitHub `main`，在线抽查首页、手机版和两类报告。
