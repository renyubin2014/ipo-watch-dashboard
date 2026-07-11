#!/usr/bin/env python3
"""Generate readable, data-first IPO HTML reports for the dashboard pool.

This script follows the a-share-company-html-research skill. It deliberately
does not use the old keyword-nearby number snippets. Core figures are extracted
as named metrics from prospectus PDF text and rendered as structured tables with
source pages. Ambiguous fields are marked as 待补充/待复核.
"""

from __future__ import annotations

import csv
import datetime as dt
import html
import json
import math
import os
import re
import signal
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DATA = ROOT / "dashboard" / "data.js"
REPORTS_JS = ROOT / "dashboard" / "reports.js"
WATCHLIST = ROOT / "data" / "ipo_watchlist.csv"
REPORT_DATE = "2026-07-10"
SKIP = {
    "长鑫科技集团股份有限公司",
    "宇树科技股份有限公司",
    # 燧原有单独的人工校验数据版，通用抽取容易把高研发费用率和叙述段数字误判。
    "上海燧原科技股份有限公司",
}
SHARED_HERO = "../../../dashboard/assets/ipo-hero.png"
PDF_PAGE_TIMEOUT_SECONDS = 5
MAX_METRIC_SCAN_PAGES = 220
MAX_RATIO_SCAN_PAGES = 260
MAX_FUNDRAISING_SCAN_PAGES = 180

DIR_ALIASES = {
    "上海燧原科技股份有限公司": "燧原科技",
    "天博智能科技（山东）股份有限公司": "天博智能",
    "广东中塑新材料股份有限公司": "中塑股份",
    "苏州绿控传动科技股份有限公司": "绿控传动",
    "洛阳轴承集团股份有限公司": "洛轴股份",
    "上海频准激光科技股份有限公司": "频准激光",
    "深圳嘉立创科技集团股份有限公司": "嘉立创",
    "江苏展芯半导体技术股份有限公司": "江苏展芯",
    "苏州市贝特利高分子材料股份有限公司": "贝特利",
    "成都超纯应用材料股份有限公司": "超纯股份",
    "福建马坑矿业股份有限公司": "马矿股份",
    "中电科思仪科技股份有限公司": "思仪科技",
    "国仪量子技术（合肥）股份有限公司": "国仪量子",
}

METRICS = [
    "营业收入",
    "净利润",
    "归母净利润",
    "扣非归母净利润",
    "毛利率",
    "经营现金流",
    "研发费用率",
]

METRIC_PATTERNS = {
    "营业收入": [r"营业收入(?:（万元）)?"],
    "净利润": [r"净利润(?:（万元）)?"],
    "归母净利润": [r"归属于母公司(?:所有者|股东)的净利润(?:（万元）)?"],
    "扣非归母净利润": [r"扣除非经常性损益.*?归属于母公司.*?净利润", r"扣非.*?归母.*?净利润"],
    "毛利率": [r"综合毛利率", r"主营业务毛利率", r"^毛利率"],
    "经营现金流": [r"经营活动产生的现金流量净额", r"经营活动现金流量净额"],
    "研发费用率": [r"研发投入占营业收入的比例", r"研发费用率"],
}

BAD_CONTEXT = [
    "预计",
    "上年同期",
    "较上年",
    "较去年",
    "同比",
    "区间",
    "增长",
    "下降",
    "分别为",
    "预测",
    "变动",
    "同向",
    "反向",
    "不低于",
    "累计",
    "年至",
    "亿元",
    "设立",
    "签署日",
    "基本情",
    "2026 年 1",
    "2026年1",
    "2026 年 3",
    "2026年3",
]


@dataclass
class Metric:
    name: str
    values: list[str]
    page: int | str
    label: str
    source: str = "招股说明书"
    status: str = "公司披露"
    note: str = ""


@dataclass
class ReportData:
    company: str
    short: str
    pdf: Path | None
    pdf_date: str
    pdf_title: str
    item: dict[str, Any]
    metrics: dict[str, Metric] = field(default_factory=dict)
    business: dict[str, Any] = field(default_factory=dict)
    customer: dict[str, Any] = field(default_factory=dict)
    supplier: dict[str, Any] = field(default_factory=dict)
    fundraising: dict[str, Any] = field(default_factory=dict)
    source_notes: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


MANUAL_CORRECTIONS: dict[str, dict[str, Any]] = {
    "上海频准激光科技股份有限公司": {
        "metrics": {
            "营业收入": {
                "values": ["41,791.65", "29,185.72", "14,772.14"],
                "page": 25,
                "label": "营业收入（万元） 41,791.65 29,185.72 14,772.14",
            },
            "净利润": {
                "values": ["15,944.29", "11,561.60", "6,046.36"],
                "page": 25,
                "label": "净利润（万元） 15,944.29 11,561.60 6,046.36",
            },
            "归母净利润": {
                "values": ["15,944.29", "11,561.60", "6,046.36"],
                "page": 25,
                "label": "归属于母公司所有者的净利润（万元） 15,944.29 11,561.60 6,046.36",
            },
            "扣非归母净利润": {
                "values": ["15,124.57", "11,143.08", "5,780.31"],
                "page": 25,
                "label": "扣除非经常性损益后归属于母公司所有者的净利润（万元） 15,124.57 11,143.08 5,780.31",
            },
            "经营现金流": {
                "values": ["19,108.03", "11,672.75", "6,009.66"],
                "page": 25,
                "label": "经营活动产生的现金流量净额（万元） 19,108.03 11,672.75 6,009.66",
            },
            "毛利率": {
                "values": ["69.33%", "67.78%", "68.53%"],
                "page": 15,
                "label": "毛利率 69.33% 67.78% 68.53%",
            },
        },
        "post_period_note": "审计截止日后/2026H1 预计：2026H1 收入预计 23,000.00-26,000.00 万元，2025H1 为 18,028.56 万元；该组数字属于半年度预计口径，已从 2025/2024/2023 年度表剔除。",
    },
    "洛阳轴承集团股份有限公司": {
        "business": {
            "text": "轴承及相关零部件的研发、生产和销售；重大装备、高端装备、新能源汽车等专用轴承为重点。",
            "page": 108,
        },
        "drop_metrics": ["净利润", "扣非归母净利润"],
        "metrics": {
            "营业收入": {
                "values": ["603,377.30", "467,494.68", "444,129.30"],
                "page": 4,
                "label": "营业收入（万元） 603,377.30 467,494.68 444,129.30",
            },
            "归母净利润": {
                "values": ["52,925.38", "25,094.38", "23,066.37"],
                "page": 4,
                "label": "归属于母公司股东的净利润（万元） 52,925.38 25,094.38 23,066.37",
            },
        },
        "post_period_note": "审计截止日后/2026H1 预计：2026H1 收入预计 320,000-335,000 万元，2025H1 为 282,051.21 万元；该组数字属于半年度预计口径，已从 2025/2024/2023 年度表剔除。",
    },
    "国仪量子技术（合肥）股份有限公司": {
        "metrics": {
            "营业收入": {
                "values": ["66,619.18", "50,147.22", "39,962.01"],
                "page": 39,
                "label": "营业收入（万元） 66,619.18 50,147.22 39,962.01",
            },
            "归母净利润": {
                "values": ["-579.72", "-7,408.02", "-13,997.07"],
                "page": 30,
                "label": "归属于母公司所有者的净利润（万元） -579.72 -7,408.02 -13,997.07",
            },
            "扣非归母净利润": {
                "values": ["-1,887.80", "-10,423.63", "-16,932.20"],
                "page": 30,
                "label": "扣除非经常性损益后归属于母公司所有者的净利润（万元） -1,887.80 -10,423.63 -16,932.20",
            },
            "经营现金流": {
                "values": ["11,834.03", "-5,023.76", "-13,359.34"],
                "page": 30,
                "label": "经营活动产生的现金流量净额（万元） 11,834.03 -5,023.76 -13,359.34",
            },
        },
        "customer": {
            "ratio": "16.07%",
            "amount": "待补充",
            "page": 21,
            "snippet": "前五大客户收入合计占主营业务收入的比重分别为 24.62%、17.02% 和 16.07%。",
        },
        "supplier": {
            "ratio": "24.58%",
            "amount": "8,172.70",
            "page": 196,
            "snippet": "2025 年度前五大供应商总计 8,172.70 万元，占采购总额比例 24.58%。",
        },
        "post_period_note": "审计截止日后/2026H1 预计：2026H1 收入预计 24,000-28,000 万元，2025H1 为 17,121.45 万元；该组数字属于半年度预计口径，已从 2025/2024/2023 年度表剔除。",
    },
    "中电科思仪科技股份有限公司": {
        "business": {
            "text": "专业从事电子测量仪器研发、制造和销售，主要产品包括整机、测试系统、整部件等。",
            "page": "20/122",
        },
    },
    "深圳嘉立创科技集团股份有限公司": {
        "board": "深交所主板",
        "business": {
            "text": "电子产业基础设施综合服务，覆盖 EDA/CAM、PCB 制造、电子元器件购销、PCBA/电子装联等。",
            "page": "103-104",
        },
    },
    "苏州绿控传动科技股份有限公司": {
        "metrics": {
            "毛利率": {
                "values": ["16.06%", "19.78%", "16.77%"],
                "page": 20,
                "label": "综合毛利率 16.06% 19.78% 16.77%",
            },
        },
        "customer": {
            "ratio": "59.10%",
            "amount": "待补充",
            "page": 20,
            "snippet": "前五名客户合计的销售收入占当期营业收入的比例分别为 63.04%、62.11%和 59.10%。",
        },
    },
    "福建马坑矿业股份有限公司": {
        "customer": {
            "ratio": "82.53%",
            "amount": "待补充",
            "page": 35,
            "snippet": "前五大客户的销售收入占当年收入的比例分别为 97.68%、92.50%和 82.53%。",
        },
        "supplier": {
            "ratio": "58.41%",
            "amount": "待补充",
            "page": 120,
            "snippet": "前五名供应商占采购金额比例分别为 62.04%、58.43%和 58.41%。",
        },
    },
    "成都超纯应用材料股份有限公司": {
        "supplier": {
            "ratio": "79.44%",
            "amount": "待补充",
            "page": 20,
            "snippet": "前五大供应商的采购占比分别为 54.05%、66.62%、79.44%。",
        },
    },
    "苏州市贝特利高分子材料股份有限公司": {
        "customer": {
            "ratio": "68.86%",
            "amount": "待补充",
            "page": 58,
            "snippet": "前五名客户销售额占销售总额的比例分别为 72.25%、68.32%和 68.86%。",
        },
    },
}


