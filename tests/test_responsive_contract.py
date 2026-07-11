import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "upgrade_current_reports.py"


class ResponsiveContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("upgrade_current_reports_responsive", MODULE_PATH)
        cls.module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[spec.name] = cls.module
        spec.loader.exec_module(cls.module)

    def test_responsive_patch_contains_required_overflow_guards(self):
        css = self.module.responsive_css()

        self.assertIn("min-width:0", css)
        self.assertIn("overflow-wrap:anywhere", css)
        self.assertIn("overflow-x:auto", css)
        self.assertIn("max-width:100%", css)
        self.assertIn("@media(max-width:620px)", css)
        self.assertIn(".toc", css)
        self.assertIn(".content", css)
        self.assertIn("section", css)

    def test_upgrade_injects_responsive_patch_once(self):
        html = "<html><head></head><body><main></main></body></html>"
        upgraded = self.module.inject_responsive_css(html)
        repeated = self.module.inject_responsive_css(upgraded)

        self.assertEqual(repeated.count("report-responsive-fix"), 1)

    def test_dashboard_styles_include_safe_mobile_overflow_contract(self):
        dashboard_css = (ROOT / "dashboard" / "styles.css").read_text(encoding="utf-8")
        mobile_css = (ROOT / "mobile" / "styles.css").read_text(encoding="utf-8")

        self.assertIn("overflow-wrap: anywhere", dashboard_css)
        self.assertIn("min-width: 0", dashboard_css)
        self.assertIn("--nav-end-space", mobile_css)
        self.assertIn("overflow-wrap: anywhere", mobile_css)
        self.assertIn("scrollbar-width: none", mobile_css)


if __name__ == "__main__":
    unittest.main()
