# Overview Financial Readability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让15家公司快速看懂中的关键事实、行业位置和财务读数更适合人类快速阅读，并纳入可追溯的2026年最新数据。

**Architecture:** 在现有标准化脚本中增加独立的关键事实解析、行业位置裁剪和财务卡片生成边界。财务数据优先读取当前完整调研和显式公司覆盖配置，不从概览长句反向猜测；发布质量门锁定格式和期间规则。

**Tech Stack:** Python 3.12、lxml 6.0.2、unittest、静态 HTML/CSS、Playwright。

## Global Constraints

- 只修改15家公司快速看懂，不修改首页、完整调研、企业池和周调度。
- 金额统一为万元、整数和千分位；百分比及倍数保留两位小数。
- 2026年实际数据优先于预计数据，预计数据必须明确标注。
- 没有可追溯2026年数据时明确说明，不推算、不编造。
- 公司与行业位置保留核心图，删除重复明细表。

---

### Task 1: 锁定人类可读的数据合同

**Files:**
- Modify: `tests/test_overview_standardization.py`
- Modify: `scripts/standardize_overview_reports.py`

**Interfaces:**
- Produces: `build_fact_cards(item, research_tree, overrides) -> str`
- Produces: `build_finance_overview(item, research_tree, overrides) -> str`
- Produces: `prune_position_content(fragment) -> str`

- [ ] **Step 1: Write the failing tests**

新增断言：关键事实卡含独立主值和脚注；金额无小数；预计值带“公司预计”；财务模块含单位；行业位置不含表格。

- [ ] **Step 2: Run tests to verify RED**

Run: `.venv/bin/python -m unittest tests.test_overview_standardization -v`

Expected: FAIL，因为当前输出仍复用长句且行业位置保留表格。

- [ ] **Step 3: Implement minimal rendering boundaries**

在标准化脚本中把关键事实、行业位置和财务读数从通用章节复制逻辑中拆出，保持其他章节不变。

- [ ] **Step 4: Run tests to verify GREEN**

Run: `.venv/bin/python -m unittest tests.test_overview_standardization -v`

Expected: PASS。

### Task 2: 核对并接入2026年最新期间

**Files:**
- Modify: `scripts/standardize_overview_reports.py`
- Modify: `tests/test_current_report_integrity.py`

**Interfaces:**
- Consumes: 当前完整调研 HTML 中的2026Q1和2026H1披露。
- Produces: `LATEST_FINANCIAL_OVERRIDES`，仅保存已在完整调研可追溯的结构化期间数据。

- [ ] **Step 1: Inventory current research data**

逐家公司扫描当前完整调研中的 `2026Q1`、`2026H1`、`预计`，记录收入、利润、现金流、同比和实际/预计标签。

- [ ] **Step 2: Write failing integrity tests**

锁定燧原科技2026Q1收入与利润、2026H1预计；锁定其他已有2026披露公司的最新期间；没有数据的公司不得出现推算值。

- [ ] **Step 3: Run tests to verify RED**

Run: `.venv/bin/python -m unittest tests.test_current_report_integrity -v`

Expected: FAIL，因为当前快速看懂遗漏最新期间。

- [ ] **Step 4: Add verified overrides and regenerate**

将核对后的期间、指标、金额、同比和数据性质传给统一组件，重新生成15份概览并更新报告映射。

- [ ] **Step 5: Run tests to verify GREEN**

Run: `.venv/bin/python -m unittest tests.test_current_report_integrity -v`

Expected: PASS。

### Task 3: 扩展发布质量门

**Files:**
- Modify: `scripts/validate_report_quality.py`
- Modify: `tests/test_report_quality_gate.py`

**Interfaces:**
- Produces: 快速看懂财务单位、金额精度、预计标签、表格去重检查。

- [ ] **Step 1: Write failing gate tests**

构造违反单位、金额小数、预计标签和行业位置重复表格的HTML，断言质量门拒绝。

- [ ] **Step 2: Run tests to verify RED**

Run: `.venv/bin/python -m unittest tests.test_report_quality_gate -v`

Expected: FAIL。

- [ ] **Step 3: Implement quality checks**

用lxml解析当前概览，检查财务模块单位、金额格式、预计标签和行业位置表格数量。

- [ ] **Step 4: Run tests to verify GREEN**

Run: `.venv/bin/python -m unittest tests.test_report_quality_gate -v`

Expected: PASS。

### Task 4: 发布构建与三端验收

**Files:**
- Modify: `dashboard/reports.js`
- Create: 15份新的 `companies/*/reports/*-overview-vN.html`
- Regenerate: `publish/ipo-watch-dashboard`

**Interfaces:**
- Consumes: 标准化脚本输出。
- Produces: GitHub Pages可直接访问的15份概览。

- [ ] **Step 1: Run full verification**

Run: `.venv/bin/python -m unittest discover -s tests -v`

Run: `.venv/bin/python scripts/validate_report_quality.py`

Expected: 全部通过，质量门输出 `REPORT_QUALITY_GATE_OK companies=15`。

- [ ] **Step 2: Build publish bundle**

Run: `.venv/bin/python scripts/build_github_pages_publish.py`

Expected: 输出 `PUBLISH_BUNDLE_OK`。

- [ ] **Step 3: Browser audit**

在390、768、1280像素下检查15份概览，共45项；要求无横向溢出、遮挡、重叠，且关键事实和财务标签可见。

- [ ] **Step 4: Commit and push**

提交本次相关文件并推送GitHub main；推送后检查Pages首页返回HTTP 200。
