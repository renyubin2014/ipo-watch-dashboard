import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate_report_quality.py"


class ReportQualityGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("validate_report_quality", MODULE_PATH)
        cls.module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[spec.name] = cls.module
        spec.loader.exec_module(cls.module)

    def test_research_report_requires_all_quality_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "research.html"
            report.write_text('<h2>来源列表</h2><p>PDF校验</p>', encoding="utf-8")
            errors = self.module.validate_research_sources(report, "样本公司")

        self.assertTrue(any("状态核验日期" in error for error in errors))
        self.assertTrue(any("单位与期间" in error for error in errors))
        self.assertTrue(any("页码与报告章节" in error for error in errors))

    def test_pdf_header_validation_rejects_html_disguised_as_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "fake.pdf"
            fake.write_text("<html>blocked</html>", encoding="utf-8")
            self.assertFalse(self.module.is_valid_pdf(fake))


if __name__ == "__main__":
    unittest.main()
