# A股 IPO Watch 看板

本仓库用于通过 GitHub Pages 发布 A 股待上市企业看板。

- 首页：`dashboard/index.html`
- 报告数量：30 份 HTML
- 报告日期：2026-07-10，北京时间
- 说明：本项目仅作研究分析，不构成投资建议。

数据和结论以各页面标注的官方披露文件、公告日期和来源列表为准。

## 公司相关热点新闻

企业池的“相关热点新闻”由静态数据驱动：

- 页面：`dashboard/news.html?company=<slug>`
- 公司数据：`dashboard/news-data/<slug>.json`
- 首页轻量索引：`dashboard/news-index.js`
- 校验与合并：`scripts/update_company_news.py`

更新前先准备符合 `tests/test_company_news_data.py` 合同的 intake JSON。合并并重建索引：

```bash
python scripts/update_company_news.py --intake /path/to/intake.json --rebuild-index
python scripts/update_company_news.py --validate
```

每家公司每日每类最多一条资讯；同一 ID 或原文 URL 不重复写入。没有达到来源和相关性质量门的资讯保持空缺，不补位。已读状态只保存在用户当前浏览器的 `localStorage`。
