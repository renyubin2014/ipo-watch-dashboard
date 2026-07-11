#!/usr/bin/env python3
"""Rebuild current overview reports into one stable, concise page contract."""

from __future__ import annotations

import html as html_std
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from lxml import etree, html


ROOT = Path(__file__).resolve().parents[1]
DATA_JS = ROOT / "dashboard" / "data.js"
REPORTS_JS = ROOT / "dashboard" / "reports.js"


STANDARD_CSS = """
<style id="standard-overview-contract">
:root{--std-ink:#172331;--std-muted:#617287;--std-line:#dce6ef;--std-blue:#2f7cf6;--std-green:#19a56d;--std-red:#df554d}
html,body{max-width:100%;overflow-x:hidden}.standard-page{width:min(1120px,calc(100% - 40px));margin:0 auto 72px}.standard-hero{min-height:420px;padding:64px max(20px,calc((100% - 1120px)/2));display:flex;flex-direction:column;justify-content:flex-end;background:linear-gradient(90deg,rgba(12,24,38,.88),rgba(12,24,38,.52)),var(--hero-image) center/cover no-repeat;color:#fff}.standard-hero h1{max-width:850px;margin:10px 0 14px;font-size:clamp(38px,6vw,68px);line-height:1.08}.standard-hero p{max-width:820px;margin:6px 0;line-height:1.65;font-size:clamp(16px,2vw,20px);color:#e6eef7}.standard-tags{display:flex;flex-wrap:wrap;gap:8px}.standard-tags span{padding:6px 10px;border-radius:999px;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.22);font-size:13px}.standard-section{min-width:0;margin-top:20px;padding:24px;border:1px solid var(--std-line);border-radius:18px;background:#fff;box-shadow:0 14px 36px rgba(23,43,67,.07)}.standard-section h2{margin:0 0 16px;font-size:28px;color:var(--std-ink)}.standard-section p,.standard-section li{overflow-wrap:anywhere;line-height:1.72}.standard-conclusion{margin-top:24px}.conclusion-row{display:grid;grid-template-columns:6px minmax(0,1fr);gap:14px;padding:15px 16px;margin:10px 0;border:1px solid var(--std-line);border-radius:14px;background:#fff}.conclusion-row>i{display:block;border-radius:99px;background:var(--std-green)}.conclusion-row.risk>i{background:var(--std-red)}.conclusion-row h3{margin:0 0 6px;font-size:17px}.conclusion-row p{margin:0}.fact-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.fact-card{min-width:0;padding:16px;border:1px solid var(--std-line);border-radius:14px;background:#f8fbff}.fact-card span{display:block;color:var(--std-muted);font-size:12px;font-weight:800}.fact-card strong{display:block;margin-top:8px;color:var(--std-ink);font-size:19px;line-height:1.35;overflow-wrap:anywhere}.standard-body{min-width:0}.standard-body>*{max-width:100%}.standard-body table{display:block;width:100%;max-width:100%;overflow-x:auto}.standard-body img,.standard-body svg,.standard-body canvas,.standard-body input{max-width:100%}.standard-body .source,.standard-body [class*=source]{display:none!important}
@media(max-width:760px){.standard-page{width:min(100% - 24px,1120px)}.standard-hero{min-height:360px;padding:40px 18px}.standard-section{padding:17px}.standard-section h2{font-size:23px}.fact-grid{grid-template-columns:1fr 1fr}.conclusion-row{gap:10px;padding:12px}}
@media(max-width:430px){.fact-grid{grid-template-columns:1fr}}
</style>
"""


def parse_js(path: Path) -> dict[str, Any]:
    match = re.search(r"=\s*(\{.*\})\s*;", path.read_text(encoding="utf-8"), re.S)
    if not match:
        raise ValueError(path)
    return json.loads(match.group(1))


def rounded_integer(value: Decimal) -> str:
    integer = value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"{int(integer):,}"


def format_overview_amount(value: str) -> str:
    text = str(value).strip()
    match = re.fullmatch(r"(-?[\d,]+(?:\.\d+)?)\s*(亿元|亿|万元)", text)
    if not match:
        return text
    number = Decimal(match.group(1).replace(",", ""))
    if match.group(2) in {"亿", "亿元"}:
        number *= Decimal("10000")
    return f"{rounded_integer(number)}万元"


