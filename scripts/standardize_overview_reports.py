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

LATEST_FINANCIAL_OVERRIDES: dict[str, list[dict[str, Any]]] = {
    "天博智能科技（山东）股份有限公司": [
        {"period": "2026Q1", "metric": "收入", "values": [Decimal("40697.16")], "detail": "同比下降6.42%", "estimate": False},
        {"period": "2026Q1", "metric": "利润", "values": [Decimal("6928.13")], "detail": "扣非归母净利润同比下降14.42%", "estimate": False},
        {"period": "2026Q1", "metric": "经营现金流", "values": [Decimal("4802.71")], "detail": "同比增长155.15%", "estimate": False},
    ],
    "宇树科技股份有限公司": [
        {"period": "2026Q1", "metric": "收入", "display": "同比增长68.49%", "detail": "收入仍增长，但较2025全年增速回落", "estimate": False},
        {"period": "2026Q1", "metric": "利润", "display": "同比下降52.55%", "detail": "扣非后归母净利润同比下降", "estimate": False},
    ],
    "洛阳轴承集团股份有限公司": [
        {"period": "2026H1", "metric": "收入", "values": [Decimal("320000"), Decimal("335000")], "detail": "2025H1为282,051万元", "estimate": True},
    ],
    "上海频准激光科技股份有限公司": [
        {"period": "2026H1", "metric": "收入", "values": [Decimal("23000"), Decimal("26000")], "detail": "2025H1为18,029万元", "estimate": True},
    ],
    "国仪量子技术（合肥）股份有限公司": [
        {"period": "2026H1", "metric": "收入", "values": [Decimal("24000"), Decimal("28000")], "detail": "2025H1为17,121万元", "estimate": True},
    ],
}

FUNDRAISING_OVERRIDES = {
    "上海燧原科技股份有限公司": "600,000万元",
    "天博智能科技（山东）股份有限公司": "205,663万元",
    "宇树科技股份有限公司": "420,171万元",
    "广东中塑新材料股份有限公司": "64,549万元",
    "苏州绿控传动科技股份有限公司": "158,000万元",
    "洛阳轴承集团股份有限公司": "180,000万元",
    "上海频准激光科技股份有限公司": "141,030万元",
    "深圳嘉立创科技集团股份有限公司": "420,000万元",
    "江苏展芯半导体技术股份有限公司": "88,950万元",
    "苏州市贝特利高分子材料股份有限公司": "76,266万元",
    "成都超纯应用材料股份有限公司": "112,468万元",
    "福建马坑矿业股份有限公司": "100,000万元",
    "中电科思仪科技股份有限公司": "150,000万元",
    "国仪量子技术（合肥）股份有限公司": "116,895万元",
    "长鑫科技集团股份有限公司": "发行募资规模尚未最终确定",
}

ANNUAL_FINANCIAL_OVERRIDES = {
    "天博智能科技（山东）股份有限公司": {"经营现金流": [Decimal("23141.81"), Decimal("20719.25"), Decimal("16549.52")]},
    "深圳嘉立创科技集团股份有限公司": {"经营现金流": [Decimal("190428.66"), Decimal("149935.69"), Decimal("156685.78")]},
    "苏州市贝特利高分子材料股份有限公司": {"经营现金流": [Decimal("-40299.06"), Decimal("-16444.00"), Decimal("-3750.65")]},
}

OVERVIEW_TEXT_REPLACEMENTS = {
    "天博智能科技（山东）股份有限公司": {"经营现金流 待补充，现金流/利润为 待补充": "经营现金流23,142万元，现金流/利润为0.66倍"},
    "深圳嘉立创科技集团股份有限公司": {"经营现金流 待补充，现金流/利润为 待补充": "经营现金流190,429万元，现金流/利润为1.55倍"},
    "苏州市贝特利高分子材料股份有限公司": {"经营现金流 待补充，现金流/利润为 待补充": "经营现金流-40,299万元，现金流/利润为-3.47倍"},
}


