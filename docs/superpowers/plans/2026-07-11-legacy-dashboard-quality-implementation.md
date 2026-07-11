# 旧版 IPO 看板质量改造 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在旧版首页布局不变的前提下，将15家公司统一到单一发布数据源，建立可复现环境和报告质量门，并升级两类报告的分析表达。

**Architecture:** `dashboard/data.js` 定义当前15家公司发布集合，`dashboard/reports.js` 为同一集合提供两类报告映射。Python 校验器在报告生成和 GitHub Pages 打包前验证集合、路径、PDF、状态、单位、页码与来源映射；报告生成器统一输出长鑫风格的结论与分析模块。

**Tech Stack:** Python 3.12、pypdf、标准库 unittest、静态 HTML/CSS/JavaScript、GitHub Pages。

## Global Constraints

- 当前发布集合固定为旧版线上15家公司。
- 不修改周调度任务和企业池更新逻辑。
- 不修改旧版首页、电脑版和手机版的页面布局。
- PDF、状态、单位、页码与报告映射质量信息只显示在完整调研来源列表。
- 后续只发布到 GitHub Pages，不使用 Sites。

---

### Task 1: 单一发布集合与可复现环境

**Files:**
- Create: `.python-version`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Modify: `dashboard/data.js`
- Create: `tests/test_publish_contract.py`

**Interfaces:**
- Produces: `load_js_object(path: Path) -> dict` 测试辅助函数；固定15家公司集合。

- [ ] 写失败测试，断言 `dashboard/data.js` 与 `dashboard/reports.js` 都恰好是线上15家公司且集合相同。
- [ ] 运行 `python3 -m unittest tests.test_publish_contract -v`，确认因18/15分叉失败。
- [ ] 用发布版15家公司数据恢复源 `dashboard/data.js`，保留长鑫并移除四个未发布候选；规范嘉立创板块为“深交所主板”。
- [ ] 写入 `.python-version` 的 `3.12`，在 `requirements.txt` 固定 `pypdf==6.1.1`，在 `requirements-dev.txt` 引用运行依赖。
- [ ] 使用 Python 3.12 隔离环境安装锁定依赖，并运行测试确认集合测试通过。

### Task 2: 发布与来源质量门

**Files:**
- Create: `scripts/validate_report_quality.py`
- Modify: `scripts/build_github_pages_publish.py`
- Modify: `tests/test_current_report_integrity.py`
- Create: `tests/test_report_quality_gate.py`

**Interfaces:**
- Produces: `validate_publish_contract(root: Path) -> list[str]`。
- Produces: `validate_research_sources(html_path: Path, company: str) -> list[str]`。
- Consumes: `dashboard/data.js`、`dashboard/reports.js`、公司 `sources/` 与完整调研 HTML。

- [ ] 写失败测试，覆盖公司集合不一致、报告文件不存在、无有效 PDF、来源缺状态日期、关键数据缺单位/期间/页码、来源未说明对应章节。
- [ ] 运行质量门测试，确认每类错误都能被识别。
- [ ] 实现校验器：解析两份 JS JSON 包装；比较集合；验证报告路径；验证 PDF 文件头 `%PDF-`；解析完整调研来源表的结构化 `data-*` 元数据。
- [ ] 在 GitHub Pages 构建入口复制文件前调用质量门，错误时输出公司与缺失字段并终止。
- [ ] 修复原有完整性测试，使其使用同一15家公司集合并继续保留财务纠错断言。
- [ ] 运行 `python3 -m unittest discover -s tests -v`，确认环境与合同相关测试通过。

### Task 3: 统一报告模板和15家公司内容

**Files:**
- Modify: `scripts/generate_skill_structured_reports.py`
- Modify: `skills/a-share-company-html-research/references/html-report-blueprint.md`
- Modify: `tests/test_finance_visuals.py`
- Modify: `companies/*/reports/*-overview-*.html`
- Modify: `companies/*/reports/*-research-*.html`
- Modify: `dashboard/reports.js`

**Interfaces:**
- Produces: `build_strengths_and_risks(data: ReportData) -> tuple[list[dict], list[dict]]`。
- Produces: `build_profit_mechanism(data: ReportData) -> dict`。
- Produces: `build_non_consensus(data: ReportData) -> list[dict]`。
- Produces: `build_falsification_signals(data: ReportData) -> list[dict]`。

- [ ] 写失败测试，要求快速看懂出现“先说结论”“最大优势”“最大风险”，完整调研出现“利润机制”“非共识判断”“反证信号”。
- [ ] 为报告数据增加通俗判断结构，优先使用公司现有财务、行业位置、客户供应商和募投证据；缺证据时明确“待复核”，不生成模板化空话。
- [ ] 快速看懂在 Hero 后加入结论模块，不改变首页看板布局。
- [ ] 完整调研加入三类分析模块，并让核心判断与反证信号一一对应。
- [ ] 完整调研来源列表输出来源级别、文件、PDF校验、状态及日期、期间、单位、页码、使用章节和限制的结构化元数据。
- [ ] 按统一模板为当前15家公司生成新版本报告，更新 `dashboard/reports.js` 指向新文件，不覆盖旧报告。
- [ ] 运行报告内容测试与质量门，确认15家公司全部合格。

### Task 4: 构建和浏览器验收

**Files:**
- Modify: `publish/ipo-watch-dashboard/**`（由构建脚本生成，保留 `.git`）

**Interfaces:**
- Consumes: 已通过质量门的15家公司数据与报告。
- Produces: 可直接由 GitHub Pages 托管的静态发布包。

- [ ] 记录旧版 `index.html`、`dashboard/index.html`、`mobile/index.html` 布局文件哈希。
- [ ] 运行 `python3 scripts/build_github_pages_publish.py`，确认输出 `PUBLISH_BUNDLE_OK`。
- [ ] 再次核对三个布局文件哈希；允许 `data.js`、`reports.js` 和报告文件变化，不允许布局文件变化。
- [ ] 用浏览器检查桌面端首页、390px手机版、随机三家公司和长鑫科技的两类报告。
- [ ] 运行全部测试、无占位符扫描、重复 ID 检查和本地链接检查。

### Task 5: GitHub 发布

**Files:**
- Commit: `publish/ipo-watch-dashboard` 中本次生成和文档变更。

**Interfaces:**
- Produces: 原 GitHub Pages 地址上的旧版看板更新。

- [ ] 用 `git diff --check` 和 `git status --short` 核对仅含本次范围。
- [ ] 提交一个清晰目的的发布提交，不包含 Sites 或周调度改动。
- [ ] 推送 `main` 到现有 GitHub 仓库。
- [ ] 在线核验根入口、电脑版、手机版及报告链接；确认 `/v2/` 不再恢复。
