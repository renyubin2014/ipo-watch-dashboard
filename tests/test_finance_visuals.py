import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "generate_skill_structured_reports.py"


spec = importlib.util.spec_from_file_location("generate_skill_structured_reports", MODULE_PATH)
reports = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = reports
spec.loader.exec_module(reports)


def sample_report_data() -> object:
    item = {
        "name": "样本股份有限公司",
        "board": "科创板",
        "industry": "专用设备制造业",
        "status": "注册生效",
        "classification": "重点跟踪",
        "latestProgress": "注册生效",
        "industryScore": 4,
        "scoreNote": "测试样本",
        "sourceName": "测试来源",
        "sourceDate": "2026-07-10",
        "fileName": "测试招股书",
        "officialLink": "待补充",
        "applyDate": "2026-01-01",
        "expectedListingTime": "待补充",
        "sponsor": "测试保荐机构",
    }
    return reports.ReportData(
        company="样本股份有限公司",
        short="样本",
        pdf=None,
        pdf_date="2026-07-10",
        pdf_title="样本招股说明书",
        item=item,
        business={"text": "公司主要从事测试业务。", "page": 1},
        customer={"ratio": "35.00%", "amount": "10,000.00", "page": 2, "snippet": "测试客户"},
        supplier={"ratio": "25.00%", "amount": "8,000.00", "page": 3, "snippet": "测试供应商"},
        fundraising={"amount": "50,000.00", "page": 4, "snippet": "测试募投"},
        metrics={
            "营业收入": reports.Metric("营业收入", ["100,000.00", "80,000.00", "60,000.00"], 10, "营业收入 100,000.00 80,000.00 60,000.00"),
            "扣非归母净利润": reports.Metric("扣非归母净利润", ["12,000.00", "8,000.00", "4,000.00"], 11, "扣非归母净利润 12,000.00 8,000.00 4,000.00"),
            "经营现金流": reports.Metric("经营现金流", ["9,500.00", "7,200.00", "2,100.00"], 12, "经营活动现金流量净额 9,500.00 7,200.00 2,100.00"),
            "毛利率": reports.Metric("毛利率", ["31.00%", "29.00%", "27.00%"], 13, "主营业务毛利率 31.00% 29.00% 27.00%"),
        },
    )


class FinanceVisualTests(unittest.TestCase):
    def test_overview_replaces_generic_bar_chart_with_readable_finance_cards(self):
        html = reports.overview_html(sample_report_data())

        self.assertIn("核心财务读数", html)
        self.assertIn("行业位置", html)
        self.assertIn("业务/产品阶梯", html)
        self.assertIn("finance-cards", html)
        self.assertIn("收入", html)
        self.assertIn("三年复合增速", html)
        self.assertIn("利润率", html)
        self.assertIn("现金流/利润", html)
        self.assertIn("倍", html)
        self.assertNotIn("核心财务图", html)
        self.assertNotIn("bar-chart", html)
        self.assertNotIn("初筛评分", html)

    def test_research_finance_section_uses_judgement_cards_not_duplicate_chart(self):
        html = reports.research_html(sample_report_data())

        self.assertIn("财务读数判断", html)
        self.assertIn("增长", html)
        self.assertIn("利润质量", html)
        self.assertIn("现金流", html)
        self.assertNotIn("bar-chart", html)

    def test_cash_profit_ratio_uses_chinese_unit_and_handles_loss(self):
        self.assertEqual(reports.ratio_multiple("9,500.00", "12,000.00"), "0.79 倍")
        self.assertEqual(reports.ratio_multiple("11,834.03", "-580.00"), "不适用")

    def test_business_extraction_ignores_shareholder_business_relationship(self):
        texts = [
            "科大控股的主营业务为投资管理，未从事与发行人主营业务相同或相似的业务。",
            "四、发行人主营业务经营情况 公司秉承为国造仪的理念，自成立以来专注于高端科学仪器的研发，面向量子科技、材料科学等多个领域提供高端科学仪器装备。",
        ]

        result = reports.extract_business(texts)

        self.assertEqual(result["page"], 2)
        self.assertIn("高端科学仪器", result["text"])

    def test_sanitize_metrics_drops_suspicious_numbers_before_rendering(self):
        data = sample_report_data()
        data.metrics["扣非归母净利润"] = reports.Metric("扣非归母净利润", ["202", "5", "202"], 20, "扣非归母净利润 202 5 202")
        data.metrics["经营现金流"] = reports.Metric("经营现金流", ["231,418,054.46", "207,192,501.59", "165,495,179.76"], 21, "经营活动现金流量净额 231,418,054.46 207,192,501.59 165,495,179.76")

        reports.sanitize_metrics(data)

        self.assertNotIn("扣非归母净利润", data.metrics)
        self.assertNotIn("经营现金流", data.metrics)
        self.assertTrue(any("扣非归母净利润" in warning for warning in data.warnings))
        self.assertTrue(any("经营现金流" in warning for warning in data.warnings))


if __name__ == "__main__":
    unittest.main()
