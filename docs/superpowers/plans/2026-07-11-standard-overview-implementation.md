# 快速看懂标准化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将15份快速看懂统一为固定章节顺序、万元整数金额格式、短Hero和无来源列表的静态报告。

**Architecture:** 使用 lxml 解析现有HTML DOM，识别Hero、结论和分析模块后重组成统一骨架；公司专属内容保留在标准章节槽位。生成模板同步采用同一章节与格式函数，后续生成不会回退。

**Tech Stack:** Python 3.12、lxml 6.0.2、unittest、静态 HTML/CSS、浏览器几何审计。

## Global Constraints

- Hero最多两句话，后面立即是“先说结论”。
- 15家公司采用同一8段结构。
- 金额统一为万元整数并使用千位分隔符。
- 快速看懂不显示来源列表，完整调研来源不变。
- 不修改周调度、企业池、Sites或V2。

---

### Task 1: 标准化合同测试

**Files:**
- Create: `tests/test_overview_standardization.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `format_overview_amount(value: str) -> str`、`standardize_overview_html(source: str, company: str, item: dict) -> str` 的行为合同。

- [ ] 写失败测试，验证 `295亿`、`2.95亿元`、`2950000.49万元` 均输出 `2,950,000万元`。
- [ ] 写失败测试，验证Hero后第一个主模块是“先说结论”，来源列表被删除，标准章节按序存在。
- [ ] 运行单测，确认函数不存在或旧结构不合格而失败。

### Task 2: DOM重组器与模板

**Files:**
- Create: `scripts/standardize_overview_reports.py`
- Modify: `scripts/generate_skill_structured_reports.py`
- Modify: `scripts/build_github_pages_publish.py`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: 当前 `dashboard/data.js`、`dashboard/reports.js` 和15份概览HTML。
- Produces: 固定Hero、结论、IPO事实、行业位置、业务阶梯、上下游、财务、跟踪的概览HTML。

- [ ] 实现金额解析与万元整数格式化，待补充文本原样保留。
- [ ] 用 lxml 删除概览来源列表，提取可复用模块并按标准槽位重组。
- [ ] 将Hero介绍压缩为主营业务一句和核心验证点一句。
- [ ] 清除事实卡负上边距，保证结论不被覆盖。
- [ ] 同步更新通用生成模板和发布工具文件清单。

### Task 3: 批量生成与静态质量门

**Files:**
- Create: `companies/*/reports/*overview-vN.html`
- Modify: `dashboard/reports.js`
- Modify: `scripts/validate_report_quality.py`

**Interfaces:**
- Produces: 15份新版本快速看懂及其映射。

- [ ] 为15家公司生成新版本，不覆盖旧报告。
- [ ] 校验每份只有一个“先说结论”，8个标准章节顺序一致。
- [ ] 校验概览没有来源列表、亿元单位或金额小数。
- [ ] 运行全部单测和15家公司质量门。

### Task 4: 浏览器验收与GitHub发布

**Files:**
- Modify: `publish/ipo-watch-dashboard/**`（构建生成）。

**Interfaces:**
- Produces: 15份概览乘3档视口的45次审计结果。

- [ ] 在390px、768px、1280px检查15份快速看懂的页面宽度、模块顺序和遮挡。
- [ ] 确认Hero正文最多两段且结论为首个主模块。
- [ ] 运行完整测试、质量门、构建和 `git diff --check`。
- [ ] 提交并推送现有GitHub `main`，在线核验首页与概览链接。
