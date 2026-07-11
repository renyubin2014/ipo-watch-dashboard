import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "upgrade_current_reports.py"


class ReportUpgradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("upgrade_current_reports", MODULE_PATH)
        cls.module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[spec.name] = cls.module
        spec.loader.exec_module(cls.module)

    def test_overview_adds_plain_language_strength_and_risk_summary(self):
        html = "<main><section class='grid facts'></section></main>"
        upgraded = self.module.upgrade_overview(
            html,
            "样本公司",
            {"advantages": ["优势证据"], "risks": ["风险机制"]},
        )

        self.assertIn("先说结论", upgraded)
        self.assertIn("最大优势", upgraded)
        self.assertIn("优势证据", upgraded)
        self.assertIn("最大风险", upgraded)
        self.assertIn("风险机制", upgraded)
        self.assertIn('class="conclusion-row advantage"', upgraded)
        self.assertIn('class="conclusion-row risk"', upgraded)
        self.assertNotIn('class="grid two"><div class="box advantage"', upgraded)

    def test_research_adds_judgement_sections_and_source_quality_mapping(self):
        html = '<section id="risk"></section><section id="sources"><h2>10. 来源列表</h2></section>'
        upgraded = self.module.upgrade_research(
            html,
            "样本公司",
            {"profit": "利润由价格驱动", "non_consensus": ["判断一"], "signals": ["价格下降"]},
            {"pdf": "companies/样本/sources/招股书.pdf", "status": "注册生效", "status_date": "2026-07-10"},
        )

        self.assertIn("利润机制", upgraded)
        self.assertIn("非共识判断", upgraded)
        self.assertIn("反证信号", upgraded)
        self.assertIn("来源质量映射", upgraded)
        self.assertIn("PDF校验", upgraded)
        self.assertIn("状态核验日期", upgraded)
        self.assertIn("单位与期间", upgraded)
        self.assertIn("页码与报告章节", upgraded)
        self.assertIn("report-responsive-fix", upgraded)


if __name__ == "__main__":
    unittest.main()
