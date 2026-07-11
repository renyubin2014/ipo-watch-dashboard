#!/usr/bin/env python3
"""Fail closed when the current dashboard/report evidence contract is broken."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_RESEARCH_LABELS = (
    "来源列表",
    "PDF校验",
    "状态核验日期",
    "单位与期间",
    "页码与报告章节",
    "利润机制",
    "非共识判断",
    "反证信号",
)
REQUIRED_OVERVIEW_HEADINGS = (
    "先说结论",
    "IPO与关键事实",
    "公司与行业位置",
    "产品或业务阶梯",
    "上下游关系",
    "财务读数",
    "后续重点跟踪",
)


def load_js_object(path: Path) -> dict:
    match = re.search(r"=\s*(\{.*\})\s*;", path.read_text(encoding="utf-8"), re.S)
    if not match:
        raise ValueError(f"Cannot parse {path}")
    return json.loads(match.group(1))


def is_valid_pdf(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 1024 and path.read_bytes()[:5] == b"%PDF-"
    except OSError:
        return False


def validate_research_sources(html_path: Path, company: str) -> list[str]:
    if not html_path.exists():
        return [f"{company}: 完整调研不存在 {html_path}"]
    text = html_path.read_text(encoding="utf-8", errors="ignore")
    return [f"{company}: 完整调研来源列表缺少 {label}" for label in REQUIRED_RESEARCH_LABELS if label not in text]


def validate_publish_contract(root: Path = ROOT) -> list[str]:
    data = load_js_object(root / "dashboard" / "data.js")
    reports = load_js_object(root / "dashboard" / "reports.js")
    companies = {item["name"] for item in data["items"]}
    errors: list[str] = []
    if len(companies) != 15:
        errors.append(f"发布集合必须为15家，当前为{len(companies)}家")
    if companies != set(reports):
        errors.append(f"数据与报告映射公司集合不一致：仅数据={sorted(companies-set(reports))}；仅映射={sorted(set(reports)-companies)}")
    for company in sorted(companies):
        mapping = reports.get(company, {})
        for key, label in (("overviewUrl", "快速看懂"), ("researchUrl", "完整调研")):
            raw = mapping.get(key)
            if not raw:
                errors.append(f"{company}: 缺少{label}映射")
                continue
            path = (root / "dashboard" / raw).resolve()
            if not path.exists():
                errors.append(f"{company}: {label}文件不存在 {path}")
            elif key == "overviewUrl":
                text = path.read_text(encoding="utf-8", errors="ignore")
                for marker in (*REQUIRED_OVERVIEW_HEADINGS, "最大优势", "最大风险"):
                    if marker not in text:
                        errors.append(f"{company}: 快速看懂缺少 {marker}")
                positions = [text.find(heading) for heading in REQUIRED_OVERVIEW_HEADINGS]
                if all(position >= 0 for position in positions) and positions != sorted(positions):
                    errors.append(f"{company}: 快速看懂章节顺序不符合统一模板")
                if "来源列表" in text:
                    errors.append(f"{company}: 快速看懂不应包含来源列表")
            else:
                errors.extend(validate_research_sources(path, company))
        aliases = []
        for raw in (mapping.get("overviewUrl", ""), mapping.get("researchUrl", "")):
            match = re.search(r"companies/([^/]+)/", raw)
            if match:
                aliases.append(match.group(1))
        if aliases:
            pdfs = list((root / "companies" / aliases[0] / "sources").glob("*.pdf"))
            if pdfs and not any(is_valid_pdf(path) for path in pdfs):
                errors.append(f"{company}: sources 目录没有通过文件头校验的 PDF")
    return errors


def main() -> None:
    errors = validate_publish_contract()
    if errors:
        raise SystemExit("REPORT_QUALITY_GATE_FAILED\n" + "\n".join(errors))
    print("REPORT_QUALITY_GATE_OK companies=15")


if __name__ == "__main__":
    main()