def normalize_display_text(text: str) -> str:
    def money(match: re.Match[str]) -> str:
        return format_overview_amount(match.group(0))

    text = re.sub(r"-?[\d,]+(?:\.\d+)?\s*(?:亿元|亿(?!美元|美金|台|个|片)|万元)", money, text)
    text = re.sub(r"(-?\d+(?:\.\d+)?)\s*%", lambda m: f"{Decimal(m.group(1)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}%", text)
    text = re.sub(r"(-?\d+(?:\.\d+)?)\s*倍", lambda m: f"{Decimal(m.group(1)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}倍", text)
    if "万元" in text:
        def contextual_money(match: re.Match[str]) -> str:
            suffix = text[match.end() :].lstrip()
            if suffix.startswith(("%", "倍")):
                return match.group(0)
            return rounded_integer(Decimal(match.group(1).replace(",", "")))

        text = re.sub(r"(-?[\d,]+\.\d+)", contextual_money, text)
    return text


def normalize_html_text(source: str) -> str:
    tree = html.fromstring(source)
    for node in tree.iter():
        if node.tag in {"style", "script"}:
            continue
        if node.text:
            node.text = normalize_display_text(node.text)
        if node.tail:
            node.tail = normalize_display_text(node.tail)
    return "<!doctype html>" + etree.tostring(tree, encoding="unicode", method="html")


def first_sentences(text: str, limit: int = 1, max_chars: int = 90) -> str:
    clean = re.sub(r"\s+", "", text or "").strip()
    if not clean:
        return ""
    parts = [part for part in re.split(r"(?<=[。！？])", clean) if part]
    result = "".join(parts[:limit]) or clean
    return result if len(result) <= max_chars else result[: max_chars - 1] + "…"


def hero_intro(tree: html.HtmlElement, item: dict[str, Any]) -> str:
    candidates = tree.xpath("//*[contains(concat(' ',normalize-space(@class),' '),' hero ')]//p")
    for node in candidates:
        text = first_sentences(node.text_content(), 1, 88)
        if text:
            return text
    return f"公司所属{item.get('industry', '相关行业')}，主营业务与产品结构以完整调研披露为准。"


def section_content(tree: html.HtmlElement, keywords: list[str]) -> str:
    results: list[str] = []
    for node in tree.xpath("//section|//article"):
        headings = node.xpath(".//h2|.//h3")
        if not headings:
            continue
        title = re.sub(r"\s+", "", headings[0].text_content())
        if not any(keyword in title for keyword in keywords):
            continue
        clone = html.fromstring(etree.tostring(node, encoding="unicode", method="html"))
        for old_heading in clone.xpath(".//h2|.//h3")[:1]:
            old_heading.tag = "h3"
        for source in clone.xpath(".//*[contains(@class,'source')]"):
            parent = source.getparent()
            if parent is not None:
                parent.remove(source)
        results.append("".join(etree.tostring(child, encoding="unicode", method="html") for child in clone))
        if len(results) >= 3:
            break
    return "".join(results) if results else '<p class="standard-missing">本模块的确定性信息仍需结合完整调研复核。</p>'


def fact_value(item: dict[str, Any], key: str, fallback: str) -> str:
    value = item.get("metrics", {}).get(key) or fallback
    return first_sentences(str(value), 1, 72)


