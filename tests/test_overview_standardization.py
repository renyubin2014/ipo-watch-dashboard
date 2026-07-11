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
        self.assertIn("29,500万元", result)
        self.assertIn("42.80%", result)
        self.assertEqual(result.count("先说结论"), 1)


if __name__ == "__main__":
    unittest.main()