INDUSTRY_LANDSCAPES: dict[str, dict[str, Any]] = {
    "天博智能科技（山东）股份有限公司": {
        "title": "汽车热管理与电声部件：细分件按排名看位置",
        "rows": [
            {"name": "汽车调温器", "value": "天博：全球第 3 / 国内第 1", "note": "弗若斯特沙利文按 2024 年收入排名；招股书未披露精确市占率。"},
            {"name": "汽车智能水阀", "value": "天博：国内第 2", "note": "对应新能源汽车热管理增量部件。"},
            {"name": "汽车温度传感器", "value": "天博：国内第 4", "note": "中汽协销量口径亦列示国内第 4。"},
            {"name": "AVAS 声学部件", "value": "天博：国内第 2", "note": "电动车低速提示音系统。"},
        ],
        "observation": "天博的行业位置不是整车热管理总包，而是在调温器、水阀、温度传感器、AVAS 等小而关键的细分件里取得排名优势；后续要补第三方报告原文中的百分比市占。",
        "source": "来源：天博智能招股说明书（注册稿），公告日期 2026-06-18，第 21 页、第 78 页；第三方口径为弗若斯特沙利文/中国汽车工业协会。",
    },
    "广东中塑新材料股份有限公司": {
        "title": "改性工程塑料：高端外资占优，中端本土替代",
        "rows": [
            {"name": "高端改性塑料", "value": "外资大型跨国企业占据主要位置", "note": "招股书未披露各公司百分比市占。"},
            {"name": "中端市场", "value": "本土企业逐步提升份额", "note": "政策支持和本土研发推动国产替代。"},
            {"name": "低端市场", "value": "规模大、企业多、集中度低", "note": "利润率低，竞争激烈。"},
            {"name": "中塑股份", "value": "精密结构件/消费电子材料切入", "note": "终端客户进入三星、华为、小米、OPPO、传音等供应链资源池。"},
        ],
        "observation": "中塑所在赛道没有一个像 DRAM 那样清晰的寡头市占表；更重要的是看它是否能从消费电子材料，迁移到新能源汽车、储能、家电等更分散但更长期的应用。",
        "source": "来源：中塑股份招股说明书（注册稿），公告日期 2026-06-05，第 27 页、第 29 页；招股书未披露公司精确市占率。",
    },
    "苏州绿控传动科技股份有限公司": {
        "title": "新能源商用车电驱：公司在重卡电机配套连续第一",
        "rows": [
            {"name": "新能源重卡整车侧", "value": "徐工集团 + 三一集团：29.93%", "percent": 29.93, "note": "按招股书披露的 2025 年销量排名，二者合计市场占有率。"},
            {"name": "新能源重卡电机配套", "value": "绿控传动：2023-2025 年持续第 1", "note": "科瑞咨询上险数据口径；招股书未披露精确百分比。"},
            {"name": "主要客户验证", "value": "徐工、三一、东风、金龙、福田等", "note": "客户侧与整车集中度强相关。"},
        ],
        "observation": "绿控的优势在于卡在新能源商用车动力链的关键部件，但它的需求弹性要跟着徐工、三一等头部整车厂的新能源重卡销量走。",
        "source": "来源：绿控传动招股说明书（注册稿），公告日期 2026-05-20，第 25 页、第 124 页；第三方口径为科瑞咨询上险数据。",
    },
    "洛阳轴承集团股份有限公司": {
        "title": "轴承：综合收入第 4，专用轴承多项前三",
        "rows": [
            {"name": "国内轴承行业收入", "value": "洛轴：2023-2024 年第 4", "note": "中国轴承工业协会口径。"},
            {"name": "风电主轴轴承", "value": "洛轴：行业第 1", "note": "重大装备轴承细分。"},
            {"name": "风电偏变轴承", "value": "洛轴：行业第 2", "note": "重大装备轴承细分。"},
            {"name": "轨交/航空/新能源车轮毂轴承", "value": "洛轴：行业前三", "note": "高端装备与新能源汽车轴承。"},
        ],
        "observation": "洛轴不是只看“轴承大盘”的公司，真正的估值弹性来自风电、轨交、航空航天、新能源车等专用轴承能否持续提升收入和毛利结构。",
        "source": "来源：洛轴股份招股说明书（注册稿），公告日期 2026-05-20，第 27 页、第 30 页；招股书披露排名，不披露精确市占率。",
    },
    "上海频准激光科技股份有限公司": {
        "title": "精准激光：Toptica 等海外强，本土品牌频准领先",
        "rows": [
            {"name": "量子信息领域激光器中国市场", "value": "2024 年 1.01 亿美元，2030 年预计 3 亿美元", "note": "QY Research 市场规模口径。"},
            {"name": "半导体设备激光器需求", "value": "2024 年 5.28 亿美元，2030 年预计 10.93 亿美元", "note": "QY Research 市场规模口径。"},
            {"name": "德国 Toptica", "value": "国内仍占较大份额", "note": "招股书描述，未披露精确百分比。"},
            {"name": "频准激光", "value": "国产品牌领先", "note": "量子科技精准激光器国内市场；精确市占待补第三方原文。"},
        ],
        "observation": "频准的行业位置有两个读法：在量子科研激光里是国产替代的头部，在半导体设备激光里仍是小市场切入者；不能把国产领先直接等同于大行业高份额。",
        "source": "来源：频准激光招股说明书（注册稿），公告日期 2026-05-22，第 23 页、第 36 页、第 72 页；QY Research 为招股书引用口径。",
    },
    "深圳嘉立创科技集团股份有限公司": {
        "title": "电子产业基础设施：从 PCB 打样到分销服务长尾客户",
        "rows": [
            {"name": "超级客户直采", "value": "约 44%", "percent": 44.0, "note": "不足 1% 的超级客户主要直接向原厂采购。"},
            {"name": "分销渠道/长尾客户", "value": "约 56%", "percent": 56.0, "note": "99% 以上制造商主要通过分销商渠道采购。"},
            {"name": "嘉立创", "value": "PCB + 元器件 + PCBA 一体化服务", "note": "招股书未披露公司在整体 PCB 或分销市场精确市占。"},
        ],
        "observation": "嘉立创的关键不只是 PCB 产能，而是把长尾研发、试产、小批量制造需求做成在线基础设施；看行业位置时要把它放进 56% 的分销/长尾服务池里理解。",
        "source": "来源：嘉立创招股说明书（注册稿），公告日期 2026-05-12，第 129 页；The Business Research Company 数据为招股书引用口径。",
    },
    "江苏展芯半导体技术股份有限公司": {
        "title": "军工电源管理芯片：民营配套企业前列",
        "rows": [
            {"name": "江苏展芯", "value": "4.36%", "percent": 4.36, "note": "按 80 亿元国内军规级电源管理芯片市场规模测算。"},
            {"name": "臻镭科技", "value": "2.46%", "percent": 2.46, "note": "公开披露电源管理芯片收入测算。"},
            {"name": "鸿远电子", "value": "1.31%", "percent": 1.31, "note": "集成电路收入含非电源管理芯片，口径偏宽。"},
            {"name": "振华风光", "value": "1.10%", "percent": 1.10, "note": "以历史披露占比测算。"},
            {"name": "成都华微", "value": "0.70%", "percent": 0.70, "note": "以招股书 2023H1 占比测算。"},
        ],
        "observation": "展芯的 4.36% 看起来不高，但军工电子有保密和认证门槛，公开可比口径下已处于民营军工电源管理芯片配套企业前列。",
        "source": "来源：江苏展芯招股说明书（注册稿），公告日期 2026-05-15，第 145 页；市场规模及同行收入为公司披露测算口径。",
    },
    "苏州市贝特利高分子材料股份有限公司": {
        "title": "导电材料/有机硅：几个小市场里有明确份额",
        "rows": [
            {"name": "HJT 浆料", "value": "约 7%", "percent": 7.0, "note": "2025 年全球市占率，以销量计。"},
            {"name": "个人电脑键盘导电浆料", "value": "约 46%", "percent": 46.0, "note": "2025 年全球市占率，以销量计。"},
            {"name": "卡斯特铂金催化剂", "value": "约 27%", "percent": 27.0, "note": "2025 年全球细分领域市占率，以销售收入计。"},
            {"name": "TOPCon 电池技术", "value": "87.6%", "percent": 87.6, "note": "CPIA 口径；用于提示公司银粉主需求仍在 TOPCon。"},
            {"name": "HJT 电池技术", "value": "2.6%", "percent": 2.6, "note": "CPIA 口径；HJT 浆料仍是早期变量。"},
        ],
        "observation": "贝特利不是单一光伏浆料公司：键盘导电浆料和铂金催化剂已有高份额，HJT 浆料只有约 7% 且下游 HJT 技术本身仍只占 2.6%，这决定了它的成长弹性和不确定性同时存在。",
        "source": "来源：贝特利招股说明书（注册稿），公告日期 2026-05-13，第 22 页、第 24 页、第 36 页；CPIA/IDC/QYResearch 为招股书引用口径。",
    },
    "成都超纯应用材料股份有限公司": {
        "title": "半导体设备特殊涂层零部件：本土企业第一，但总体份额仍小",
        "rows": [
            {"name": "超纯股份", "value": "中国大陆 5.7%", "percent": 5.7, "note": "2024 年半导体设备特殊涂层零部件本土企业中排名第一。"},
            {"name": "国际设备/零部件体系", "value": "海外龙头仍占主导", "note": "招股书描述进口替代空间逐步打开，未披露海外龙头精确份额。"},
            {"name": "客户 A + 客户 B", "value": "2025 年收入合计 64.79%", "percent": 64.79, "note": "客户侧集中度，提示行业验证和收入质量。"},
        ],
        "observation": "超纯的 5.7% 说明它已经在国产替代里排到前面，但远没到寡头地位；它更像半导体设备国产供应链里的“小而尖”验证样本。",
        "source": "来源：超纯股份招股说明书（注册稿），公告日期 2026-05-06，第 20 页、第 25 页；弗若斯特沙利文为招股书引用口径。",
    },
    "福建马坑矿业股份有限公司": {
        "title": "铁矿石：国际四大矿山主导，马矿在国内上市同业里靠前",
        "rows": [
            {"name": "国际铁矿石供应", "value": "淡水河谷、力拓、必和必拓、FMG 主导", "note": "招股书描述四大国际巨头拥有主导话语权，未披露精确百分比。"},
            {"name": "马矿股份", "value": "同业上市公司铁矿相关收入/产量第 2", "note": "2025 年国内上市同业同类业务口径，仅大中矿业超过发行人。"},
            {"name": "中国钼矿储量", "value": "39.33%", "percent": 39.33, "note": "USGS 2024 年末数据，马矿伴生钼业务的行业背景。"},
            {"name": "中国钼矿产量", "value": "46.15%", "percent": 46.15, "note": "USGS 2024 年产量口径。"},
        ],
        "observation": "马矿的主线不是全球铁矿定价权，而是东南沿海铁精粉稳定供给和伴生钼资源价值；国际四大矿山决定大周期，区域客户和矿山品位决定公司利润。",
        "source": "来源：马矿股份招股说明书（注册稿），公告日期 2026-05-29，第 24 页、第 27 页、第 79 页；中国冶金矿山企业协会/USGS 为招股书引用口径。",
    },
    "中电科思仪科技股份有限公司": {
        "title": "电子测量仪器：国内企业第一，但全球仍看是德等巨头",
        "rows": [
            {"name": "全球产品及测试测量系统市场", "value": "1,391.2 亿元", "note": "招股书披露 2024 年市场规模。"},
            {"name": "是德科技", "value": "354.75 亿元", "note": "2024 年收入位列第一。"},
            {"name": "中国市场规模", "value": "495.0 亿元", "note": "2024 年电子测量仪器产品及测试测量系统。"},
            {"name": "思仪科技", "value": "国内企业第 1；约 4.15% 中国市场收入占比", "percent": 4.15, "note": "20.52 亿元收入 / 495.0 亿元中国市场规模。"},
            {"name": "微波/毫米波测量仪器", "value": "约 13.97%", "percent": 13.97, "note": "10.17 亿元相关整机收入 / 72.8 亿元中国市场规模。"},
        ],
        "observation": "思仪在国内企业里已经是头部，但放到全球和中国总市场，收入占比仍是个位数；真正要看能否从微波/毫米波强项扩展到更完整的测试测量平台。",
        "source": "来源：思仪科技招股说明书（注册稿），公告日期 2026-04-29，第 23 页；市场规模和收入为公司披露口径。",
    },
    "国仪量子技术（合肥）股份有限公司": {
        "title": "高端科学仪器：国际巨头压制，本土品牌在细分仪器突围",
        "rows": [
            {"name": "国际科学服务/仪器巨头", "value": "赛默飞、丹纳赫、安捷伦、蔡司、布鲁克等", "note": "招股书列示的主要国际对标对象。"},
            {"name": "国仪量子", "value": "电子顺磁共振、扫描 NV 探针等细分突破", "note": "招股书披露打破国际巨头在国内相关市场垄断。"},
            {"name": "客户集中度", "value": "2025 年前五大客户 16.07%", "percent": 16.07, "note": "客户分散，说明不是靠单一大客户放量。"},
            {"name": "供应商集中度", "value": "2025 年前五大供应商 24.58%", "percent": 24.58, "note": "供应链集中度相对可控。"},
        ],
        "observation": "国仪的行业位置更像“多细分仪器的国产替代组合”，不是单一仪器市占率故事；本版不伪造科学仪器总市场份额，后续应补各产品线第三方份额。",
        "source": "来源：国仪量子招股说明书（注册稿），公告日期 2026-05-12，第 2 页、第 21-22 页、第 196 页；招股书未披露公司整体精确市占率。",
    },
}