def standardize_overview_html(source: str, item: dict[str, Any], analysis: dict[str, Any], hero_url: str) -> str:
    tree = html.fromstring(source)
    for old_style in tree.xpath("//style[@id='standard-overview-contract']"):
        parent = old_style.getparent()
        if parent is not None:
            parent.remove(old_style)
    head = tree.find("head")
    head_html = etree.tostring(head, encoding="unicode", method="html") if head is not None else "<head></head>"
    head_html = head_html.replace("</head>", STANDARD_CSS + "</head>")
    advantage = analysis.get("advantages", ["核心优势仍需复核"])[0]
    risk = analysis.get("risks", ["核心风险仍需复核"])[0]
    intro = hero_intro(tree, item)
    verification = first_sentences(f"核心验证点：{advantage}；主要风险：{risk}", 1, 100)
    facts = [
        ("IPO状态", item.get("status", "待补充")),
        ("拟募资", fact_value(item, "fundraisingFit", "待补充")),
        ("最新收入", fact_value(item, "revenueGrowth", "待补充")),
        ("最新利润", fact_value(item, "profitQuality", "待补充")),
        ("待确认", item.get("expectedListingTime", "待补充")),
    ]
    fact_html = "".join(f'<div class="fact-card"><span>{html_std.escape(str(label))}</span><strong>{html_std.escape(str(value))}</strong></div>' for label, value in facts)
    slots = [
        ("company-position", "公司与行业位置", ["行业位置", "行业格局", "数据读图", "市场位置", "可比样本"]),
        ("business-ladder", "产品或业务阶梯", ["业务/产品阶梯", "产品阶梯", "业务阶梯", "业务结构"]),
        ("value-chain", "上下游关系", ["上下游", "上中下游", "产业链", "客户结构", "算力链"]),
        ("finance-overview", "财务读数", ["核心财务", "财务读数", "三年核心数据", "财务分析", "数据读图", "利润为什么"]),
        ("tracking", "后续重点跟踪", ["后续只盯", "后续重点", "跟踪清单"]),
    ]
    slot_html = "".join(
        f'<section id="{slot_id}" class="standard-section"><h2>{title}</h2><div class="standard-body">{section_content(tree, keywords)}</div></section>'
        for slot_id, title, keywords in slots
    )
    scripts_html = "".join(etree.tostring(node, encoding="unicode", method="html") for node in tree.xpath("//body//script"))
    result = f"""<!doctype html><html lang="zh-CN">{head_html}<body>
<header class="standard-hero" style="--hero-image:url('{html_std.escape(hero_url, quote=True)}')"><div class="standard-tags"><span>{html_std.escape(str(item.get('board','待补充')))}</span><span>{html_std.escape(str(item.get('status','待补充')))}</span></div><h1>{html_std.escape(str(item['name']))}</h1><p>{html_std.escape(intro)}</p><p>{html_std.escape(verification)}</p></header>
<main class="standard-page"><section id="conclusion" class="standard-section standard-conclusion"><h2>先说结论</h2><div class="conclusion-row advantage"><i></i><div><h3>最大优势</h3><p>{html_std.escape(str(advantage))}</p></div></div><div class="conclusion-row risk"><i></i><div><h3>最大风险</h3><p>{html_std.escape(str(risk))}</p></div></div></section>
<section id="ipo-facts" class="standard-section"><h2>IPO与关键事实</h2><div class="fact-grid">{fact_html}</div></section>{slot_html}</main>{scripts_html}</body></html>"""
    return normalize_html_text(result)


def next_path(path: Path) -> Path:
    match = re.match(r"(.+)-v(\d+)\.html$", path.name)
    if not match:
        return path.with_name(path.stem + "-standard-v1.html")
    return path.with_name(f"{match.group(1)}-v{int(match.group(2)) + 1}.html")


def latest_unstandardized_overview(current: Path) -> Path:
    candidates = sorted(
        current.parent.glob("*-overview-v*.html"),
        key=lambda path: int(re.search(r"-v(\d+)\.html$", path.name).group(1)) if re.search(r"-v(\d+)\.html$", path.name) else 0,
        reverse=True,
    )
    for candidate in candidates:
        if "standard-page" not in candidate.read_text(encoding="utf-8", errors="ignore"):
            return candidate
    return current


def main() -> None:
    from upgrade_current_reports import ANALYSIS

    data = parse_js(DATA_JS)
    items = {item["name"]: item for item in data["items"]}
    reports = parse_js(REPORTS_JS)
    for company, mapping in reports.items():
        current = (ROOT / "dashboard" / mapping["overviewUrl"]).resolve()
        target = next_path(current)
        base = latest_unstandardized_overview(current)
        asset = mapping.get("assetUrl") or "../dashboard/assets/ipo-hero.png"
        asset_path = (ROOT / "dashboard" / asset).resolve()
        hero_url = Path(asset_path).relative_to(target.parent, walk_up=True).as_posix()
        output = standardize_overview_html(base.read_text(encoding="utf-8"), items[company], ANALYSIS[company], hero_url)
        target.write_text(output, encoding="utf-8")
        mapping["overviewUrl"] = "../" + str(target.relative_to(ROOT))
    REPORTS_JS.write_text("window.IPO_COMPANY_REPORTS = " + json.dumps(reports, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")


if __name__ == "__main__":
    main()