STANDARD_CSS = """
<style id="standard-overview-contract">
:root{--std-ink:#172331;--std-muted:#617287;--std-line:#dce6ef;--std-blue:#2f7cf6;--std-green:#19a56d;--std-red:#df554d}
html,body{max-width:100%;overflow-x:hidden}.standard-page{width:min(1120px,calc(100% - 40px));margin:0 auto 72px}.standard-hero{min-height:420px;padding:64px max(20px,calc((100% - 1120px)/2));display:flex;flex-direction:column;justify-content:flex-end;background:linear-gradient(90deg,rgba(12,24,38,.88),rgba(12,24,38,.52)),var(--hero-image) center/cover no-repeat;color:#fff}.standard-hero h1{max-width:850px;margin:10px 0 14px;font-size:clamp(38px,6vw,68px);line-height:1.08}.standard-hero p{max-width:820px;margin:6px 0;line-height:1.65;font-size:clamp(16px,2vw,20px);color:#e6eef7}.standard-tags{display:flex;flex-wrap:wrap;gap:8px}.standard-tags span{padding:6px 10px;border-radius:999px;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.22);font-size:13px}.standard-section{min-width:0;margin-top:20px;padding:24px;border:1px solid var(--std-line);border-radius:18px;background:#fff;box-shadow:0 14px 36px rgba(23,43,67,.07)}.standard-section h2{margin:0 0 16px;font-size:28px;color:var(--std-ink)}.standard-section p,.standard-section li{overflow-wrap:anywhere;line-height:1.72}.standard-conclusion{margin-top:24px}.conclusion-row{display:grid;grid-template-columns:6px minmax(0,1fr);gap:14px;padding:15px 16px;margin:10px 0;border:1px solid var(--std-line);border-radius:14px;background:#fff}.conclusion-row>i{display:block;border-radius:99px;background:var(--std-green)}.conclusion-row.risk>i{background:var(--std-red)}.conclusion-row h3{margin:0 0 6px;font-size:17px}.conclusion-row p{margin:0}.fact-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.fact-card{min-width:0;padding:16px;border:1px solid var(--std-line);border-radius:14px;background:#f8fbff}.fact-card span{display:block;color:var(--std-muted);font-size:12px;font-weight:800}.fact-card strong{display:block;margin-top:8px;color:var(--std-ink);font-size:19px;line-height:1.35;overflow-wrap:anywhere}.fact-card small{display:block;margin-top:7px;color:var(--std-muted);font-size:12px;line-height:1.5}.standard-body{min-width:0}.standard-body>*{max-width:100%}.standard-body table{display:block;width:100%;max-width:100%;overflow-x:auto}.standard-body img,.standard-body svg,.standard-body canvas,.standard-body input{max-width:100%}.standard-body .source,.standard-body [class*=source]{display:none!important}.finance-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.finance-heading h2{margin-bottom:0}.finance-unit{color:var(--std-muted);font-size:13px}.finance-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:18px}.finance-card{min-width:0;padding:16px;border:1px solid var(--std-line);border-radius:14px;background:#f8fbff}.finance-card.latest{background:#eef6ff;border-color:#b8d5ff}.finance-card.estimate{background:#fff8e9;border-color:#efd59a}.finance-card .tag{display:inline-block;padding:4px 8px;border-radius:99px;background:#e4edf7;color:#466078;font-size:11px;font-weight:800}.finance-card .period{display:block;margin-top:10px;color:var(--std-muted);font-size:12px}.finance-card strong{display:block;margin-top:5px;font-size:22px;line-height:1.3}.finance-card small{display:block;margin-top:7px;color:var(--std-muted);line-height:1.5}.finance-note{margin:14px 0 0;color:var(--std-muted);font-size:13px}
@media(max-width:760px){.standard-page{width:min(100% - 24px,1120px)}.standard-hero{min-height:360px;padding:40px 18px}.standard-section{padding:17px}.standard-section h2{font-size:23px}.fact-grid,.finance-grid{grid-template-columns:1fr 1fr}.conclusion-row{gap:10px;padding:12px}}
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


def prune_position_content(fragment: str) -> str:
    wrapper = html.fragment_fromstring(fragment, create_parent="div")
    for table in wrapper.xpath(".//table"):
        parent = table.getparent()
        if parent is not None:
            parent.remove(table)
    return "".join(etree.tostring(child, encoding="unicode", method="html") for child in wrapper)


def number_from_text(value: str) -> Decimal | None:
    match = re.search(r"-?[\d,]+(?:\.\d+)?", value or "")
    return Decimal(match.group(0).replace(",", "")) if match else None


def amount_label(value: Decimal | None, *, loss_word: bool = False) -> str:
    if value is None:
        return "待补充"
    if loss_word and value < 0:
        return f"亏损{rounded_integer(abs(value))}万元"
    return f"{rounded_integer(value)}万元"


def extract_financial_rows(research_source: str) -> dict[str, Any]:
    if not research_source:
        return {"annual": {}, "latest": []}
    tree = html.fromstring(research_source)
    annual: dict[str, list[Decimal]] = {}
    latest: list[dict[str, Any]] = []
    annual_labels = {"营业收入", "净利润", "归母净利润", "扣非归母净利润", "扣非后归母净利润", "经营现金流", "经营现金流净额"}
    finance_sections = []
    for section in tree.xpath("//section"):
        headings = section.xpath(".//h2[1]")
        if headings and any(keyword in headings[0].text_content() for keyword in ("财务", "最新经营读数")):
            finance_sections.append(section)
    rows = [row for section in finance_sections for row in section.xpath(".//tr")] or tree.xpath("//tr")
    for row in rows:
        cells = [re.sub(r"\s+", " ", cell.text_content()).strip() for cell in row.xpath("./th|./td")]
        if len(cells) < 2:
            continue
        label = cells[0]
        if label in annual_labels and len(cells) >= 4:
            values = [number_from_text(value) for value in cells[1:4]]
            if all(value is not None for value in values):
                annual[label] = [value for value in values if value is not None]
        if not label.startswith("2026"):
            continue
        value_text = cells[1]
        row_text = " ".join(cells)
        if any(marker in row_text for marker in ("待官方 PDF 复核", "媒体转述", "FT 称", "WSJ 称")):
            continue
        values = [Decimal(value.replace(",", "")) for value in re.findall(r"-?[\d,]+(?:\.\d+)?", value_text)]
        if not values:
            continue
        metric = "收入" if "收入" in label else "利润" if "利润" in label else "经营现金流" if "现金流" in label else label
        period_match = re.search(r"2026(?:Q[1-4]|H[12]|年(?:一季度|上半年|前三季度)?)", label)
        latest.append({
            "period": period_match.group(0) if period_match else "2026最新期间",
            "metric": metric,
            "values": values[:2] if "至" in value_text else values[:1],
            "detail": re.sub(r"^-?[\d,]+(?:\.\d+)?\s*(?:至\s*-?[\d,]+(?:\.\d+)?)?\s*万元[，,]?", "", value_text).strip(),
            "estimate": "预计" in label,
        })
    return {"annual": annual, "latest": latest}


def preferred_profit(annual: dict[str, list[Decimal]]) -> tuple[str, list[Decimal]] | None:
    for label in ("扣非后归母净利润", "扣非归母净利润", "归母净利润", "净利润"):
        if label in annual:
            return label, annual[label]
    return None


def latest_metric(financials: dict[str, Any], metric: str, *, actual_only: bool = False) -> dict[str, Any] | None:
    rows = [row for row in financials["latest"] if row["metric"] == metric and (not actual_only or not row["estimate"])]
    return rows[0] if rows else None


def fact_card(label: str, main: str, detail: str = "") -> str:
    detail_html = f"<small>{html_std.escape(detail)}</small>" if detail else ""
    return f'<div class="fact-card"><span>{html_std.escape(label)}</span><strong>{html_std.escape(main)}</strong>{detail_html}</div>'


def build_fact_cards(item: dict[str, Any], financials: dict[str, Any]) -> str:
    annual = financials["annual"]
    revenue = latest_metric(financials, "收入", actual_only=True) or latest_metric(financials, "收入")
    profit = latest_metric(financials, "利润", actual_only=True) or latest_metric(financials, "利润")
    if revenue:
        revenue_value = revenue.get("display") or "至".join(amount_label(value) for value in revenue["values"])
        revenue_main = f'{revenue["period"]}{"预计" if revenue["estimate"] else ""}｜{revenue_value}'
        revenue_detail = revenue["detail"].replace("同比 +", "同比增长").replace("同比+", "同比增长")
    elif annual.get("营业收入"):
        revenue_main = f'2025｜{amount_label(annual["营业收入"][0])}'
        revenue_detail = "最新披露仍为2025年度"
    else:
        revenue_main, revenue_detail = "官方数据尚待复核", "尚未取得可稳定复核的招股书财务原文"
    if profit:
        profit_value = profit.get("display") or "至".join(amount_label(value, loss_word=True) for value in profit["values"])
        profit_main = f'{profit["period"]}{"预计" if profit["estimate"] else ""}｜{profit_value}'
        profit_detail = profit["detail"].replace("同比 +", "同比增长").replace("同比+", "同比增长").replace("扩大 ", "扩大")
    else:
        picked = preferred_profit(annual)
        if picked:
            profit_main = f'2025｜{amount_label(picked[1][0], loss_word=True)}'
            profit_detail = f'{picked[0]}；最新披露仍为2025年度'
        else:
            profit_main, profit_detail = "官方数据尚待复核", "尚未取得可稳定复核的招股书财务原文"
    company = str(item.get("name", ""))
    fundraising = FUNDRAISING_OVERRIDES.get(company) or fact_value(item, "fundraisingFit", "募资规模尚未披露")
    listing = str(item.get("expectedListingTime", "") or "")
    if any(marker in listing for marker in ("待补充", "待确认")) or not listing:
        listing = "发行价与上市日期尚未披露"
    return "".join([
        fact_card("IPO状态", str(item.get("status", "待补充"))),
        fact_card("拟募资", fundraising),
        fact_card("最新收入", revenue_main, revenue_detail),
        fact_card("最新利润", profit_main, profit_detail),
        fact_card("发行安排", listing),
    ])


def build_finance_overview(financials: dict[str, Any]) -> str:
    annual = financials["annual"]
    picked_profit = preferred_profit(annual)
    cards: list[str] = []
    metrics = (("营业收入", annual.get("营业收入")), ("利润", picked_profit[1] if picked_profit else None), ("经营现金流", annual.get("经营现金流") or annual.get("经营现金流净额")))
    for metric, values in metrics:
        if not values:
            continue
        detail = "；".join(f"{year}年 {amount_label(value, loss_word=metric == '利润')}" for year, value in zip((2025, 2024, 2023), values))
        cards.append(f'<div class="finance-card"><span class="tag">历史年度</span><span class="period">{metric}</span><strong>{amount_label(values[0], loss_word=metric == "利润")}</strong><small>{html_std.escape(detail)}</small></div>')
    for row in financials["latest"]:
        value = row.get("display") or "至".join(amount_label(item, loss_word=row["metric"] == "利润") for item in row["values"])
        kind = "公司预计" if row["estimate"] else "最新实际"
        css = "estimate" if row["estimate"] else "latest"
        cards.append(f'<div class="finance-card {css}"><span class="tag">{kind}</span><span class="period">{html_std.escape(row["period"])} · {html_std.escape(row["metric"])}</span><strong>{html_std.escape(value)}</strong><small>{html_std.escape(row["detail"] or "以完整调研可追溯数据为准")}</small></div>')
    note = "" if financials["latest"] else '<p class="finance-note">最新披露仍为2025年度；未取得可追溯的2026年财务数据，不作推算。</p>'
    return f'<div class="finance-heading"><h2>财务读数</h2><span class="finance-unit">单位：万元；百分比除外</span></div><div class="finance-grid">{"".join(cards)}</div>{note}'


def fact_value(item: dict[str, Any], key: str, fallback: str) -> str:
    value = item.get("metrics", {}).get(key) or fallback
    return first_sentences(str(value), 1, 72)


def standardize_overview_html(source: str, item: dict[str, Any], analysis: dict[str, Any], hero_url: str, research_source: str = "") -> str:
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
    financials = extract_financial_rows(research_source)
    financials["annual"].update(ANNUAL_FINANCIAL_OVERRIDES.get(str(item.get("name")), {}))
    overrides = LATEST_FINANCIAL_OVERRIDES.get(str(item.get("name")), [])
    if overrides:
        financials["latest"] = overrides + financials["latest"]
    fact_html = build_fact_cards(item, financials)
    slots = [
        ("business-ladder", "产品或业务阶梯", ["业务/产品阶梯", "产品阶梯", "业务阶梯", "业务结构"]),
        ("value-chain", "上下游关系", ["上下游", "上中下游", "产业链", "客户结构", "算力链"]),
        ("tracking", "后续重点跟踪", ["后续只盯", "后续重点", "跟踪清单"]),
    ]
    position_html = prune_position_content(section_content(tree, ["行业位置", "行业格局", "数据读图", "市场位置", "可比样本"]))
    slot_html = f'<section id="company-position" class="standard-section"><h2>公司与行业位置</h2><div class="standard-body">{position_html}</div></section>' + "".join(
        f'<section id="{slot_id}" class="standard-section"><h2>{title}</h2><div class="standard-body">{section_content(tree, keywords)}</div></section>'
        for slot_id, title, keywords in slots
    )
    tracking_marker = '<section id="tracking"'
    tracking_index = slot_html.find(tracking_marker)
    finance_html = f'<section id="finance-overview" class="standard-section">{build_finance_overview(financials)}</section>'
    slot_html = slot_html[:tracking_index] + finance_html + slot_html[tracking_index:] if tracking_index >= 0 else slot_html + finance_html
    scripts_html = "".join(etree.tostring(node, encoding="unicode", method="html") for node in tree.xpath("//body//script"))
    result = f"""<!doctype html><html lang="zh-CN">{head_html}<body>
