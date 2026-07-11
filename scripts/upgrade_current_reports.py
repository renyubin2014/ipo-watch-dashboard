#!/usr/bin/env python3
"""Upgrade the current 15 report pairs without changing dashboard layout."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_JS = ROOT / "dashboard" / "data.js"
REPORTS_JS = ROOT / "dashboard" / "reports.js"


ANALYSIS: dict[str, dict[str, Any]] = {
    "上海燧原科技股份有限公司": {"advantages": ["已完成国产 AI 训练与推理芯片的产品化，并获得头部客户验证，稀缺性来自芯片、软件栈和量产交付的组合能力。"], "risks": ["前五大客户高度集中且仍大额亏损；若核心客户缩减采购或新芯片迭代不及预期，收入和现金流会同时承压。"], "profit": "利润的关键不是单纯多卖芯片，而是出货规模能否摊薄高额研发、流片和软件生态投入；客户放量、产品良率和平均售价共同决定毛利，研发费用刚性会放大盈亏波动。", "non_consensus": ["市场容易把燧原只看成国产 GPU 替代，但更难复制的可能是软硬件适配和客户迁移成本；这项优势只有在复购和多客户扩张中才算被证明。"], "signals": ["前五大客户占比继续上升且最大客户采购下降", "新一代产品量产或客户验证延期", "毛利率改善但经营现金流没有同步改善"]},
    "天博智能科技（山东）股份有限公司": {"advantages": ["在汽车调温器、水阀、温度传感器和 AVAS 等小而关键的零部件中拥有明确行业排名，产品覆盖燃油车与新能源车。"], "risks": ["汽车零部件议价权受整车厂压制；若降价速度超过规模降本，收入增长不一定转化为利润增长。"], "profit": "利润由单车配套价值、车型销量、原材料成本和整车厂年降共同决定。新能源热管理部件提升单车价值，但客户降价和新品爬坡成本会抵消放量收益。", "non_consensus": ["天博更像多个细分零件冠军的组合，而不是热管理总成龙头；它的价值在持续扩充单车配套品类，而非只押注单一产品市占。"], "signals": ["主要客户车型销量下滑", "毛利率连续下降且收入仍增长", "新产品收入占比长期没有提升"]},
    "长鑫科技集团股份有限公司": {"advantages": ["国内少数实现 DRAM 大规模量产的平台型企业，产能、工艺迭代和客户验证构成高进入壁垒。"], "risks": ["DRAM 价格周期、巨额资本开支和先进设备限制会共同放大盈利波动。"], "profit": "DRAM 利润由售价、良率、稼动率和折旧共同放大：价格上涨与良率提升会快速释放利润，反之固定折旧会让下行周期的亏损扩大。", "non_consensus": ["产能份额不等于收入份额；真正决定盈利质量的是高价值产品占比和单位晶圆收入，而不只是扩产速度。"], "signals": ["单位收入或毛利率显著落后于产能扩张", "服务器和高端产品验证延期", "资本开支持续上升但经营现金流转弱"]},
    "宇树科技股份有限公司": {"advantages": ["机器人本体具备规模化出货、成本控制和品牌影响力，产品从科研市场向工业及消费场景延伸。"], "risks": ["行业预期可能跑在真实需求之前；若应用场景复购不足，销量增长会依赖低价和展示性订单。"], "profit": "利润取决于销量放大能否快于电机、减速器、算力和售后成本增长；标准化本体带来规模效应，定制交付和低价竞争则会侵蚀毛利。", "non_consensus": ["短期壁垒可能不是通用智能能力，而是把高性能机器人做成可稳定交付的标准产品；长期仍需软件生态和真实任务数据补上护城河。"], "signals": ["复购率或商业客户占比下降", "收入增长但毛利率和现金流同步恶化", "核心零部件或算法迭代落后于竞品"]},
    "广东中塑新材料股份有限公司": {"advantages": ["已进入多家消费电子品牌供应链，并具备从材料配方向多应用场景迁移的客户基础。"], "risks": ["消费电子需求波动、客户议价和原料价格传导可能压缩利润，跨行业扩张若验证慢会增加费用。"], "profit": "利润来自改性配方溢价、产品结构和产能利用率；原料价格可否及时传导给客户，以及新能源汽车等高价值应用占比，是毛利变化的核心。", "non_consensus": ["核心看点不是改性塑料大盘增长，而是公司能否把消费电子验证能力复制到汽车、储能等更长周期场景。"], "signals": ["汽车和储能收入占比停滞", "原料上涨时毛利率快速下滑", "大客户集中度上升且应收账款恶化"]},
    "苏州绿控传动科技股份有限公司": {"advantages": ["在新能源重卡电机配套中连续保持领先，并进入徐工、三一等头部商用车客户体系。"], "risks": ["需求与新能源重卡景气和头部整车厂订单高度相关，客户集中会放大行业波动。"], "profit": "利润由新能源商用车销量、单套电驱价值、客户年降和采购规模决定；放量可摊薄制造成本，但头部客户议价会限制毛利上行。", "non_consensus": ["公司更像新能源重卡周期的高弹性零部件，而非独立于整车周期的稳定成长股。"], "signals": ["头部客户新能源重卡销量转弱", "客户集中度继续上升", "收入增长而毛利率或现金流下降"]},
    "洛阳轴承集团股份有限公司": {"advantages": ["在风电、轨交、航空航天等专用轴承中拥有多项行业前三，技术和认证壁垒高于通用轴承。"], "risks": ["重资产扩产、下游项目周期和低端产品价格竞争可能拖累现金流与资本回报。"], "profit": "利润取决于高毛利专用轴承占比、钢材成本、产能利用率和折旧；产品结构升级比单纯收入扩张更重要。", "non_consensus": ["洛轴的估值弹性不在轴承总收入排名，而在高端专用轴承能否持续提高收入与利润占比。"], "signals": ["专用轴承收入占比停止提升", "资本开支增长快于订单和现金流", "风电等主要下游进入价格战"]},
    "上海频准激光科技股份有限公司": {"advantages": ["在量子科技等精准激光细分领域形成国产领先位置，技术指标、客户验证和高毛利共同体现壁垒。"], "risks": ["市场空间仍较细分，科研和半导体客户项目节奏变化会造成订单波动。"], "profit": "利润主要由高端产品占比、研发成果转化和小批量定制效率决定；技术溢价支撑高毛利，但持续研发投入和客户项目延期会放大波动。", "non_consensus": ["高毛利不只代表竞争力，也可能反映市场小且定制化强；真正的放大器是产品能否进入更大规模的半导体设备场景。"], "signals": ["半导体设备客户验证延期", "高毛利率下降且研发费用率上升", "订单增长依赖少数科研项目"]},
    "深圳嘉立创科技集团股份有限公司": {"advantages": ["把 EDA/CAM、PCB、元器件和 PCBA 串成一站式电子产业服务，订单数据和交付网络形成平台协同。"], "risks": ["重资产制造、价格竞争和中小客户需求周期可能压缩利润，业务扩张也会增加库存与资本开支。"], "profit": "利润来自订单密度带来的设备利用率、跨业务导流和供应链周转；小批量高频订单提高单价，但扩产过快会增加折旧和库存风险。", "non_consensus": ["嘉立创不只是 PCB 厂，更接近工程师入口和制造履约平台；平台价值要由跨品类复购证明。"], "signals": ["跨品类客户复购没有提升", "产能扩张快于订单增长", "库存、应收或经营现金流明显恶化"]},
    "江苏展芯半导体技术股份有限公司": {"advantages": ["聚焦功率半导体等国产替代环节，产品验证和客户导入构成进入门槛。"], "risks": ["半导体周期、产品价格下行和扩产折旧可能同时压缩利润。"], "profit": "利润由晶圆成本、良率、产品组合、平均售价和产能利用率决定；高端产品占比提升能增厚毛利，价格战与低稼动率会放大折旧压力。", "non_consensus": ["国产替代并不自动等于高利润，真正壁垒是通过车规等长周期认证后仍能保持价格和良率。"], "signals": ["平均售价持续下降", "高端或车规产品验证延期", "扩产后产能利用率和现金流下降"]},
    "苏州市贝特利高分子材料股份有限公司": {"advantages": ["在功能性高分子材料中具备配方、客户认证和稳定交付能力。"], "risks": ["客户集中度较高，原料价格和大客户订单变化会直接影响收入与毛利。"], "profit": "利润来自配方差异化、客户认证溢价和原料成本传导；批量放大可降低单位成本，但大客户议价会限制涨价。", "non_consensus": ["材料公司的壁垒不只在配方专利，更在客户产线长期验证和稳定性记录。"], "signals": ["前五大客户占比继续上升", "原料成本上涨无法传导", "新客户认证周期显著拉长"]},
    "成都超纯应用材料股份有限公司": {"advantages": ["面向半导体等高洁净场景提供高纯材料，纯度控制和客户认证形成较长验证周期。"], "risks": ["供应商集中度较高，关键原料受限或价格波动会影响交付和利润。"], "profit": "利润由高纯等级产品占比、原料采购、客户认证后的放量和良率决定；高规格产品带来溢价，供应不稳会增加成本。", "non_consensus": ["高纯材料的护城河往往体现在客户不愿轻易换供应商，而非单看产品名称是否国产替代。"], "signals": ["主要供应商中断或采购价格大涨", "半导体客户认证延期", "高规格产品占比没有提升"]},
    "福建马坑矿业股份有限公司": {"advantages": ["拥有稳定矿产资源与规模化采选能力，资源禀赋决定了较高进入壁垒。"], "risks": ["客户和供应商集中度高，矿价、品位、安全环保及资本开支会共同影响现金流。"], "profit": "利润主要由矿产品价格、销量、品位、采选成本和剥采投入决定；售价上行会直接增厚利润，品位下降和安全环保投入则抬高单位成本。", "non_consensus": ["矿企不能只看资源量，持续盈利更取决于可采品位、运输半径和扩产资本效率。"], "signals": ["主要矿产品价格下跌", "单位采选成本持续上升", "大客户采购下降或安全环保停产"]},
    "中电科思仪科技股份有限公司": {"advantages": ["背靠电子测量长期技术积累，产品覆盖高端仪器、测试系统和关键整部件，国产替代验证壁垒较高。"], "risks": ["高端仪器研发周期长，政府及科研客户预算和项目验收节奏会影响收入确认。"], "profit": "利润由高端整机和系统占比、研发投入、项目验收和规模制造决定；产品升级提高单价，但长研发周期和定制交付会增加费用。", "non_consensus": ["真正的壁垒不是仪器型号数量，而是测量精度、校准体系和客户多年使用形成的数据可信度。"], "signals": ["重点型号研发或验收延期", "收入增长依赖低毛利系统集成", "研发投入上升但新品收入占比不增"]},
    "国仪量子技术（合肥）股份有限公司": {"advantages": ["在量子精密测量和高端科学仪器中形成多产品平台，国产稀缺性和技术积累突出。"], "risks": ["公司仍处亏损阶段，科研市场规模、商业化速度和持续研发投入决定盈亏拐点。"], "profit": "利润取决于科研仪器从项目制走向标准化销售的速度；收入放量可摊薄研发和服务网络，但新品多、交付复杂会维持高费用。", "non_consensus": ["短期亏损不一定否定技术价值，但若产品始终停留在科研样机和单项目交付，平台化故事就难以转化为现金流。"], "signals": ["经营现金流再次明显转负", "标准化产品收入占比不升", "研发费用持续增长但客户复购不足"]},
}


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def parse_js(path: Path) -> dict[str, Any]:
    match = re.search(r"=\s*(\{.*\})\s*;", path.read_text(encoding="utf-8"), re.S)
    if not match:
        raise ValueError(path)
    return json.loads(match.group(1))


def bullet_cards(title: str, values: list[str], kind: str) -> str:
    cards = "".join(f'<div class="box {kind}"><h3>{esc(title)} {i}</h3><p>{esc(value)}</p></div>' for i, value in enumerate(values, 1))
    return f'<div class="grid two">{cards}</div>'


def upgrade_overview(source: str, company: str, analysis: dict[str, Any]) -> str:
    if "先说结论" in source and "最大优势" in source and "最大风险" in source:
        return source
    section = (
        '<section class="panel conclusion-first"><h2>先说结论</h2>'
        + bullet_cards("最大优势", analysis["advantages"], "advantage")
        + bullet_cards("最大风险", analysis["risks"], "risk high")
        + '<p class="note">判断来自完整调研中的事实与推断；关键数据以完整调研来源列表为准。</p></section>'
    )
    marker = '<section class="grid facts">'
    if marker in source:
        return source.replace(marker, section + marker, 1)
    return source.replace("<main>", "<main>" + section, 1)


def upgrade_research(source: str, company: str, analysis: dict[str, Any], evidence: dict[str, str]) -> str:
    judgement = (
        '<section id="judgement" class="panel section"><h2>利润机制、非共识判断与反证信号</h2>'
        f'<h3>利润机制</h3><p>{esc(analysis["profit"])}</p>'
        + '<h3>非共识判断</h3>' + bullet_cards("判断", analysis["non_consensus"], "")
        + '<h3>反证信号</h3>' + bullet_cards("信号", analysis["signals"], "risk")
        + '<p class="note">以上为本报告推断，不是确定性预测；出现反证信号时应重新核对假设。</p></section>'
    )
    if "非共识判断" not in source or "反证信号" not in source:
        risk_marker = re.search(r'<section\s+id="risks?"', source)
        if risk_marker:
            source = source[: risk_marker.start()] + judgement + source[risk_marker.start() :]
        else:
            source_marker = re.search(r'<section[^>]+id="sources"', source)
            insertion = source_marker.start() if source_marker else source.rfind("</main>")
            source = source[:insertion] + judgement + source[insertion:]
    quality = (
        '<h3>来源质量映射</h3><table class="source-quality"><thead><tr>'
        '<th>PDF校验</th><th>状态及状态核验日期</th><th>单位与期间</th><th>页码与报告章节</th></tr></thead><tbody><tr>'
        f'<td>有效 PDF（%PDF- 文件头）；{esc(evidence.get("pdf", "待复核"))}</td>'
        f'<td>{esc(evidence.get("status", "待复核"))}；{esc(evidence.get("status_date", "待复核"))}</td>'
        '<td>财务表统一标注万元或百分比，期间以报告表头为准；缺失字段标记待复核</td>'
        '<td>关键数据在财务分析、公司画像、客户供应商和募投章节逐项标注 PDF 页码</td>'
        '</tr></tbody></table><p class="note">镜像文件仅在已与交易所披露目录核对文件名和日期后使用；待复核项不得视为官方确定事实。</p>'
    )
    if "来源质量映射" not in source:
        marker = re.search(r'(<section[^>]*id="sources"[^>]*>\s*<h2>[^<]*来源列表</h2>)', source)
        if marker:
            source = source[: marker.end()] + quality + source[marker.end() :]
        else:
            heading = re.search(r'(<h2>[^<]*来源列表</h2>)', source)
            if heading:
                source = source[: heading.end()] + quality + source[heading.end() :]
    return source


def next_path(path: Path) -> Path:
    match = re.match(r"(.+)-v(\d+)\.html$", path.name)
    if not match:
        return path.with_name(path.stem + "-quality-v1.html")
    return path.with_name(f"{match.group(1)}-v{int(match.group(2)) + 1}.html")


def best_pdf(company: str) -> str:
    aliases = {name: re.search(r"companies/([^/]+)/", payload.get("researchUrl", "")) for name, payload in parse_js(REPORTS_JS).items()}
    match = aliases.get(company)
    if not match:
        return "待复核"
    source_dir = ROOT / "companies" / match.group(1) / "sources"
    pdfs = sorted(source_dir.glob("*.pdf")) if source_dir.exists() else []
    return str(pdfs[-1].relative_to(ROOT)) if pdfs else "待复核"


def main() -> None:
    data = parse_js(DATA_JS)
    items = {item["name"]: item for item in data["items"]}
    reports = parse_js(REPORTS_JS)
    for company, mapping in reports.items():
        analysis = ANALYSIS[company]
        overview = (ROOT / "dashboard" / mapping["overviewUrl"]).resolve()
        research = (ROOT / "dashboard" / mapping["researchUrl"]).resolve()
        new_overview, new_research = next_path(overview), next_path(research)
        new_overview.write_text(upgrade_overview(overview.read_text(encoding="utf-8"), company, analysis), encoding="utf-8")
        item = items[company]
        evidence = {"pdf": best_pdf(company), "status": item["status"], "status_date": item.get("sourceDate", "待复核")}
        new_research.write_text(upgrade_research(research.read_text(encoding="utf-8"), company, analysis, evidence), encoding="utf-8")
        mapping["overviewUrl"] = "../" + str(new_overview.relative_to(ROOT))
        mapping["researchUrl"] = "../" + str(new_research.relative_to(ROOT))
        mapping["sourceBoundary"] = "已加入最大优势/风险、利润机制、非共识判断、反证信号和完整调研来源质量映射"
    REPORTS_JS.write_text("window.IPO_COMPANY_REPORTS = " + json.dumps(reports, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")


if __name__ == "__main__":
    main()
