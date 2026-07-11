import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"


def parse_js_object(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"=\s*(\{.*\})\s*;", text, re.S)
    if not match:
        raise ValueError(f"Cannot parse {path}")
    return json.loads(match.group(1))


class CurrentReportIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = parse_js_object(DASHBOARD / "data.js")
        cls.reports = parse_js_object(DASHBOARD / "reports.js")

    def report_path(self, company: str, key: str) -> Path:
        report = self.reports[company]
        return (DASHBOARD / report[key]).resolve()

    def report_text(self, company: str, key: str = "researchUrl") -> str:
        return self.report_path(company, key).read_text(encoding="utf-8", errors="ignore")

    def test_current_report_links_exist(self):
        for item in self.data["items"]:
            report = self.reports.get(item["name"])
            self.assertIsNotNone(report, item["name"])
            for key in ("overviewUrl", "researchUrl"):
                path = self.report_path(item["name"], key)
                self.assertTrue(path.exists(), f"{item['name']} {key} missing: {path}")

    def test_no_known_h1_estimate_sequences_are_used_as_annual_tables(self):
        combined = "\n".join(
            self.report_text(name, key)
            for name in self.reports
            for key in ("overviewUrl", "researchUrl")
        )
        dashboard_data = (DASHBOARD / "data.js").read_text(encoding="utf-8")
        for text in (combined, dashboard_data):
            self.assertNotIn("23,000.00</td><td>26,000.00</td><td>18,028.56", text)
            self.assertNotIn("320,000</td><td>335,000</td><td>282,051.21", text)
            self.assertNotIn("24,000</td><td>28,000</td><td>17,121.45", text)
            self.assertNotIn("23,000.00, 26,000.00, 18,028.56", text)
            self.assertNotIn("320,000, 335,000, 282,051.21", text)
            self.assertNotIn("24,000, 28,000, 17,121.45", text)

    def test_corrected_annual_financials_are_present(self):
        pinzhun = self.report_text("上海频准激光科技股份有限公司")
        self.assertIn("41,791.65</td><td>29,185.72</td><td>14,772.14", pinzhun)
        self.assertIn("15,944.29</td><td>11,561.60</td><td>6,046.36", pinzhun)
        self.assertIn("15,124.57</td><td>11,143.08</td><td>5,780.31", pinzhun)
        self.assertIn("19,108.03</td><td>11,672.75</td><td>6,009.66", pinzhun)

        luozhou = self.report_text("洛阳轴承集团股份有限公司")
        self.assertIn("603,377.30</td><td>467,494.68</td><td>444,129.30", luozhou)
        self.assertIn("52,925.38</td><td>25,094.38</td><td>23,066.37", luozhou)
        self.assertIn("2026H1 预计", luozhou)

        guoyi = self.report_text("国仪量子技术（合肥）股份有限公司")
        self.assertIn("66,619.18</td><td>50,147.22</td><td>39,962.01", guoyi)
        self.assertIn("-579.72</td><td>-7,408.02</td><td>-13,997.07", guoyi)
        self.assertIn("-1,887.80</td><td>-10,423.63</td><td>-16,932.20", guoyi)
        self.assertIn("11,834.03</td><td>-5,023.76</td><td>-13,359.34", guoyi)

    def test_profit_label_is_explicit_not_mixed(self):
        linked_text = "\n".join(
            self.report_text(name, key)
            for name in self.reports
            for key in ("overviewUrl", "researchUrl")
        )
        dashboard_data = (DASHBOARD / "data.js").read_text(encoding="utf-8")
        self.assertNotIn("扣非/净利润", linked_text)
        self.assertNotIn("扣非/净利润", dashboard_data)

    def test_main_business_false_positives_are_removed(self):
        self.assertIn("电子测量仪器研发、制造和销售", self.report_text("中电科思仪科技股份有限公司"))
        self.assertIn("轴承及相关零部件的研发、生产和销售", self.report_text("洛阳轴承集团股份有限公司"))
        self.assertIn("电子产业基础设施综合服务", self.report_text("深圳嘉立创科技集团股份有限公司"))
        linked_text = "\n".join(self.report_text(name) for name in self.reports)
        self.assertNotIn("主营业务为轴承出口", linked_text)
        self.assertNotIn("中信华产业园", linked_text)
        self.assertNotIn("股东回报", linked_text)

    def test_customer_supplier_values_promoted_from_stable_excerpts(self):
        green = self.report_text("苏州绿控传动科技股份有限公司")
        self.assertIn("59.10%", green)
        self.assertIn("16.06%", green)
        makeng = self.report_text("福建马坑矿业股份有限公司")
        self.assertIn("82.53%", makeng)
        self.assertIn("58.41%", makeng)

    def test_changxin_status_and_review_boundary(self):
        changxin = self.report_text("长鑫科技集团股份有限公司")
        self.assertIn("发行中", changxin)
        self.assertIn("2026-07-16", changxin)
        self.assertIn("上市日仍待上市公告书", changxin)
        self.assertIn("待官方 PDF 复核", changxin)

    def test_jlc_board_is_normalized(self):
        item = next(item for item in self.data["items"] if item["name"] == "深圳嘉立创科技集团股份有限公司")
        self.assertEqual(item["board"], "深交所主板")

    def test_yushu_score_removed_and_industry_share_context_added(self):
        for key in ("overviewUrl", "researchUrl"):
            text = self.report_text("宇树科技股份有限公司", key)
            self.assertNotIn("初筛评分", text)
            self.assertIn("可比样本收入占比", text)
            self.assertIn("不等同于全行业市占率", text)
            self.assertIn("35.48%", text)

    def test_non_changxin_reports_have_industry_position_share_context(self):
        generic_exclusions = {
            "长鑫科技集团股份有限公司",
            "宇树科技股份有限公司",
            "上海燧原科技股份有限公司",
        }
        for company in self.reports:
            if company in generic_exclusions:
                continue
            for key in ("overviewUrl", "researchUrl"):
                text = self.report_text(company, key)
                self.assertIn("市占 / 排名 / 占比口径", text, f"{company} {key}")
                self.assertIn("文件未披露精确市占", text, f"{company} {key}")

        for key in ("overviewUrl", "researchUrl"):
            text = self.report_text("上海燧原科技股份有限公司", key)
            self.assertIn("行业格局占比", text)
            self.assertIn("英伟达", text)
            self.assertIn("55.00%", text)
            self.assertIn("燧原科技", text)
            self.assertIn("1.70%", text)


if __name__ == "__main__":
    unittest.main()