<header class="standard-hero" style="--hero-image:url('{html_std.escape(hero_url, quote=True)}')"><div class="standard-tags"><span>{html_std.escape(str(item.get('board','待补充')))}</span><span>{html_std.escape(str(item.get('status','待补充')))}</span></div><h1>{html_std.escape(str(item['name']))}</h1><p>{html_std.escape(intro)}</p><p>{html_std.escape(verification)}</p></header>
<main class="standard-page"><section id="conclusion" class="standard-section standard-conclusion"><h2>先说结论</h2><div class="conclusion-row advantage"><i></i><div><h3>最大优势</h3><p>{html_std.escape(str(advantage))}</p></div></div><div class="conclusion-row risk"><i></i><div><h3>最大风险</h3><p>{html_std.escape(str(risk))}</p></div></div></section>
<section id="ipo-facts" class="standard-section"><h2>IPO与关键事实</h2><div class="fact-grid">{fact_html}</div></section>{slot_html}</main>{scripts_html}</body></html>"""
    company = str(item.get("name", ""))
    for old, new in OVERVIEW_TEXT_REPLACEMENTS.get(company, {}).items():
        result = result.replace(old, new)
    result = result.replace("待补充（注册生效；未见发行/上市公告）", "发行价与上市日期尚未披露")
    result = result.replace("待补充（关注发行/上市公告）", "发行价与上市日期尚未披露")
    result = result.replace("发行价、发行市值、上市日期仍为 待补充", "发行价、发行市值和上市日期尚未披露")
    result = result.replace("占比 待补充；金额 待补充", "集中度合计未在招股书概览页单列")
    result = result.replace("金额 待补充", "金额未在本页单独汇总")
    result = result.replace("待补充", "尚未披露")
    result = result.replace("待明确", "尚未披露")
    result = result.replace("待确认", "尚未披露")
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
        research = (ROOT / "dashboard" / mapping["researchUrl"]).resolve()
        output = standardize_overview_html(base.read_text(encoding="utf-8"), items[company], ANALYSIS[company], hero_url, research.read_text(encoding="utf-8"))
        target.write_text(output, encoding="utf-8")
        mapping["overviewUrl"] = "../" + str(target.relative_to(ROOT))
    REPORTS_JS.write_text("window.IPO_COMPANY_REPORTS = " + json.dumps(reports, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")


if __name__ == "__main__":
    main()
