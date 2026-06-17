from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from html import unescape
from urllib.request import Request, urlopen

from .config import Company


SEC_HEADERS = {"User-Agent": "DivisMonitor/0.1 dad@example.com"}
LI_AUTO_CIK = "1791706"


@dataclass
class UsBuyback:
    company_code: str
    trade_date: str
    filing_date: str
    accession_number: str
    exhibit_name: str
    exchange: str
    shares: Decimal
    amount: Decimal
    currency: str
    high_price: Decimal
    low_price: Decimal
    source_url: str


def parse_decimal(value: str) -> Decimal:
    cleaned = value.replace(",", "").strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return Decimal("0")


def parse_textual_date(value: str) -> str | None:
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            from datetime import datetime

            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def sec_url(path: str) -> str:
    return f"https://www.sec.gov{path}"


def fetch_li_auto_us_buybacks(company: Company) -> list[UsBuyback]:
    if company.code != "02015":
        return []
    submissions_url = f"https://data.sec.gov/submissions/CIK{int(LI_AUTO_CIK):010d}.json"
    data = json.loads(urlopen(Request(submissions_url, headers=SEC_HEADERS), timeout=30).read().decode("utf-8"))
    recent = data["filings"]["recent"]
    out: list[UsBuyback] = []
    for form, filing_date, accession, primary_doc in zip(
        recent["form"],
        recent["filingDate"],
        recent["accessionNumber"],
        recent["primaryDocument"],
        strict=False,
    ):
        if form != "6-K" or filing_date < company.program.start_date:
            continue
        out.extend(fetch_accession_us_buybacks(company, filing_date, accession))
    return out


def fetch_accession_us_buybacks(company: Company, filing_date: str, accession: str) -> list[UsBuyback]:
    accession_flat = accession.replace("-", "")
    base_path = f"/Archives/edgar/data/{LI_AUTO_CIK}/{accession_flat}"
    txt_url = sec_url(f"{base_path}/{accession}.txt")
    try:
        html = urlopen(Request(txt_url, headers=SEC_HEADERS), timeout=15).read().decode("utf-8", errors="replace")
    except Exception:
        return []
    text = unescape(re.sub(r"<[^>]+>", " ", html))
    text = " ".join(text.split())
    return dedupe(parse_us_buyback_text(company, filing_date, accession, f"{accession}.txt", txt_url, text))


def parse_us_buyback_text(company: Company, filing_date: str, accession: str, exhibit_name: str, source_url: str, text: str) -> list[UsBuyback]:
    pattern = re.compile(
        r"([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})\s+"
        r"([0-9][0-9,]*)\s+On another stock exchange\s+"
        r"(Nasdaq Global Select Market)\s+"
        r"(USD)\s+([0-9]+(?:\.[0-9]+)?)\s+"
        r"USD\s+([0-9]+(?:\.[0-9]+)?)\s+"
        r"USD\s+([0-9][0-9,]*(?:\.[0-9]+)?)",
        re.I,
    )
    out = []
    for match in pattern.finditer(text):
        trade_date = parse_textual_date(match.group(1))
        if not trade_date:
            continue
        out.append(
            UsBuyback(
                company_code=company.code,
                trade_date=trade_date,
                filing_date=filing_date,
                accession_number=accession,
                exhibit_name=exhibit_name,
                exchange=match.group(3),
                shares=parse_decimal(match.group(2)),
                currency=match.group(4).upper(),
                high_price=parse_decimal(match.group(5)),
                low_price=parse_decimal(match.group(6)),
                amount=parse_decimal(match.group(7)),
                source_url=source_url,
            )
        )
    return out


def dedupe(rows: list[UsBuyback]) -> list[UsBuyback]:
    seen = set()
    out = []
    for row in rows:
        key = (row.trade_date, row.exchange, row.shares, row.amount)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out
