#!/usr/bin/env python3
"""Validate and merge curated company-news payloads for the static dashboard."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "dashboard" / "news-data"
INDEX_PATH = ROOT / "dashboard" / "news-index.js"
ITEM_FIELDS = {
    "id", "type", "title", "publishedAt", "selectedAt", "sourceName",
    "sourceUrl", "summary", "whyImportant", "companyRelevance",
    "watchNext", "evidenceLevel", "tags",
}
EXPLAINER_SECTIONS = {
    "basics", "profitMechanism", "industryNow", "companyImpact",
    "watchMetrics", "misconceptions", "sourcesAndCutoff",
}


def valid_http_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_company_payload(payload: dict) -> list[str]:
    errors: list[str] = []
    for field in ("schemaVersion", "slug", "company", "industry", "updatedAt", "explainer", "items"):
        if field not in payload:
            errors.append(f"缺少字段：{field}")
    items = payload.get("items", [])
    if not isinstance(items, list):
        return errors + ["items 必须是数组"]

    ids: list[str] = []
    urls: list[str] = []
    daily: Counter[tuple[str, str]] = Counter()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"items[{index}] 必须是对象")
            continue
        missing = sorted(ITEM_FIELDS - set(item))
        if missing:
            errors.append(f"items[{index}] 缺少字段：{', '.join(missing)}")
        if item.get("type") not in {"company", "industry"}:
            errors.append(f"items[{index}] type 非法")
        if not valid_http_url(item.get("sourceUrl")):
            errors.append(f"items[{index}] sourceUrl 非法")
        if item.get("id"):
            ids.append(str(item["id"]))
        if item.get("sourceUrl"):
            urls.append(str(item["sourceUrl"]))
        if item.get("selectedAt") and item.get("type"):
            daily[(str(item["selectedAt"]), str(item["type"]))] += 1

    if len(ids) != len(set(ids)) or len(urls) != len(set(urls)):
        errors.append("资讯 ID 或原文 URL 重复")
    if any(count > 1 for count in daily.values()):
        errors.append("每日每类最多 1 条")

    explainer = payload.get("explainer")
    if explainer is not None:
        if not isinstance(explainer, dict):
            errors.append("explainer 必须是对象或 null")
        else:
            for field in ("id", "version", "title", "updatedAt", "asOf", "sections"):
                if field not in explainer:
                    errors.append(f"explainer 缺少字段：{field}")
            sections = explainer.get("sections", {})
            if not isinstance(sections, dict) or not EXPLAINER_SECTIONS.issubset(sections):
                errors.append("explainer 必须包含七个科普板块")
            else:
                empty_sections = sorted(key for key in EXPLAINER_SECTIONS if not sections.get(key))
                if empty_sections:
                    errors.append(f"explainer 板块不能为空：{', '.join(empty_sections)}")
                sources = sections.get("sourcesAndCutoff", [])
                source_text = " ".join(sources if isinstance(sources, list) else [str(sources)])
                if source_text.count("http") < 2:
                    errors.append("explainer 来源板块至少需要 2 个完整 URL")
    return errors


def merge_intake(existing: dict, intake: dict) -> dict:
    merged = deepcopy(existing)
    current = list(merged.get("items", []))
    seen_ids = {str(item.get("id")) for item in current}
    seen_urls = {str(item.get("sourceUrl")) for item in current}
    for item in intake.get("items", []):
        if str(item.get("id")) in seen_ids or str(item.get("sourceUrl")) in seen_urls:
            continue
        current.append(deepcopy(item))
        seen_ids.add(str(item.get("id")))
        seen_urls.add(str(item.get("sourceUrl")))
    merged["items"] = sorted(current, key=lambda item: item.get("publishedAt", ""), reverse=True)
    if intake.get("explainer") is not None:
        merged["explainer"] = deepcopy(intake["explainer"])
    if intake.get("updatedAt"):
        merged["updatedAt"] = intake["updatedAt"]
    return merged


def load_payloads() -> list[dict]:
    payloads = []
    for path in sorted(DATA_DIR.glob("*.json")):
        payloads.append(json.loads(path.read_text(encoding="utf-8")))
    return payloads


def write_index(payloads: list[dict]) -> None:
    index = {}
    for payload in payloads:
        explainer = payload.get("explainer") or {}
        index[payload["company"]] = {
            "slug": payload["slug"],
            "updatedAt": payload["updatedAt"],
            "activeItemIds": [item["id"] for item in payload.get("items", [])],
            "explainerId": explainer.get("id"),
            "explainerVersion": explainer.get("version"),
        }
    INDEX_PATH.write_text(
        "window.IPO_NEWS_INDEX = " + json.dumps(index, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--rebuild-index", action="store_true")
    parser.add_argument("--intake", type=Path)
    args = parser.parse_args()

    if args.intake:
        intake = json.loads(args.intake.read_text(encoding="utf-8"))
        slug = intake["slug"]
        path = DATA_DIR / f"{slug}.json"
        existing = json.loads(path.read_text(encoding="utf-8"))
        merged = merge_intake(existing, intake)
        errors = validate_company_payload(merged)
        if errors:
            raise SystemExit("\n".join(errors))
        path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    payloads = load_payloads()
    all_errors = []
    for payload in payloads:
        all_errors.extend(f"{payload.get('slug', '?')}: {error}" for error in validate_company_payload(payload))
    if all_errors:
        raise SystemExit("\n".join(all_errors))
    if args.rebuild_index or args.intake:
        write_index(payloads)
    if args.validate:
        print(f"validated {len(payloads)} company news payloads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
