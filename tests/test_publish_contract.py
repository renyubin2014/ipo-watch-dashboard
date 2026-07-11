import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COMPANIES = {
    "上海燧原科技股份有限公司",
    "天博智能科技（山东）股份有限公司",
    "长鑫科技集团股份有限公司",
    "宇树科技股份有限公司",
    "广东中塑新材料股份有限公司",
    "苏州绿控传动科技股份有限公司",
    "洛阳轴承集团股份有限公司",
    "上海频准激光科技股份有限公司",
    "深圳嘉立创科技集团股份有限公司",
    "江苏展芯半导体技术股份有限公司",
    "苏州市贝特利高分子材料股份有限公司",
    "成都超纯应用材料股份有限公司",
    "福建马坑矿业股份有限公司",
    "中电科思仪科技股份有限公司",
    "国仪量子技术（合肥）股份有限公司",
}


def load_js_object(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"=\s*(\{.*\})\s*;", text, re.S)
    if not match:
        raise ValueError(f"Cannot parse {path}")
    return json.loads(match.group(1))


class PublishContractTests(unittest.TestCase):
    def test_dashboard_and_report_mapping_use_same_fifteen_companies(self):
        data = load_js_object(ROOT / "dashboard" / "data.js")
        reports = load_js_object(ROOT / "dashboard" / "reports.js")

        dashboard_companies = {item["name"] for item in data["items"]}
        report_companies = set(reports)

        self.assertEqual(dashboard_companies, EXPECTED_COMPANIES)
        self.assertEqual(report_companies, EXPECTED_COMPANIES)

    def test_jlc_board_is_normalized(self):
        data = load_js_object(ROOT / "dashboard" / "data.js")
        jlc = next(item for item in data["items"] if item["name"] == "深圳嘉立创科技集团股份有限公司")
        self.assertEqual(jlc["board"], "深交所主板")


if __name__ == "__main__":
    unittest.main()