def esc(value: Any) -> str:
    text = "待补充" if value in (None, "") else str(value)
    return html.escape(text, quote=True)


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\u3000", " ").replace("\n", " ")).strip()


def parse_js_object(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"=\s*(\{.*\})\s*;", text, re.S)
    if not match:
        raise ValueError(f"Cannot parse {path}")
    return json.loads(match.group(1))


def write_js_object(path: Path, name: str, payload: dict[str, Any]) -> None:
    path.write_text(f"{name} = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")


def load_watchlist() -> dict[str, dict[str, str]]:
    with WATCHLIST.open(encoding="utf-8-sig", newline="") as file:
        return {row["公司名"]: row for row in csv.DictReader(file)}


def valid_pdf(path: Path) -> bool:
    try:
        return path.read_bytes()[:5] == b"%PDF-"
    except OSError:
        return False


def find_prospectus(short: str) -> Path | None:
    sources = ROOT / "companies" / short / "sources"
    if not sources.exists():
        return None
    candidates = sorted(
        sources.glob("*招股说明书*.pdf"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        if valid_pdf(path):
            return path
    return None


def source_date_from_name(path: Path | None, fallback: str = "待补充") -> str:
    if not path:
        return fallback
    match = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
    return match.group(1) if match else fallback


def source_title_from_name(path: Path | None) -> str:
    if not path:
        return "待补充"
    name = path.stem
    name = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", name)
    name = re.sub(r"-(东方财富镜像|深交所|eastmoney-mirror)$", "", name)
    return name


def safe_reader(path: Path) -> PdfReader | None:
    try:
        return PdfReader(str(path))
    except Exception:
        return None


class PdfPageTimeout(Exception):
    pass


def _timeout_handler(signum: int, frame: Any) -> None:
    raise PdfPageTimeout()


def extract_page_text(page: Any, timeout: int = PDF_PAGE_TIMEOUT_SECONDS) -> str:
    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(timeout)
    try:
        return page.extract_text() or ""
    except Exception:
        return ""
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def page_texts(path: Path, *, max_pages: int | None = None) -> list[str]:
    reader = safe_reader(path)
    if not reader:
        return []
    pages = reader.pages if max_pages is None else reader.pages[:max_pages]
    return [extract_page_text(page) for page in pages]


def numbers(text: str) -> list[str]:
    nums = re.findall(r"-?\d{1,3}(?:,\d{3})*(?:\.\d+)?%?|-?\d+\.\d+%?|-?\d+%?", text)
    return [num for num in nums if num not in {"2023", "2024", "2025", "2026"}]


def metric_start(metric: str, line: str) -> int | None:
    for pattern in METRIC_PATTERNS[metric]:
        match = re.search(pattern, line)
        if match:
            return match.start()
    return None


def normalize_values(metric: str, vals: list[str], line: str) -> list[str] | None:
    vals = vals[:]
    if metric in {"营业收入", "净利润", "归母净利润", "扣非归母净利润", "经营现金流"}:
        if any(bad in line for bad in ("设立", "签署日", "基本情", "不低于", "累计", "年至", "亿元")):
            return None
        if re.search(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?-\d", line):
            return None
        if "分别为" in line:
            return None
        if any("%" in v for v in vals[:3]):
            return None
        if metric == "营业收入" and any(v.startswith("-") for v in vals[:3]):
            return None
        if metric == "营业收入" and any((to_float(v) or 0) < 1000 for v in vals[:3]):
            return None
        if metric == "经营现金流" and any(abs(to_float(v) or 0) < 100 for v in vals[:3]):
            return None
        return vals[:3] if len(vals) >= 3 else None
    if metric in {"毛利率", "研发费用率"}:
        if any(bad in line for bad in ("分别为", "变动", "同向", "反向", "敏感")):
            return None
        if metric == "毛利率" and "收入占比" in line and len(vals) >= 6:
            vals = vals[0::2]
        if len(vals) >= 6 and any(v in {"100.00%", "100%"} for v in vals[1::2]):
            vals = vals[0::2]
        fixed = []
        for value in vals:
            if "%" not in value and re.fullmatch(r"-?\d+(?:\.\d+)?", value):
                fixed.append(value + "%")
            else:
                fixed.append(value)
        if len(fixed) >= 3 and all("%" in v for v in fixed[:3]):
            pct_values = [to_float(v) for v in fixed[:3]]
            if any(value is None or value < 0 or value > 100 for value in pct_values):
                return None
            return fixed[:3]
    return None


def candidate_score(metric: str, page_no: int, line: str, values: list[str], revenue_page: int | None) -> int:
    score = 0
    if page_no <= 80:
        score += 20
    if revenue_page and abs(page_no - revenue_page) <= 8:
        score += 35
    if re.match(
        r"^(营业收入|净利润|归属于母公司|归属于公司普通股|扣除非经常性|综合毛利率|主营业务毛利率|毛利率|经营活动产生的现金流量净额|经营活动现金流量净额|研发投入占营业收入的比例|研发费用率)\s",
        line,
    ):
        score += 60
    if line.startswith(metric) or any(line.startswith(re.sub(r"[\\^$?()+*.\[\]{}|]", "", p).replace(".*", "")) for p in METRIC_PATTERNS[metric]):
        score += 15
    if "（万元）" in line or metric in {"毛利率", "研发费用率"}:
        score += 8
    if any(bad in line for bad in BAD_CONTEXT):
        score -= 80
    if "报告期内" in line:
        score -= 30
    if "目 录" in line or "目录" in line[:20]:
        score -= 100
    if values and len(values) == 3:
        score += 12
    return score


def joined_lines(text: str) -> list[str]:
    raw = [clean(line) for line in text.splitlines() if clean(line)]
    out = []
    for i, line in enumerate(raw):
        out.append(line)
        if i + 1 < len(raw):
            out.append(line + " " + raw[i + 1])
        if i + 2 < len(raw):
            out.append(line + " " + raw[i + 1] + " " + raw[i + 2])
    return out


def extract_metrics(path: Path) -> dict[str, Metric]:
    texts = page_texts(path, max_pages=MAX_METRIC_SCAN_PAGES)
    candidates: dict[str, list[tuple[int, int, str, list[str]]]] = {metric: [] for metric in METRICS}
    revenue_page: int | None = None
    for page_no, text in enumerate(texts, start=1):
        for line in joined_lines(text):
            for metric in METRICS:
                start = metric_start(metric, line)
                if start is None:
                    continue
                sliced = line[start:]
                vals = normalize_values(metric, numbers(sliced), sliced)
                if not vals:
                    continue
                score = candidate_score(metric, page_no, sliced, vals, revenue_page)
                if metric == "营业收入" and revenue_page is None and page_no <= 80 and score > 0:
                    revenue_page = page_no
                candidates[metric].append((score, page_no, sliced[:260], vals))
    result: dict[str, Metric] = {}
    for metric, items in candidates.items():
        if not items:
            continue
        items.sort(key=lambda item: item[0], reverse=True)
        score, page_no, line, vals = items[0]
        if score < -20:
            continue
        result[metric] = Metric(name=metric, values=vals, page=page_no, label=line)
    return result


def first_sentence(text: str, patterns: list[str]) -> tuple[str, int | str]:
    for page_no, page in enumerate(page_texts_from_cache(text), start=1):
        compact = clean(page)
        for pattern in patterns:
            idx = compact.find(pattern)
            if idx == -1:
                continue
            snippet = compact[idx : idx + 360]
            stop = re.search(r"[。；;]", snippet)
            return (snippet[: stop.end()] if stop else snippet, page_no)
    return "待补充", "待补充"


def page_texts_from_cache(_: str) -> list[str]:
    raise RuntimeError("page_texts_from_cache should be monkey-patched")


def extract_business(texts: list[str]) -> dict[str, Any]:
    patterns = [
        ("公司主要从事", 90),
        ("主要从事", 75),
        ("主营业务为", 70),
        ("主营业务是", 70),
        ("公司业务聚焦", 70),
        ("自成立以来专注于", 68),
        ("公司秉承", 62),
        ("公司致力于", 58),
    ]
    bad_markers = [
        "与发行人主营业务",
        "发行人主营业务的关系",
        "主营业务及其与发行人",
        "未从事与发行人",
        "主营业务及在发行人业务中的定位",
        "股东构成",
        "直接持有公司",
        "投资管理",
    ]
    candidates: list[tuple[int, int, str]] = []
    for page_no, page in enumerate(texts[:120], start=1):
        compact = clean(page)
        for pattern, base_score in patterns:
            idx = compact.find(pattern)
            if idx == -1:
                continue
            snippet = compact[idx : idx + 420]
            stop = re.search(r"[。；;]", snippet)
            text = snippet[: stop.end()] if stop else snippet
            score = base_score
            if page_no <= 40:
                score += 30
            if "发行人主营业务经营情况" in compact or "公司经营的主要业务和主要产品" in compact:
                score += 35
            if "主要产品" in text or "产品" in text:
                score += 8
            if any(marker in compact[max(0, idx - 180) : idx + 260] for marker in bad_markers):
                score -= 180
            if "未从事" in text or "投资管理" in text:
                score -= 120
            candidates.append((score, page_no, text))
    candidates = [candidate for candidate in candidates if candidate[0] > 0]
    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        _, page_no, text = candidates[0]
        return {"text": text, "page": page_no}
    return {"text": "待补充", "page": "待补充"}


def extract_ratio_section(path: Path, terms: list[str], entity: str) -> dict[str, Any]:
    reader = safe_reader(path)
    if not reader:
        return {"ratio": "待补充", "amount": "待补充", "page": "待补充", "snippet": "待补充"}
    for page_no, page in enumerate(reader.pages, start=1):
        if page_no > MAX_RATIO_SCAN_PAGES:
            break
        try:
            text = extract_page_text(page)
        except Exception:
            continue
        compact = clean(text)
        if not any(term in compact for term in terms):
            continue
        next_text = ""
        if page_no < len(reader.pages):
            next_text = extract_page_text(reader.pages[page_no])
        block = clean(compact + " " + next_text)
        idxs = [block.find(term) for term in terms if block.find(term) != -1]
        idx = min(idxs) if idxs else 0
        snippet = block[idx : idx + 900]
        m = re.search(r"2025\s*年度?.{0,260}?合计\s+([\d,]+(?:\.\d+)?)\s+(\d{1,3}(?:\.\d+)?%)", snippet)
        if not m:
            m = re.search(r"2025\s*年.{0,260}?小计\s+([\d,]+(?:\.\d+)?)\s+(\d{1,3}(?:\.\d+)?%)", snippet)
        if m:
            return {"ratio": m.group(2), "amount": m.group(1), "page": page_no, "snippet": snippet[:360]}
        m = re.search(r"比例分别为\s*([\d.]+%)、\s*([\d.]+%)及\s*([\d.]+%)", snippet)
        if m:
            return {"ratio": m.group(3), "amount": "待补充", "page": page_no, "snippet": snippet[:360]}
        m = re.search(r"占同期营业收入的比例分别为\s*([\d.]+%)、\s*([\d.]+%)、\s*([\d.]+%)", snippet)
        if m:
            return {"ratio": m.group(3), "amount": "待补充", "page": page_no, "snippet": snippet[:360]}
        return {"ratio": "待补充", "amount": "待补充", "page": page_no, "snippet": snippet[:360]}
    return {"ratio": "待补充", "amount": "待补充", "page": "待补充", "snippet": f"未在招股书中稳定定位{entity}表"}


def extract_fundraising(path: Path) -> dict[str, Any]:
    reader = safe_reader(path)
    if not reader:
        return {"amount": "待补充", "page": "待补充", "snippet": "待补充"}
    for page_no, page in enumerate(reader.pages, start=1):
        if page_no > MAX_FUNDRAISING_SCAN_PAGES:
            break
        if page_no < 50:
            continue
        try:
            text = extract_page_text(page)
        except Exception:
            continue
        compact = clean(text)
        if "目 录" in compact[:120] or "目录" in compact[:80]:
            continue
        if not ("募集资金" in compact and ("拟投入" in compact or "募集资金运用" in compact or "募集资金用途" in compact)):
            continue
        snippet = compact[max(0, compact.find("募集资金") - 120) : compact.find("募集资金") + 820]
        m = re.search(r"合计\s+([\d,]+(?:\.\d+)?)", snippet)
        amount = m.group(1) if m else "待补充"
        return {"amount": amount, "page": page_no, "snippet": snippet[:420]}
    return {"amount": "待补充", "page": "待补充", "snippet": "未稳定定位募投合计金额"}


def to_float(value: str | None) -> float | None:
    if not value or value == "待补充":
        return None
    value = value.replace(",", "").replace("%", "")
    try:
        return float(value)
    except ValueError:
        return None


def pct_change(new: str, old: str) -> str:
    a = to_float(new)
    b = to_float(old)
    if a is None or b in (None, 0):
        return "待补充"
    return f"{(a / b - 1) * 100:.2f}%"


def cagr(last: str, first: str, years: int = 2) -> str:
    a = to_float(last)
    b = to_float(first)
    if a is None or b in (None, 0) or a <= 0 or b <= 0:
        return "待补充"
    return f"{((a / b) ** (1 / years) - 1) * 100:.2f}%"


def format_wan(value: str) -> str:
    if value in (None, "", "待补充"):
        return "待补充"
    return f"{value} 万元"


def latest(metric: Metric | None) -> str:
    return metric.values[0] if metric and metric.values else "待补充"


def values3(metric: Metric | None) -> list[str]:
    values = list(metric.values) if metric else []
    while len(values) < 3:
        values.append("待补充")
    return values[:3]


def preferred_profit_metric(data: ReportData) -> tuple[str, Metric | None]:
    for metric_name in ("扣非归母净利润", "归母净利润", "净利润"):
        metric = data.metrics.get(metric_name)
        if metric:
            return metric_name, metric
    return "扣非归母净利润待补充", None


def preferred_profit_values(metrics: dict[str, Any]) -> tuple[str, list[str]]:
    for metric_name in ("扣非归母净利润", "归母净利润", "净利润"):
        payload = metrics.get(metric_name)
        if payload:
            return metric_name, payload.get("values", [])
    return "扣非归母净利润待补充", []


def metric_floats(metric: Metric | None) -> list[float] | None:
    if not metric:
        return None
    values = [to_float(value) for value in values3(metric)]
    if any(value is None for value in values):
        return None
    return [float(value) for value in values]


def source_line(data: ReportData, metric: Metric | None) -> str:
    if not metric:
        return "来源：待补充"
    return f"来源：{data.pdf_title}，公告日期 {data.pdf_date}，第 {metric.page} 页"


def drop_metric(data: ReportData, metric_name: str, reason: str) -> None:
    if metric_name in data.metrics:
        data.metrics.pop(metric_name)
        data.warnings.append(f"{metric_name} 已降为待补充：{reason}")


def sanitize_metrics(data: ReportData) -> None:
    revenue = data.metrics.get("营业收入")
    revenue_values = metric_floats(revenue)
    if revenue and (not revenue_values or any(value < 1000 for value in revenue_values)):
        drop_metric(data, "营业收入", "营业收入数值过小或不完整，疑似抽到页码/日期")
        revenue_values = None
    max_revenue = max(revenue_values) if revenue_values else None

    for metric_name in ("净利润", "归母净利润", "扣非归母净利润"):
        metric = data.metrics.get(metric_name)
        values = metric_floats(metric)
        if not metric or not values:
            continue
        if max_revenue and all(abs(value) < 1000 for value in values) and max_revenue > 10000:
            drop_metric(data, metric_name, "利润数值过小且与收入规模不匹配，疑似误抽每股/页码数据")
            continue
        if max_revenue and any(abs(value) > max_revenue * 1.2 for value in values):
            drop_metric(data, metric_name, "利润绝对值超过收入规模，疑似单位或字段误抽")

    cash = data.metrics.get("经营现金流")
    cash_values = metric_floats(cash)
    if cash and cash_values:
        if all(abs(value) < 100 for value in cash_values):
            drop_metric(data, "经营现金流", "现金流数值过小，疑似抽到页码/日期")
        elif max_revenue and any(abs(value) > max_revenue * 5 for value in cash_values):
            drop_metric(data, "经营现金流", "现金流绝对值远高于收入规模，疑似单位误抽")

    for metric_name in ("毛利率", "研发费用率"):
        metric = data.metrics.get(metric_name)
        values = metric_floats(metric)
        if metric and (not values or any(value < 0 or value > 100 for value in values)):
            drop_metric(data, metric_name, "百分比超出 0-100 合理区间")


def apply_manual_corrections(data: ReportData) -> None:
    correction = MANUAL_CORRECTIONS.get(data.company)
    if not correction:
        return
    if correction.get("board"):
        data.item["board"] = correction["board"]
    if correction.get("business"):
        data.business = correction["business"]
    for metric_name in correction.get("drop_metrics", []):
        data.metrics.pop(metric_name, None)
    for metric_name, payload in correction.get("metrics", {}).items():
        data.metrics[metric_name] = Metric(
            name=metric_name,
            values=list(payload["values"]),
            page=payload["page"],
            label=payload["label"],
            source="招股说明书人工复核",
            note="人工校验口径覆盖自动抽取结果",
        )
    if correction.get("customer"):
        data.customer = {**data.customer, **correction["customer"]}
    if correction.get("supplier"):
        data.supplier = {**data.supplier, **correction["supplier"]}
    if correction.get("post_period_note"):
        data.source_notes.append({"type": "post_period", "text": correction["post_period_note"]})


def post_period_note_html(data: ReportData) -> str:
    notes = [note["text"] for note in data.source_notes if note.get("type") == "post_period"]
    if not notes:
        return ""
    return "".join(f"<p class='finance-note'><strong>审计截止日后/2026H1 预计：</strong>{esc(note.replace('审计截止日后/2026H1 预计：', ''))}</p>" for note in notes)


def risk_profile(data: ReportData) -> list[tuple[str, str, str]]:
    rev = data.metrics.get("营业收入")
    profit_label, profit = preferred_profit_metric(data)
    cash = data.metrics.get("经营现金流")
    gm = data.metrics.get("毛利率")
    customer = data.customer.get("ratio", "待补充")
    risks = []
    if customer != "待补充":
        pct = to_float(customer)
        if pct and pct >= 60:
            risks.append(("客户集中", f"2025 年前五大客户合计占比约 {customer}，客户波动会直接影响收入质量。", "高"))
        else:
            risks.append(("客户结构", f"2025 年前五大客户合计占比约 {customer}，需继续看单一客户依赖。", "中"))
    if cash and latest(cash).startswith("-"):
        risks.append(("现金流", f"2025 年经营现金流为 {format_wan(latest(cash))}，经营造血需要重点复核。", "高"))
    if gm and len(gm.values) >= 3:
        risks.append(("毛利率", f"毛利率为 {' / '.join(values3(gm))}，需要结合产品结构解释变化。", "中"))
    if rev and profit:
        risks.append(("增长质量", f"2025 年收入 {format_wan(latest(rev))}，{profit_label} {format_wan(latest(profit))}，重点看利润是否跟随收入。", "中"))
    if not risks:
        risks.append(("数据限制", "关键财务或客户数据抽取不完整，先不做经营质量判断。", "高"))
    return risks[:4]


def classification_sentence(data: ReportData) -> str:
    rev = data.metrics.get("营业收入")
    profit_label, profit = preferred_profit_metric(data)
    cash = data.metrics.get("经营现金流")
    customer = data.customer.get("ratio", "待补充")
    parts = []
    if rev:
        rv = values3(rev)
        parts.append(f"2025 年收入 {format_wan(rv[0])}，三年复合增速 {cagr(rv[0], rv[2])}")
    if profit:
        parts.append(f"2025 年{profit_label} {format_wan(values3(profit)[0])}")
    if cash:
        parts.append(f"经营现金流 {format_wan(values3(cash)[0])}")
    if customer != "待补充":
        parts.append(f"前五大客户占比约 {customer}")
    if not parts:
        return "本版仅确认 IPO 状态和来源文件，关键经营数据待补充。"
    return "；".join(parts) + "。"


def score_rows(data: ReportData) -> list[dict[str, str]]:
    rev = data.metrics.get("营业收入")
    profit_label, profit = preferred_profit_metric(data)
    gm = data.metrics.get("毛利率")
    cash = data.metrics.get("经营现金流")
    customer = data.customer.get("ratio", "待补充")
    score = [
        ("行业景气度", str(data.item.get("industryScore", "待补充")), data.item.get("scoreNote", "按行业和上市阶段初筛，需结合公司数据复核。")),
        ("收入增速", "4" if rev and cagr(values3(rev)[0], values3(rev)[2]) != "待补充" else "待补充", f"收入三年复合增速 {cagr(values3(rev)[0], values3(rev)[2]) if rev else '待补充'}；2025/2024 同比 {pct_change(values3(rev)[0], values3(rev)[1]) if rev else '待补充'}。"),
        ("净利润质量", "3" if profit else "待补充", f"2025 年{profit_label} {format_wan(latest(profit))}；需结合非经常性损益和费用率复核。"),
        ("毛利率趋势", "3" if gm else "待补充", f"毛利率 {' / '.join(values3(gm)) if gm else '待补充'}。"),
        ("现金流", "4" if cash and not latest(cash).startswith("-") else ("2" if cash else "待补充"), f"2025 年经营现金流 {format_wan(latest(cash))}。"),
        ("客户集中度", "2" if to_float(customer) and to_float(customer) >= 60 else ("4" if customer != "待补充" else "待补充"), f"2025 年前五大客户占比 {customer}。"),
        ("募投合理性", "3" if data.fundraising.get("amount") != "待补充" else "待补充", f"募投合计 {format_wan(data.fundraising.get('amount'))}；需逐项目复核产能消化。"),
        ("可比公司估值", "待补充", "发行价和发行市值未披露前，不做估值结论。"),
        ("上市后交易风险", "3", "注册生效提高确定性，但发行价、流通盘和上市日期待公告。"),
    ]
    return [{"name": n, "score": s, "note": note} for n, s, note in score]


def next_version(report_dir: Path, stem: str) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    version = 1
    while True:
        path = report_dir / f"{REPORT_DATE}-{stem}-v{version}.html"
        if not path.exists():
            return path
        version += 1


CSS = """
:root{--ink:#111827;--muted:#667085;--line:#d8e1ea;--blue:#0a84ff;--green:#11a981;--orange:#b9782f;--red:#c2410c;--bg:#f5f7fb;--dark:#111923}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","PingFang SC","Microsoft YaHei",Arial,sans-serif;letter-spacing:0}a{color:#006edb;text-decoration:none}
.hero{min-height:440px;background:linear-gradient(90deg,rgba(245,247,251,.98),rgba(245,247,251,.78),rgba(245,247,251,.35)),url('__HERO__') center/cover no-repeat;display:flex;align-items:flex-end;padding:62px 7vw}.hero h1{font-size:54px;line-height:1.06;margin:12px 0 16px;max-width:980px}.hero p{font-size:21px;line-height:1.65;color:#3f5166;max-width:920px}.eyebrow{font-size:13px;color:var(--blue);font-weight:850;text-transform:uppercase;letter-spacing:.08em}.tag{display:inline-flex;padding:6px 10px;border-radius:999px;background:#e8f3ff;color:#075ca8;font-size:12px;font-weight:800;margin-right:8px}
main{padding:30px 7vw 76px}.grid{display:grid;gap:16px}.facts{grid-template-columns:repeat(5,minmax(0,1fr));margin-top:-72px}.card,.panel{background:rgba(255,255,255,.88);border:1px solid rgba(150,168,190,.38);border-radius:18px;box-shadow:0 18px 46px rgba(22,44,70,.08);backdrop-filter:blur(18px)}.card{padding:18px}.card span{display:block;color:var(--muted);font-size:12px;font-weight:800}.card strong{display:block;font-size:24px;line-height:1.18;margin:8px 0}.card small,.source{font-size:12px;color:#738297;line-height:1.45}.panel{padding:26px;margin-top:18px}.panel h2{font-size:28px;margin:0 0 16px}.panel h3{font-size:19px;margin:16px 0 8px}.panel p{line-height:1.78;color:#3f5268}.dark{background:linear-gradient(135deg,#101923,#183546);color:white}.dark p,.dark .source{color:#c9d6e4}.two{grid-template-columns:1fr 1fr}.three{grid-template-columns:repeat(3,1fr)}.flow{grid-template-columns:repeat(3,1fr)}.box{border:1px solid #dce6ef;border-radius:16px;padding:16px;background:#f8fbff}.risk{border-left:4px solid var(--orange);background:#fffaf0}.risk.high{border-left-color:var(--red);background:#fff7f5}.finance-cards{grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.finance-card{border:1px solid #dce6ef;border-radius:16px;padding:16px;background:#f8fbff}.finance-card span{display:block;color:var(--muted);font-size:12px;font-weight:850}.finance-card strong{display:block;margin:8px 0;font-size:24px;line-height:1.16}.finance-card small{color:#607086;line-height:1.45}.finance-card.is-alert{background:#fff7f5;border-color:#f0c7bc}.finance-note{margin-top:14px;color:#607086;font-size:13px;line-height:1.6}.judgement-cards{grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.judgement-card{border:1px solid #dce6ef;border-radius:16px;padding:16px;background:#f8fbff}.judgement-card h3{font-size:17px;margin:0 0 8px}.judgement-card p{margin:0;color:#3f5268;line-height:1.65}
table{width:100%;border-collapse:collapse;background:white;border-radius:14px;overflow:hidden;font-size:14px}th,td{padding:12px 13px;border-bottom:1px solid #e8edf3;text-align:left;vertical-align:top;line-height:1.55}th{background:#eef5fb;color:#314a64}tr:last-child td{border-bottom:0}.score{display:grid;grid-template-columns:150px 1fr 52px;gap:12px;align-items:center;margin:12px 0}.track{height:10px;background:#e5edf6;border-radius:99px;overflow:hidden}.track i{display:block;height:100%;width:var(--w);background:linear-gradient(90deg,var(--blue),var(--green))}
.landscape{grid-template-columns:minmax(0,1.05fr) minmax(0,.95fr);align-items:stretch}.share-bars{display:grid;gap:12px}.share-row{display:grid;grid-template-columns:132px minmax(0,1fr) 72px;gap:10px;align-items:center}.share-row span{font-size:13px;color:#39506a;font-weight:800}.share-row strong{font-size:13px;text-align:right}.share-track{height:12px;border-radius:999px;background:#e5edf6;overflow:hidden}.share-track i{display:block;height:100%;width:var(--w);background:linear-gradient(90deg,#0a84ff,#11a981)}.landscape-note{margin-top:12px;padding:12px 14px;border-radius:12px;background:#f0f7ff;color:#39506a;font-size:13px;line-height:1.6}
.layout{display:grid;grid-template-columns:220px 1fr;gap:20px}.toc{position:sticky;top:14px;align-self:start}.toc a{display:block;padding:8px 0;color:#5b6e82}.section{scroll-margin-top:24px}.note{color:#75859a;font-size:13px}
@media(max-width:1000px){.hero{padding:42px 22px 80px}.hero h1{font-size:38px}.facts,.two,.three,.flow,.layout,.landscape{grid-template-columns:1fr}main{padding:24px 18px 60px}.toc{position:static}.score{grid-template-columns:120px 1fr 42px}.share-row{grid-template-columns:98px minmax(0,1fr) 56px}}
"""


def facts(data: ReportData) -> str:
    rev = data.metrics.get("营业收入")
    profit_label, profit = preferred_profit_metric(data)
    gm = data.metrics.get("毛利率")
    cash = data.metrics.get("经营现金流")
    items = [
        ("IPO 状态", data.item.get("status"), data.item.get("latestProgress")),
        ("2025 收入", format_wan(latest(rev)), source_line(data, rev)),
        (f"2025 {profit_label}", format_wan(latest(profit)), source_line(data, profit)),
        ("毛利率", latest(gm), source_line(data, gm)),
        ("经营现金流", format_wan(latest(cash)), source_line(data, cash)),
    ]
    return "".join(f"<div class='card'><span>{esc(k)}</span><strong>{esc(v)}</strong><small>{esc(s)}</small></div>" for k, v, s in items)


def financial_table(data: ReportData) -> str:
    rows = []
    for metric in METRICS:
        item = data.metrics.get(metric)
        if item:
            values = values3(item)
            page = item.page
            source = f"{data.pdf_title}，公告日期 {data.pdf_date}，第 {page} 页"
        else:
            values = ["待补充", "待补充", "待补充"]
            source = "待补充"
        unit = "%" if metric in {"毛利率", "研发费用率"} else "万元"
        rows.append(f"<tr><td>{esc(metric)}</td><td>{esc(values[0])}</td><td>{esc(values[1])}</td><td>{esc(values[2])}</td><td>{unit}</td><td>{esc(source)}</td></tr>")
    return "<table><thead><tr><th>指标</th><th>2025</th><th>2024</th><th>2023</th><th>单位</th><th>来源</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def ratio_percent(numerator: str, denominator: str) -> str:
    a = to_float(numerator)
    b = to_float(denominator)
    if a is None or b in (None, 0):
        return "待补充"
    return f"{a / b * 100:.2f}%"


def ratio_multiple(numerator: str, denominator: str) -> str:
    a = to_float(numerator)
    b = to_float(denominator)
    if a is None or b is None:
        return "待补充"
    if b <= 0:
        return "不适用"
    return f"{a / b:.2f} 倍"


def finance_cards(data: ReportData) -> str:
    rev = data.metrics.get("营业收入")
    profit_label, profit = preferred_profit_metric(data)
    cash = data.metrics.get("经营现金流")
    customer = data.customer.get("ratio", "待补充")
    revenue_values = values3(rev)
    profit_values = values3(profit)
    cash_values = values3(cash)
    cards = [
        (
            "收入",
            format_wan(revenue_values[0]),
            f"三年复合增速 {cagr(revenue_values[0], revenue_values[2])}；2025/2024 同比 {pct_change(revenue_values[0], revenue_values[1])}",
            "",
        ),
        (
            "利润率",
            ratio_percent(profit_values[0], revenue_values[0]),
            f"2025 {profit_label} {format_wan(profit_values[0])}",
            "",
        ),
        (
            "现金流/利润",
            ratio_multiple(cash_values[0], profit_values[0]),
            f"经营现金流 {format_wan(cash_values[0])}",
            "is-alert" if cash and latest(cash).startswith("-") else "",
        ),
        (
            "客户集中度",
            customer,
            "前五大客户收入占比；待补充表示未稳定定位标准表",
            "is-alert" if to_float(customer) and to_float(customer) >= 60 else "",
        ),
    ]
    body = "".join(
        f"<div class='finance-card {klass}'><span>{esc(title)}</span><strong>{esc(value)}</strong><small>{esc(note)}</small></div>"
        for title, value, note, klass in cards
    )
    warnings = ""
    if data.warnings:
        warnings = "<p class='finance-note'>数据闸门：" + esc("；".join(data.warnings[:3])) + "</p>"
    return f"<div class='grid finance-cards'>{body}</div>{warnings}"


def finance_judgement_cards(data: ReportData) -> str:
    rev = data.metrics.get("营业收入")
    profit_label, profit = preferred_profit_metric(data)
    cash = data.metrics.get("经营现金流")
    revenue_values = values3(rev)
    profit_values = values3(profit)
    cash_values = values3(cash)
    cards = [
        (
            "增长",
            f"2025 年收入 {format_wan(revenue_values[0])}，三年复合增速 {cagr(revenue_values[0], revenue_values[2])}。这个数字只说明历史放量，下一步要看发行前更新能否延续。",
        ),
        (
            "利润质量",
            f"2025 年{profit_label} {format_wan(profit_values[0])}，利润率 {ratio_percent(profit_values[0], revenue_values[0])}。若利润字段待补充，本版不做盈利质量判断。",
        ),
        (
            "现金流",
            f"2025 年经营现金流 {format_wan(cash_values[0])}，现金流/利润为 {ratio_multiple(cash_values[0], profit_values[0])}。这个指标用来判断利润有没有变成现金。",
        ),
    ]
    return "<div class='grid judgement-cards'>" + "".join(f"<div class='judgement-card'><h3>{esc(title)}</h3><p>{esc(text)}</p></div>" for title, text in cards) + "</div>"


def thesis_text(data: ReportData) -> str:
    status = data.item.get("status", "待补充")
    board = data.item.get("board", "待补充")
    industry = data.item.get("industry", "待补充")
    return (
        f"{data.company}当前处于{board}{status}阶段，所属行业为{industry}。"
        f"{classification_sentence(data)}本版把它放进上市前研究池，核心不是给结论，而是把业务、财务、现金流和客户集中度四件事摆清楚。"
    )


def industry_landscape_html(data: ReportData) -> str:
    landscape = INDUSTRY_LANDSCAPES.get(data.company)
    if not landscape:
        return ""
    rows = landscape["rows"]
    bar_rows = []
    for row in rows:
        percent = row.get("percent")
        if percent is None:
            continue
        width = max(2, min(100, float(percent)))
        bar_rows.append(
            f"<div class='share-row'><span>{esc(row['name'])}</span><div class='share-track'><i style='--w:{width:.2f}%'></i></div><strong>{esc(row['value'])}</strong></div>"
        )
    if not bar_rows:
        bar_rows.append("<p class='note'>招股书未披露可直接画成百分比的精确市占率；本区只列官方披露的排名、竞争层级和待补口径，不做假图。</p>")
    table_rows = "".join(
        f"<tr><td>{esc(row['name'])}</td><td>{esc(row['value'])}</td><td>{esc(row['note'])}</td></tr>"
        for row in rows
    )
    return f"""
<div class="grid landscape">
  <div class="box"><h3>{esc(landscape['title'])}</h3><div class="share-bars">{''.join(bar_rows)}</div><p class="landscape-note"><strong>读图结论：</strong>{esc(landscape['observation'])}</p></div>
  <div class="box"><h3>市占 / 排名 / 占比口径</h3><table><thead><tr><th>对象</th><th>占比或位置</th><th>口径限制</th></tr></thead><tbody>{table_rows}</tbody></table></div>
</div>
<p class="source">{esc(landscape['source'])}</p>
"""


def industry_position_html(data: ReportData) -> str:
    industry = data.item.get("industry", "待补充")
    board = data.item.get("board", "待补充")
    score_note = data.item.get("scoreNote", "待补充")
    progress = data.item.get("latestProgress", "待补充")
    return f"""
{industry_landscape_html(data)}
<div class="grid three">
  <div class="box"><h3>赛道</h3><p>{esc(industry)}</p><p class="source">来源：{esc(data.item.get('sourceName'))}，公告日期 {esc(data.item.get('sourceDate'))}，文件《{esc(data.item.get('fileName'))}》。</p></div>
  <div class="box"><h3>板块匹配</h3><p>{esc(board)}。先按监管披露板块判断属性，后续再结合产品结构和可比公司复核估值口径。</p></div>
  <div class="box"><h3>上市进度</h3><p>{esc(progress)}。发行价、发行市值和上市日期没有公告前，不做交易结论。</p></div>
</div>
<p class="note">行业初判：{esc(score_note)} 本区优先列官方文件披露的市占、排名或可计算占比；文件未披露精确市占时明确标注，不用估算数冒充市场份额。</p>
"""


def business_ladder_html(data: ReportData) -> str:
    rev = data.metrics.get("营业收入")
    profit_label, profit = preferred_profit_metric(data)
    cash = data.metrics.get("经营现金流")
    rows = [
        (
            "1. 公司卖什么",
            data.business.get("text", "待补充"),
            f"来源：{data.pdf_title}，公告日期 {data.pdf_date}，第 {data.business.get('page', '待补充')} 页",
        ),
        (
            "2. 有没有收入验证",
            f"2025 年营业收入 {format_wan(latest(rev))}，2023-2025 年复合增速 {cagr(values3(rev)[0], values3(rev)[2])}。",
            source_line(data, rev),
        ),
        (
            "3. 利润和现金能否跟上",
            f"2025 年{profit_label} {format_wan(latest(profit))}，经营现金流 {format_wan(latest(cash))}，现金流/利润为 {ratio_multiple(latest(cash), latest(profit))}。",
            f"{source_line(data, profit)}；{source_line(data, cash)}",
        ),
        (
            "4. 上市前最后验证",
            f"发行价、发行市值、上市日期仍为 {data.item.get('expectedListingTime', '待补充')}。这些披露后再判断上市后交易风险。",
            "来源：发行公告/上市公告书，未披露则标记为待补充。",
        ),
    ]
    return "<div class='grid two'>" + "".join(
        f"<div class='box'><h3>{esc(title)}</h3><p>{esc(text)}</p><p class='source'>{esc(source)}</p></div>"
        for title, text, source in rows
    ) + "</div>"


def chain_flow_html(data: ReportData) -> str:
    customer = f"2025 年前五大客户占比 {data.customer.get('ratio', '待补充')}；金额 {format_wan(data.customer.get('amount'))}。"
    supplier = f"2025 年前五大供应商占比 {data.supplier.get('ratio', '待补充')}；金额 {format_wan(data.supplier.get('amount'))}。"
    return f"""
<div class="grid flow">
  <div class="box"><h3>上游</h3><p>{esc(supplier)}</p><p class="source">来源：{esc(data.pdf_title)}，公告日期 {esc(data.pdf_date)}，第 {esc(data.supplier.get('page'))} 页。</p></div>
  <div class="box"><h3>公司能力</h3><p>{esc(data.business.get('text', '待补充'))}</p></div>
  <div class="box"><h3>下游</h3><p>{esc(customer)}</p><p class="source">来源：{esc(data.pdf_title)}，公告日期 {esc(data.pdf_date)}，第 {esc(data.customer.get('page'))} 页。</p></div>
</div>
"""


def source_rows(data: ReportData) -> str:
    rows = [
        {
            "level": "官方项目状态",
            "name": data.item.get("sourceName"),
            "date": data.item.get("sourceDate"),
            "file": data.item.get("fileName"),
            "use": "核对公司、板块、状态、申报时间、保荐机构和披露目录",
            "note": data.item.get("officialLink"),
        },
        {
            "level": "官方披露文件",
            "name": data.pdf_title,
            "date": data.pdf_date,
            "file": str(data.pdf.relative_to(ROOT)) if data.pdf else "待补充",
            "use": "财务、客户、供应商、募投和业务描述",
            "note": "本地 PDF 已校验文件头；若来自第三方镜像，已在原始抓取阶段用交易所目录核对",
        },
        {
            "level": "生成资产",
            "name": "GPT img2 生成 IPO 研究主视觉",
            "date": "2026-07-09",
            "file": "dashboard/assets/ipo-hero.png",
            "use": "报告视觉资产",
            "note": "不作为事实来源",
        },
    ]
    return "".join(
        f"<tr><td>{esc(r['level'])}</td><td>{esc(r['name'])}</td><td>{esc(r['date'])}</td><td>{esc(r['file'])}</td><td>{esc(r['use'])}</td><td>{esc(r['note'])}</td></tr>"
        for r in rows
    )


def score_html(data: ReportData) -> str:
    out = []
    for row in score_rows(data):
        try:
            width = int(row["score"]) * 20
        except Exception:
            width = 0
        out.append(
            f"<div class='score'><span>{esc(row['name'])}</span><div class='track'><i style='--w:{width}%'></i></div><strong>{esc(row['score'])}</strong></div>"
        )
    return "".join(out)


def score_table(data: ReportData) -> str:
    rows = "".join(f"<tr><td>{esc(r['name'])}</td><td>{esc(r['score'])}</td><td>{esc(r['note'])}</td></tr>" for r in score_rows(data))
    return "<table><thead><tr><th>维度</th><th>分数</th><th>依据/限制</th></tr></thead><tbody>" + rows + "</tbody></table>"


def overview_html(data: ReportData) -> str:
    risks = risk_profile(data)
    risk_cards = "".join(
        f"<div class='box risk {'high' if level == '高' else ''}'><h3>{esc(name)}</h3><p>{esc(text)}</p><span class='tag'>{esc(level)}优先级</span></div>"
        for name, text, level in risks
    )
    business = data.business.get("text", "待补充")
    css = CSS.replace("__HERO__", SHARED_HERO)
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(data.company)} 概览</title><style>{css}</style></head>
<body>
<header class="hero"><div><div class="eyebrow">Overview · {REPORT_DATE} · a-share-company-html-research</div><h1>{esc(data.company)}</h1><p>{esc(thesis_text(data))} 这份概览只使用可追溯到招股书/官方项目状态的数据，无法稳定抽取的项目保留“待补充”。</p><span class="tag">{esc(data.item.get('board'))}</span><span class="tag">{esc(data.item.get('status'))}</span><span class="tag">{esc(data.item.get('classification'))}</span></div></header>
<main>
  <section class="grid facts">{facts(data)}</section>
  <section class="panel dark"><h2>核心判断</h2><p><span class="tag">公司披露</span>{esc(business)}</p><p><span class="tag">本报告推断</span>研究重点不是“是否已经注册生效”，而是收入增长、利润质量、现金流和客户/供应商集中度能否相互印证。当前更适合作为上市前研究排队标的，不构成投资建议。</p></section>
  <section class="panel"><h2>行业位置</h2>{industry_position_html(data)}</section>
  <section class="panel"><h2>业务/产品阶梯</h2>{business_ladder_html(data)}</section>
  <section class="panel"><h2>核心财务读数</h2>{finance_cards(data)}{post_period_note_html(data)}</section>
  <section class="panel"><h2>上下游读数</h2>{chain_flow_html(data)}</section>
  <section class="grid two">
    <div class="panel"><h2>募投与下一步</h2><p>募投合计：<strong>{esc(format_wan(data.fundraising.get('amount')))}</strong>。募投合理性要继续看项目是否解决真实产能/技术瓶颈，以及上市后折旧摊销压力。</p><p class="source">来源：{esc(data.pdf_title)}，第 {esc(data.fundraising.get('page'))} 页。</p></div>
    <div class="panel"><h2>读者先看什么</h2><p>先看收入是否真实放量，再看利润能否变成现金，最后看客户和供应商集中度是否会放大上市后的波动。</p><p class="note">发行价、发行市值、上市日期未披露前，估值和交易风险只列跟踪项，不做确定性判断。</p></div>
  </section>
  <section class="panel"><h2>后续只盯事项</h2><div class="grid two">{risk_cards}</div></section>
  <section class="panel"><h2>来源列表</h2><table><thead><tr><th>级别</th><th>来源</th><th>公告日期</th><th>文件</th><th>用途</th><th>备注/链接</th></tr></thead><tbody>{source_rows(data)}</tbody></table></section>
</main></body></html>"""


def research_html(data: ReportData) -> str:
    risks = risk_profile(data)
    risk_cards = "".join(
        f"<div class='box risk {'high' if level == '高' else ''}'><h3>{esc(name)}</h3><p>{esc(text)}</p><span class='tag'>{esc(level)}优先级</span></div>"
        for name, text, level in risks
    )
    css = CSS.replace("__HERO__", SHARED_HERO)
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(data.company)} 详细调研</title><style>{css}</style></head>
<body>
<header class="hero"><div><div class="eyebrow">Detailed Research · {REPORT_DATE}</div><h1>{esc(data.company)}：上市前数据版调研</h1><p>本版按最新版 skill 重跑，核心数据来自招股书/注册稿表格；不再使用关键词附近数字拼接。缺失或不稳定抽取字段标记为“待补充/待复核”。</p></div></header>
<main class="layout">
  <nav class="toc panel"><a href="#scope">0. 口径</a><a href="#facts">1. 事实表</a><a href="#business">2. 公司画像</a><a href="#position">3. 行业位置</a><a href="#ipo">4. IPO 与募投</a><a href="#ladder">5. 业务阶梯</a><a href="#finance">6. 财务</a><a href="#chain">7. 上下游</a><a href="#risk">8. 风险</a><a href="#sources">9. 来源</a><a href="#terms">10. 术语</a></nav>
  <div>
    <section id="scope" class="panel section"><h2>0. 口径说明 / 数据可信度</h2><p><span class="tag">官方事实</span>公司状态、板块、申报时间、保荐机构来自交易所项目状态和看板基础数据。<span class="tag">公司披露</span>财务、客户、供应商和募投来自招股书 PDF。<span class="tag">待复核</span>若字段显示待补充，表示脚本未能稳定定位标准表格，未做猜测。</p></section>
    <section id="facts" class="panel section"><h2>1. 关键事实表</h2><table><thead><tr><th>项目</th><th>内容</th><th>来源/备注</th></tr></thead><tbody>
      <tr><td>公司</td><td>{esc(data.company)}</td><td>{esc(data.item.get('sourceName'))}</td></tr>
      <tr><td>板块/状态</td><td>{esc(data.item.get('board'))} / {esc(data.item.get('status'))}</td><td>{esc(data.item.get('latestProgress'))}</td></tr>
      <tr><td>申报时间</td><td>{esc(data.item.get('applyDate'))}</td><td>官方项目状态</td></tr>
      <tr><td>预计上市/发行</td><td>{esc(data.item.get('expectedListingTime'))}</td><td>发行公告/上市公告书未披露则保持待补充</td></tr>
      <tr><td>保荐机构</td><td>{esc(data.item.get('sponsor'))}</td><td>官方项目状态</td></tr>
      <tr><td>招股书</td><td>{esc(data.pdf_title)}</td><td>公告日期 {esc(data.pdf_date)}；文件 {esc(str(data.pdf.relative_to(ROOT)) if data.pdf else '待补充')}</td></tr>
    </tbody></table></section>
    <section id="business" class="panel section"><h2>2. 公司画像</h2><p><span class="tag">公司披露</span>{esc(data.business.get('text'))}</p><p class="source">来源：{esc(data.pdf_title)}，公告日期 {esc(data.pdf_date)}，第 {esc(data.business.get('page'))} 页。</p></section>
    <section id="position" class="panel section"><h2>3. 行业位置</h2>{industry_position_html(data)}</section>
    <section id="ipo" class="panel section"><h2>4. IPO 进度与募投</h2><p>当前状态：{esc(data.item.get('status'))}。募投合计：{esc(format_wan(data.fundraising.get('amount')))}。发行价、发行市值和上市日期未披露前，不做估值结论。</p><p class="source">募投来源：{esc(data.pdf_title)}，第 {esc(data.fundraising.get('page'))} 页。摘录：{esc(data.fundraising.get('snippet'))}</p></section>
    <section id="ladder" class="panel section"><h2>5. 业务/产品阶梯</h2>{business_ladder_html(data)}</section>
    <section id="finance" class="panel section"><h2>6. 财务分析</h2>{financial_table(data)}{post_period_note_html(data)}<h3>读表结论</h3><p>{esc(classification_sentence(data))}</p><h3>财务读数判断</h3>{finance_judgement_cards(data)}</section>
    <section id="chain" class="panel section"><h2>7. 客户、供应商与产业链</h2>{chain_flow_html(data)}<h3>原始摘录定位</h3><div class="grid two"><div class="box"><h3>客户集中度</h3><p class="source">第 {esc(data.customer.get('page'))} 页；摘录：{esc(data.customer.get('snippet'))}</p></div><div class="box"><h3>供应商集中度</h3><p class="source">第 {esc(data.supplier.get('page'))} 页；摘录：{esc(data.supplier.get('snippet'))}</p></div></div></section>
    <section id="risk" class="panel section"><h2>8. 风险矩阵</h2><div class="grid two">{risk_cards}</div></section>
    <section class="panel section"><h2>9. 后续跟踪清单</h2><table><thead><tr><th>优先级</th><th>看什么</th><th>触发条件</th><th>意义</th></tr></thead><tbody>
      <tr><td>高</td><td>发行价、发行市值、上市日期</td><td>发行公告/上市公告书披露</td><td>决定上市后交易风险和估值框架</td></tr>
      <tr><td>高</td><td>最近一期财务更新</td><td>发行前更新或中报披露</td><td>验证增长和利润质量是否延续</td></tr>
      <tr><td>中</td><td>客户/供应商集中度变化</td><td>新招股书或问询回复更新</td><td>判断收入稳定性和议价能力</td></tr>
      <tr><td>中</td><td>募投项目调整</td><td>注册稿、发行公告或上市公告书变化</td><td>判断资本开支和产能消化压力</td></tr>
    </tbody></table></section>
    <section id="sources" class="panel section"><h2>10. 来源列表</h2><table><thead><tr><th>级别</th><th>来源</th><th>公告日期</th><th>文件</th><th>用途</th><th>备注/链接</th></tr></thead><tbody>{source_rows(data)}</tbody></table></section>
    <section id="terms" class="panel section"><h2>11. 公式与专业名词解释</h2><table><thead><tr><th>术语/公式</th><th>解释</th><th>使用限制</th></tr></thead><tbody>
      <tr><td>收入复合增速</td><td>收入复合增速 = (期末收入 / 期初收入)^(1/年数) - 1。</td><td>只说明历史增长，不代表上市后增长。</td></tr>
      <tr><td>扣非归母净利润</td><td>扣除非经常性损益后归属于母公司股东的净利润。</td><td>更接近主营质量，但仍需看收入确认、费用和现金流。</td></tr>
      <tr><td>毛利率</td><td>毛利率 = （收入 - 成本） / 收入。</td><td>产品结构变化会扭曲趋势，不能单独判断竞争力。</td></tr>
      <tr><td>经营现金流</td><td>经营活动产生的现金流量净额，反映业务造血。</td><td>成长扩张期可能被备货和应收扰动，需结合存货/应收。</td></tr>
      <tr><td>客户集中度</td><td>通常用前五大客户收入占比衡量。</td><td>集中度高不必然差，但需要验证客户稳定性和议价权。</td></tr>
    </tbody></table></section>
  </div>
</main></body></html>"""


def build_report_data(item: dict[str, Any]) -> ReportData:
    short = DIR_ALIASES[item["name"]]
    pdf = find_prospectus(short)
    data = ReportData(
        company=item["name"],
        short=short,
        pdf=pdf,
        pdf_date=source_date_from_name(pdf, item.get("sourceDate") or "待补充"),
        pdf_title=source_title_from_name(pdf),
        item=item,
    )
    if not pdf:
        data.warnings.append("未找到可用招股书 PDF")
        return data
    texts = page_texts(pdf, max_pages=100)
    data.metrics = extract_metrics(pdf)
    sanitize_metrics(data)
    data.business = extract_business(texts)
    data.customer = extract_ratio_section(pdf, ["前五大客户", "前五名客户"], "客户集中度")
    data.supplier = extract_ratio_section(pdf, ["前五大供应商", "前五名供应商"], "供应商集中度")
    data.fundraising = extract_fundraising(pdf)
    apply_manual_corrections(data)
    return data


def write_reports(data: ReportData) -> dict[str, Any]:
    report_dir = ROOT / "companies" / data.short / "reports"
    overview = next_version(report_dir, "overview")
    research = next_version(report_dir, "research")
    overview.write_text(overview_html(data), encoding="utf-8")
    research.write_text(research_html(data), encoding="utf-8")
    manifest = {
        "company": data.company,
        "generatedAt": REPORT_DATE,
        "generatedBy": "a-share-company-html-research",
        "mode": "structured_skill_rerun",
        "overview": str(overview.relative_to(ROOT)),
        "research": str(research.relative_to(ROOT)),
        "prospectusPdf": str(data.pdf.relative_to(ROOT)) if data.pdf else None,
        "pdfDate": data.pdf_date,
        "metrics": {k: {"values": v.values, "page": v.page, "label": v.label} for k, v in data.metrics.items()},
        "customer": data.customer,
        "supplier": data.supplier,
        "fundraising": data.fundraising,
        "sourceNotes": data.source_notes,
        "warnings": data.warnings,
    }
    (report_dir / f"{REPORT_DATE}-structured-skill-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"overview": overview, "research": research, "manifest": manifest}


def update_dashboard(data_obj: dict[str, Any], reports_obj: dict[str, Any], generated: dict[str, dict[str, Any]]) -> None:
    def pad(values: list[str] | None) -> list[str]:
        values = list(values or [])
        while len(values) < 3:
            values.append("待补充")
        return values[:3]

    for item in data_obj["items"]:
        name = item["name"]
        if name not in generated:
            continue
        result = generated[name]
        manifest = result["manifest"]
        item["reportStatus"] = "结构化数据版已重跑"
        metrics = manifest.get("metrics", {})
        revenue = pad(metrics.get("营业收入", {}).get("values"))
        profit_label, profit_payload_values = preferred_profit_values(metrics)
        profit = pad(profit_payload_values)
        gm = pad(metrics.get("毛利率", {}).get("values"))
        cash = pad(metrics.get("经营现金流", {}).get("values"))
        item["metrics"] = {
            "revenueGrowth": f"2025/2024/2023 营业收入：{', '.join(revenue)} 万元；三年复合增速 {cagr(revenue[0], revenue[2])}",
            "profitQuality": f"2025/2024/2023 {profit_label}：{', '.join(profit)} 万元",
            "grossMarginTrend": f"毛利率：{', '.join(gm)}",
            "cashFlow": f"经营现金流：{', '.join(cash)} 万元",
            "customerConcentration": f"2025 前五大客户占比：{manifest.get('customer', {}).get('ratio', '待补充')}",
            "fundraisingFit": f"募投合计：{format_wan(manifest.get('fundraising', {}).get('amount'))}",
            "peerValuation": "发行价/发行市值待补充",
            "tradingRisk": "注册生效但发行价、流通盘和上市公告书待披露",
        }
        item["scoreCompleteness"] = f"{sum(1 for m in METRICS if m in metrics)}/7"
        item["scoreNote"] = "已按最新版 skill 生成结构化数据版；关键财务指标来自招股书表格，缺失项不硬填。"
        reports_obj[name] = {
            "status": "结构化数据版已接入",
            "overviewUrl": "../" + str(result["overview"].relative_to(ROOT)),
            "researchUrl": "../" + str(result["research"].relative_to(ROOT)),
            "assetUrl": "../dashboard/assets/ipo-hero.png",
            "generatedBy": "a-share-company-html-research",
            "imageGeneratedBy": "GPT img2",
            "sourceBoundary": "已按最新版 skill 重跑：结构化抽取招股书财务表、客户/供应商集中度和募投字段；不再使用关键词数字拼接",
        }
    write_js_object(DASHBOARD_DATA, "window.IPO_DASHBOARD_DATA", data_obj)
    write_js_object(REPORTS_JS, "window.IPO_COMPANY_REPORTS", reports_obj)


def validate_html(paths: list[Path]) -> list[str]:
    problems = []
    banned = ["TODO", "TBD", "undefined", "NaN"]
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in banned:
            if token in text:
                problems.append(f"{path.relative_to(ROOT)} contains {token}")
        ids = re.findall(r'\sid="([^"]+)"', text)
        duplicates = sorted({value for value in ids if ids.count(value) > 1})
        if duplicates:
            problems.append(f"{path.relative_to(ROOT)} duplicate ids: {duplicates}")
        for match in re.findall(r"url\\('([^']+)'\\)|src=\"([^\"]+)\"", text):
            ref = next((x for x in match if x), "")
            if ref.startswith(("http", "#", "data:")):
                continue
            ref_path = (path.parent / ref).resolve()
            if not ref_path.exists():
                problems.append(f"{path.relative_to(ROOT)} missing asset {ref}")
    return problems


def validate_metric_payload(generated: dict[str, dict[str, Any]]) -> list[str]:
    problems = []
    for company, result in generated.items():
        metrics = result["manifest"].get("metrics", {})
        for metric_name in ("毛利率", "研发费用率"):
            values = metrics.get(metric_name, {}).get("values", [])
            for value in values:
                parsed = to_float(value)
                if parsed is None:
                    problems.append(f"{company} {metric_name} invalid value {value}")
                    continue
                if parsed < 0 or parsed > 100:
                    problems.append(f"{company} {metric_name} out of range {value}")
        for metric_name, payload in metrics.items():
            label = payload.get("label", "")
            if "分别为" in label:
                problems.append(f"{company} {metric_name} selected narrative line")
            if re.search(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?-\d", label):
                problems.append(f"{company} {metric_name} selected range line")
    return problems


def main() -> None:
    data_obj = parse_js_object(DASHBOARD_DATA)
    reports_obj = parse_js_object(REPORTS_JS)
    generated: dict[str, dict[str, Any]] = {}
    html_paths: list[Path] = []
    targets = {name.strip() for name in os.environ.get("IPO_TARGETS", "").split("|") if name.strip()}
    for item in data_obj["items"]:
        if item["name"] in SKIP:
            continue
        if item["name"] not in DIR_ALIASES:
            continue
        if targets and item["name"] not in targets and DIR_ALIASES[item["name"]] not in targets:
            continue
        report_data = build_report_data(item)
        result = write_reports(report_data)
        generated[item["name"]] = result
        html_paths.extend([result["overview"], result["research"]])
        print(
            f"{item['name']} -> metrics={len(report_data.metrics)}/7 overview={result['overview'].name} research={result['research'].name}",
            flush=True,
        )
    for item in data_obj["items"]:
        if item["name"] in generated or item["name"] in SKIP or item["name"] not in DIR_ALIASES:
            continue
        report_dir = ROOT / "companies" / DIR_ALIASES[item["name"]] / "reports"
        manifest_path = report_dir / f"{REPORT_DATE}-structured-skill-manifest.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        overview = ROOT / manifest["overview"]
        research = ROOT / manifest["research"]
        if overview.exists() and research.exists():
            generated[item["name"]] = {"overview": overview, "research": research, "manifest": manifest}
            html_paths.extend([overview, research])
    update_dashboard(data_obj, reports_obj, generated)
    problems = validate_html(html_paths)
    problems.extend(validate_metric_payload(generated))
    summary = {
        "generatedAt": REPORT_DATE,
        "generatedCompanies": list(generated.keys()),
        "generatedReportCount": len(html_paths),
        "validationProblems": problems,
    }
    out = ROOT / "reports" / f"structured_skill_rerun_{REPORT_DATE}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if problems:
        print("VALIDATION_PROBLEMS")
        for problem in problems:
            print(problem)
        raise SystemExit(1)
    print("VALIDATION_OK")
    print(out)


if __name__ == "__main__":
    main()
