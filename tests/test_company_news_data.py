import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "dashboard" / "news-data"
SCRIPT = ROOT / "scripts" / "update_company_news.py"


def load_updater():
    spec = importlib.util.spec_from_file_location("update_company_news", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CompanyNewsDataTests(unittest.TestCase):
    def test_all_companies_have_a_complete_evergreen_explainer(self):
        updater = load_updater()
        for path in sorted(DATA_DIR.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            explainer = payload.get("explainer")
            self.assertIsInstance(explainer, dict, path.name)
            sections = explainer.get("sections", {})
            for key in updater.EXPLAINER_SECTIONS:
                self.assertTrue(sections.get(key), f"{path.name}: {key}")
            source_lines = sections.get("sourcesAndCutoff", [])
            source_text = " ".join(source_lines if isinstance(source_lines, list) else [source_lines])
            self.assertGreaterEqual(source_text.count("http"), 2, f"{path.name}: sourcesAndCutoff")

    def test_fifteen_company_payloads_pass_contract(self):
        updater = load_updater()
        files = sorted(DATA_DIR.glob("*.json"))
        self.assertEqual(len(files), 15)
        for path in files:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(updater.validate_company_payload(payload), [], path.name)

    def test_contract_rejects_duplicate_and_daily_overflow(self):
        updater = load_updater()
        item = {
            "id": "same-id",
            "type": "company",
            "title": "测试资讯",
            "publishedAt": "2026-07-11T08:00:00+08:00",
            "selectedAt": "2026-07-11",
            "sourceName": "公司官网",
            "sourceUrl": "https://example.com/news",
            "summary": "这是用于数据合同测试的事实摘要。",
            "whyImportant": "验证重复资讯会被拒绝。",
            "companyRelevance": "直接涉及测试公司。",
            "watchNext": "观察后续正式公告。",
            "evidenceLevel": "official",
            "tags": ["测试"],
        }
        payload = {
            "schemaVersion": 1,
            "slug": "test",
            "company": "测试公司",
            "industry": "测试行业",
            "updatedAt": "2026-07-11T09:00:00+08:00",
            "explainer": None,
            "items": [item, dict(item)],
        }
        errors = updater.validate_company_payload(payload)
        self.assertTrue(any("重复" in error for error in errors))
        self.assertTrue(any("每日每类最多 1 条" in error for error in errors))

    def test_merge_deduplicates_by_id_and_source_url(self):
        updater = load_updater()
        existing = {"items": [{"id": "a", "sourceUrl": "https://example.com/a"}]}
        intake = {
            "items": [
                {"id": "a", "sourceUrl": "https://example.com/new-a"},
                {"id": "b", "sourceUrl": "https://example.com/a"},
                {"id": "c", "sourceUrl": "https://example.com/c"},
            ]
        }
        merged = updater.merge_intake(existing, intake)
        self.assertEqual([item["id"] for item in merged["items"]], ["a", "c"])

    def test_changxin_has_dram_explainer_and_two_curated_items(self):
        payload = json.loads((DATA_DIR / "changxin.json").read_text(encoding="utf-8"))
        self.assertIn("DRAM", payload["explainer"]["title"])
        self.assertEqual(len(payload["explainer"]["sections"]), 7)
        self.assertEqual({item["type"] for item in payload["items"]}, {"company", "industry"})
        self.assertTrue(all(item["sourceUrl"].startswith("https://") for item in payload["items"]))

    def test_seed_content_keeps_robot_and_ai_chip_industry_signals(self):
        yushu = json.loads((DATA_DIR / "yushu.json").read_text(encoding="utf-8"))
        suiyuan = json.loads((DATA_DIR / "suiyuan.json").read_text(encoding="utf-8"))
        yushu_industry = next(item for item in yushu["items"] if item["type"] == "industry")
        suiyuan_industry = next(item for item in suiyuan["items"] if item["type"] == "industry")
        self.assertIn("人形机器人", yushu_industry["title"])
        self.assertIn("H200", suiyuan_industry["title"])


if __name__ == "__main__":
    unittest.main()
