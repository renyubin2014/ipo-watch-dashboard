import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "dashboard"


class CompanyNewsPageTests(unittest.TestCase):
    def test_page_has_mobile_shell_and_history_control(self):
        html = (ROOT / "news.html").read_text(encoding="utf-8")
        self.assertIn('name="viewport"', html)
        self.assertIn('id="historyToggle"', html)
        self.assertIn('id="explainer"', html)
        self.assertIn('id="newsList"', html)
        self.assertIn('src="news.js"', html)
        self.assertNotIn("宁缺毋滥", html)
        self.assertNotIn("近 7 日", html)

    def test_script_marks_only_news_items_read(self):
        script = (ROOT / "news.js").read_text(encoding="utf-8")
        self.assertIn("markItemRead", script)
        self.assertNotIn("markExplainerRead", script)
        self.assertIn("historyToggle", script)
        self.assertNotIn("markAllRead", script)
        self.assertIn('rel = "noopener noreferrer"', script)
        self.assertNotIn("近 7 日", script)

    def test_explainer_renders_all_seven_sections(self):
        script = (ROOT / "news.js").read_text(encoding="utf-8")
        self.assertIn('"科普"', script)
        self.assertNotIn("置顶科普 · 最多一篇", script)
        for key in (
            "basics", "profitMechanism", "industryNow", "companyImpact",
            "watchMetrics", "misconceptions", "sourcesAndCutoff",
        ):
            self.assertIn(key, script)

    def test_mobile_css_has_no_horizontal_overflow_and_touch_targets(self):
        styles = (ROOT / "news.css").read_text(encoding="utf-8")
        self.assertIn("overflow-x: hidden", styles)
        self.assertIn("min-height: 44px", styles)
        self.assertIn("font-size: 16px", styles)
        self.assertNotIn("table", styles)


if __name__ == "__main__":
    unittest.main()
