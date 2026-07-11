import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "dashboard"


class CompanyNewsDashboardTests(unittest.TestCase):
    def test_dashboard_loads_news_index_before_app(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('<script src="news-index.js"></script>', html)
        self.assertLess(html.index("news-index.js"), html.index("app.js"))

    def test_company_cards_render_news_link_and_unread_contract(self):
        script = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn("相关热点新闻", script)
        self.assertIn("window.IPO_NEWS_INDEX", script)
        self.assertIn("IPO_NEWS_READ_IDS_V1", script)
        self.assertIn("hasUnreadNews", script)
        self.assertIn("news.html?company=", script)

    def test_mobile_actions_stay_on_one_row_with_small_italic_badge(self):
        styles = (ROOT / "styles.css").read_text(encoding="utf-8")
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", styles)
        self.assertIn(".news-unread", styles)
        self.assertIn("font-style: italic", styles)
        self.assertIn("font-size: 11px", styles)
        self.assertIn("min-height: 44px", styles)


if __name__ == "__main__":
    unittest.main()
