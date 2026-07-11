import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "standardize_overview_reports.py"


class OverviewStandardizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("standardize_overview_reports", MODULE_PATH)
        cls.module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[spec.name] = cls.module
        spec.loader.exec_module(cls.module)

    def test_amounts_are_formatted_as_integer_wan(self):
        self.assertEqual(self.module.format_overview_amount("295亿"), "2,950,000万元")
        self.assertEqual(self.module.format_overview_amount("2.95亿元"), "29,500万元")
        self.assertEqual(self.module.format_overview_amount("2950000.49万元"), "2,950,000万元")
        self.assertEqual(self.module.format_overview_amount("-116400.5万元"), "-116,401万元")

    def test_standardized_page_has_fixed_order_and_no_source_list(self):
        source = """<!doctype html><html><head><title>样本</title></head><body>
        <header class="hero"><h1>旧标题</h1><p>很长的旧介绍</p></header><main>
        <section><h2>行业位置</h2><p>行业内容</p></section>
        <section class="panel conclusion-first"><h2>先说结论</h2><p>结论</p></section>
        <section><h2>业务/产品阶梯</h2><p>业务内容</p></section>
        <section><h2>上下游读数</h2><p>上下游内容</p></section>
        <section><h2>核心财务读数</h2><p>收入 2.95亿元，毛利率 42.8%</p></section>
        <section><h2>后续只盯事项</h2><p>跟踪内容</p></section>
        <section><h2>来源列表</h2><p>来源内容</p></section></main></body></html>"""
        item = {"name": "样本股份有限公司", "board": "科创板", "status": "注册生效", "industry": "设备制造业", "latestProgress": "注册生效", "expectedListingTime": "待补充", "metrics": {}}
        analysis = {"advantages": ["优势"], "risks": ["风险"]}

        result = self.module.standardize_overview_html(source, item, analysis, "")

        expected = ["先说结论", "IPO与关键事实", "公司与行业位置", "产品或业务阶梯", "上下游关系", "财务读数", "后续重点跟踪"]
        positions = [result.index(text) for text in expected]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("来源列表", result)
        self.assertIn("单位：万元；百分比除外", result)
        self.assertEqual(result.count("先说结论"), 1)

    def test_financial_cards_are_short_labeled_and_use_integer_wan(self):
        source = """<html><head><title>样本</title></head><body><header class='hero'><p>介绍</p></header><main>
        <section><h2>行业位置</h2><div class='chart'>图</div><table><tr><td>重复明细</td></tr></table><p>读图结论</p></section>
        <section><h2>业务阶梯</h2><p>业务</p></section><section><h2>上下游</h2><p>链条</p></section>
        <section><h2>后续只盯</h2><p>跟踪</p></section></main></body></html>"""
        research = """<html><body><section id='finance'><h2>财务分析</h2><table>
        <tr><th>项目</th><th>2025</th><th>2024</th><th>2023</th></tr>
        <tr><td>营业收入</td><td>99,016.00</td><td>72,238.74</td><td>30,118.74</td></tr>
        <tr><td>扣非归母净利润</td><td>-119,726.11</td><td>-150,269.38</td><td>-156,668.54</td></tr>
        <tr><td>2026Q1 营业收入</td><td>28,699.33 万元，同比 +1,474.85%</td></tr>
        <tr><td>2026Q1 净利润</td><td>-44,434.41 万元，同比亏损扩大 38.04%</td></tr>
        <tr><td>2026H1 收入预计</td><td>106,000.00 至 115,000.00 万元，同比 +258.68% 至 +289.13%</td></tr>
        </table></section></body></html>"""
        item = {"name": "样本股份有限公司", "board": "科创板", "status": "注册生效", "industry": "设备制造业", "expectedListingTime": "待补充", "metrics": {"fundraisingFit": "拟募资600,000万元", "revenueGrowth": "2025/2024/2023营业收入：99,016.00,72,238.74,30,118.74万元", "profitQuality": "2025/2024/2023扣非归母净利润：-119,726.11,-150,269.38,-156,668.54万元"}}
        analysis = {"advantages": ["优势"], "risks": ["风险"]}

        result = self.module.standardize_overview_html(source, item, analysis, "", research)

        self.assertIn('<strong>2026Q1｜28,699万元</strong>', result)
        self.assertIn('同比增长1,474.85%', result)
        self.assertIn('<strong>2026Q1｜亏损44,434万元</strong>', result)
        self.assertIn('同比亏损扩大38.04%', result)
        self.assertIn('公司预计', result)
        self.assertIn('单位：万元；百分比除外', result)
        self.assertNotRegex(result, r"\d+\.\d+万元")

    def test_industry_position_keeps_visual_but_removes_duplicate_table(self):
        fragment = """<section><h2>行业位置</h2><div class='share-row'>图表</div><table><tr><td>重复明细</td></tr></table><p>读图结论</p></section>"""

        result = self.module.prune_position_content(fragment)

        self.assertIn("share-row", result)
        self.assertIn("读图结论", result)
        self.assertNotIn("<table", result)


if __name__ == "__main__":
    unittest.main()
