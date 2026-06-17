from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
SITE_DIR = ROOT / "site"
REPORTS_DIR = ROOT / "reports"
DB_PATH = DATA_DIR / "monitor.sqlite"


@dataclass(frozen=True)
class Program:
    name: str
    start_date: str
    end_date: str | None
    limit_amount: Decimal | None
    limit_currency: str | None
    limit_shares: Decimal | None
    share_base: Decimal | None
    basis: str
    source_url: str
    source_title: str
    source_date: str
    period_label: str
    limit_label: str
    us_amount: Decimal | None = None
    us_currency: str | None = None
    us_shares: Decimal | None = None
    us_ads: Decimal | None = None
    us_ordinary_shares_per_ads: Decimal | None = None
    us_as_of: str | None = None
    us_source_url: str | None = None
    us_source_title: str | None = None
    us_note: str | None = None
    status: str = "active"
    note: str = ""


@dataclass(frozen=True)
class Company:
    code: str
    stock_id: str
    yahoo_symbol: str
    name_cn: str
    name_en: str
    program: Program
    us_yahoo_symbol: str | None = None
    enabled: bool = True


COMPANIES: list[Company] = [
    Company(
        code="00700",
        stock_id="7609",
        yahoo_symbol="0700.HK",
        name_cn="腾讯控股",
        name_en="TENCENT",
        program=Program(
            name="2026 AGM repurchase mandate",
            start_date="2026-05-13",
            end_date=None,
            limit_amount=None,
            limit_currency=None,
            limit_shares=Decimal("912386327"),
            share_base=Decimal("9123863270"),
            basis="shares",
            source_url="https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0409/2026040901309.pdf",
            source_title="2026 AGM circular - Share Repurchase Mandate",
            source_date="2026-04-09",
            period_label="2026 AGM approval date to next AGM / revocation / variation",
            limit_label="Up to 912,386,327 shares, representing 10% of issued shares at mandate date",
            status="active",
            us_note="未找到公司披露的美股/ADR专项回购数据；港股回购单独统计。",
            note="按年度股东大会回购授权监控；官方上限为可回购股数，不强行换算金额预算。",
        ),
    ),
    Company(
        code="01810",
        stock_id="190371",
        yahoo_symbol="1810.HK",
        name_cn="小米集团",
        name_en="XIAOMI-W",
        program=Program(
            name="HK$20bn share repurchase programme",
            start_date="2026-06-02",
            end_date=None,
            limit_amount=Decimal("20000000000"),
            limit_currency="HKD",
            limit_shares=None,
            share_base=None,
            basis="amount",
            source_url="https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0526/2026052600980.pdf",
            source_title="Voluntary Announcement - HK$20 Billion On-market Share Repurchase Program",
            source_date="2026-05-26",
            period_label="Effective from 2026-06-02, over the next 12 months and until the 2027 AGM",
            limit_label="Up to HK$20 billion of Class B ordinary shares",
            status="active",
            us_note="未找到公司披露的美股/ADR专项回购数据；港股回购单独统计。",
            note="专项金额计划；结束日按 2027 AGM 前后披露复核。",
        ),
    ),
    Company(
        code="02015",
        stock_id="1000108505",
        yahoo_symbol="2015.HK",
        name_cn="理想汽车",
        name_en="LI AUTO-W",
        us_yahoo_symbol="LI",
        program=Program(
            name="US$1bn share repurchase programme",
            start_date="2026-03-24",
            end_date="2027-03-31",
            limit_amount=Decimal("1000000000"),
            limit_currency="USD",
            limit_shares=None,
            share_base=Decimal("2142804240"),
            basis="amount",
            source_url="https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0324/2026032401608.pdf",
            source_title="Voluntary Announcement in relation to Share Repurchase Program",
            source_date="2026-03-24",
            period_label="From approval date 2026-03-24 up to 2027-03-31",
            limit_label="Up to USD1.0 billion of Class A ordinary shares and/or ADSs",
            us_amount=Decimal("139700000"),
            us_currency="USD",
            us_shares=Decimal("16400000"),
            us_ads=Decimal("6700000"),
            us_ordinary_shares_per_ads=Decimal("2"),
            us_as_of="2026-05-26",
            us_source_url="https://ir.lixiang.com/news-releases/news-release-details/li-auto-inc-announces-unaudited-first-quarter-2026-financial",
            us_source_title="Li Auto Q1 2026 Results - US$1.0 Billion Share Repurchase Program",
            us_note="官方累计快照：约 1,640 万股 Class A 普通股，包含约 670 万 ADS；这是计划级累计披露，不是每日交易明细，不能与 HKEX 日回购直接相加。",
            status="active",
            note="专项金额计划覆盖 Class A 普通股及/或 ADS；港股和美股/ADS 回购必须分开统计，未接入 ADS 数据前不计算合并进度。",
        ),
    ),
    Company(
        code="03690",
        stock_id="198419",
        yahoo_symbol="3690.HK",
        name_cn="美团",
        name_en="MEITUAN-W",
        program=Program(
            name="No clearly identified current special programme",
            start_date="2026-01-01",
            end_date=None,
            limit_amount=None,
            limit_currency=None,
            limit_shares=None,
            share_base=Decimal("6174619000"),
            basis="none",
            source_url="https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0604/2026060401708.pdf",
            source_title="2026 AGM circular - Repurchase Mandate",
            source_date="2026-06-04",
            period_label="If approved at 2026 AGM, until next AGM / revocation / variation",
            limit_label="AGM mandate up to 617,461,900 Class B shares; no current special cash programme identified",
            status="watch_only",
            us_note="美团当前未启用监控。",
            note="保留监控，但暂无明确当前专项回购计划；不显示计划进度百分比。",
        ),
        enabled=False,
    ),
]


ACTIVE_COMPANIES: list[Company] = [company for company in COMPANIES if company.enabled]
