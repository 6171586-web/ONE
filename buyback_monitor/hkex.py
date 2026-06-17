from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin

from pypdf import PdfReader

from .config import RAW_DIR, Company


BASE = "https://www1.hkexnews.hk"
HEADERS = {
    "User-Agent": "Mozilla/5.0 buyback-monitor/0.1",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class Filing:
    company_code: str
    release_time: str
    title: str
    pdf_url: str
    size: str | None = None


@dataclass
class ParsedBuyback:
    trade_date: str | None
    shares: Decimal | None
    amount: Decimal | None
    currency: str | None
    high_price: Decimal | None
    low_price: Decimal | None
    status: str
    note: str
    raw_text: str
    pdf_sha256: str | None
    raw_text_path: str | None


@dataclass
class ParsedUsBuyback:
    trade_date: str
    exchange: str
    shares: Decimal
    amount: Decimal
    currency: str
    high_price: Decimal
    low_price: Decimal


def fetch_filings(company: Company, start_date: str) -> list[Filing]:
    url = (
        f"{BASE}/search/titlesearch.xhtml?category=0&lang=EN"
        f"&market=SEHK&stockId={company.stock_id}"
    )
    request = Request(url, headers=HEADERS)
    with urlopen(request, timeout=45) as response:
        page = response.read().decode("utf-8", errors="replace")
    rows = re.findall(r"<tr[\s\S]*?</tr>", page, flags=re.I)
    filings: list[Filing] = []
    for row in rows:
        text = html.unescape(re.sub(r"<[^>]+>", " ", row))
        text = " ".join(text.split())
        if "Next Day Disclosure Returns" not in text or "Share Buyback" not in text:
            continue
        release_match = re.search(r"Release Time:\s*(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})", text)
        if not release_match:
            continue
        release_dt = datetime.strptime(release_match.group(1), "%d/%m/%Y %H:%M")
        if release_dt.date() < date.fromisoformat(start_date):
            continue
        link_match = re.search(r'<a[^>]+href="([^"]+\.pdf)"', row, flags=re.I)
        if not link_match:
            continue
        title = "Next Day Disclosure Return"
        headline_match = re.search(r'<div class="headline">([\s\S]*?)</div>', row, flags=re.I)
        if headline_match:
            title_text = html.unescape(re.sub(r"<[^>]+>", " ", headline_match.group(1)))
            title = " ".join(title_text.split()) or title
        filings.append(
            Filing(
                company_code=company.code,
                release_time=release_dt.isoformat(timespec="minutes"),
                title=title,
                pdf_url=urljoin(BASE, link_match.group(1)),
            )
        )
    return filings


def download_pdf(url: str, company_code: str) -> tuple[Path, str]:
    pdf_dir = RAW_DIR / "pdf" / company_code
    pdf_dir.mkdir(parents=True, exist_ok=True)
    name = url.rstrip("/").split("/")[-1]
    path = pdf_dir / name
    if not path.exists():
        request = Request(url, headers=HEADERS)
        with urlopen(request, timeout=60) as response:
            path.write_bytes(response.read())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, digest


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    texts: list[str] = []
    for page in reader.pages:
        texts.append(page.extract_text() or "")
    return "\n".join(texts)


def parse_decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    cleaned = value.replace(",", "").replace("HK$", "").replace("US$", "").strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_buyback_pdf(pdf_url: str, company_code: str) -> ParsedBuyback:
    pdf_sha256 = None
    raw_text_path = None
    try:
        path, pdf_sha256 = download_pdf(pdf_url, company_code)
        raw_text = extract_pdf_text(path)
        text_dir = RAW_DIR / "text" / company_code
        text_dir.mkdir(parents=True, exist_ok=True)
        raw_text_path_obj = text_dir / f"{path.stem}.txt"
        raw_text_path_obj.write_text(raw_text, encoding="utf-8")
        raw_text_path = str(raw_text_path_obj)
    except Exception as exc:
        return ParsedBuyback(None, None, None, None, None, None, "failed", f"PDF 下载或解析失败：{exc}", "", pdf_sha256, raw_text_path)

    compact = " ".join(raw_text.split())
    submitted = parse_textual_date(re.search(r"Date Submitted:\s*([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})", compact, re.I))

    entries = []
    entry_pattern = re.compile(
        r"Date of changes\s+([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})\s+([0-9][0-9,]*)\s+[0-9.]+\s*%\s+HKD\s+([0-9]+(?:\.[0-9]+)?)",
        re.I,
    )
    for match in entry_pattern.finditer(compact):
        entry_date = parse_textual_date(match)
        entry_shares = parse_decimal(match.group(2))
        entry_price = parse_decimal(match.group(3))
        if entry_date and entry_shares is not None and entry_price is not None:
            entries.append((entry_date, entry_shares, entry_price))

    selected = None
    if entries:
        if submitted:
            selected = next((entry for entry in entries if entry[0] == submitted), None)
        selected = selected or sorted(entries, key=lambda item: item[0])[-1]

    trade_date = selected[0] if selected else None

    currency = "HKD" if re.search(r"\bHKD\b|HK\$", compact, re.I) else None
    if re.search(r"\bUSD\b|US\$", compact, re.I):
        currency = "USD"

    report_entry = parse_section_two_entry(compact, submitted)
    if report_entry:
        trade_date, shares, high_price, low_price, amount, currency = report_entry
    else:
        trade_date = selected[0] if selected else None
        shares = selected[1] if selected else None
        high_price = selected[2] if selected else None
        low_price = selected[2] if selected else None
        amount = selected[1] * selected[2] if selected else None
    amount_patterns = [
        r"(?:Total|Aggregate)[^0-9]{0,40}(?:HK\$|HKD|US\$|USD)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)",
        r"(?:consideration|amount paid)[^0-9]{0,40}(?:HK\$|HKD|US\$|USD)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)",
    ]
    if amount is None:
        for pattern in amount_patterns:
            match = re.search(pattern, compact, re.I)
            if match:
                amount = parse_decimal(match.group(1))
                break

    share_patterns = [
        r"(?:number of shares repurchased|shares repurchased|No\. of shares)[^0-9]{0,40}([0-9][0-9,]*)",
        r"([0-9][0-9,]*)\s+(?:shares|Shares)\s+(?:repurchased|bought back)",
    ]
    if shares is None:
        for pattern in share_patterns:
            match = re.search(pattern, compact, re.I)
            if match:
                shares = parse_decimal(match.group(1))
                break

    if high_price is None or low_price is None:
        price_values = [parse_decimal(v) for v in re.findall(r"(?:highest|lowest|price)[^0-9]{0,20}([0-9]+(?:\.[0-9]+)?)", compact, re.I)]
        price_values = [v for v in price_values if v is not None and v < Decimal("10000")]
        high_price = max(price_values) if price_values else None
        low_price = min(price_values) if price_values else None

    missing = []
    if not trade_date:
        missing.append("交易日")
    if shares is None:
        missing.append("股数")
    if amount is None:
        missing.append("金额")
    if missing:
        return ParsedBuyback(trade_date, shares, amount, currency, high_price, low_price, "partial", "未能稳定解析：" + "、".join(missing), raw_text, pdf_sha256, raw_text_path)
    return ParsedBuyback(trade_date, shares, amount, currency or "HKD", high_price, low_price, "ok", "", raw_text, pdf_sha256, raw_text_path)


def parse_textual_date(match: re.Match | None) -> str | None:
    if not match:
        return None
    value = match.group(1)
    try:
        return datetime.strptime(value, "%d %B %Y").date().isoformat()
    except ValueError:
        try:
            return datetime.strptime(value, "%d %b %Y").date().isoformat()
        except ValueError:
            return None


def parse_section_two_entry(compact: str, submitted: str | None) -> tuple[str, Decimal, Decimal, Decimal, Decimal, str] | None:
    pattern = re.compile(
        r"([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})\s+"
        r"([0-9][0-9,]*)\s+On the Exchange\s+"
        r"(HKD|USD)\s+([0-9]+(?:\.[0-9]+)?)\s+"
        r"(?:HKD|USD)\s+([0-9]+(?:\.[0-9]+)?)\s+"
        r"(?:HKD|USD)\s+([0-9][0-9,]*(?:\.[0-9]+)?)",
        re.I,
    )
    entries = []
    for match in pattern.finditer(compact):
        trade_date = parse_textual_date(match)
        shares = parse_decimal(match.group(2))
        high = parse_decimal(match.group(4))
        low = parse_decimal(match.group(5))
        amount = parse_decimal(match.group(6))
        currency = match.group(3).upper()
        if trade_date and shares is not None and high is not None and low is not None and amount is not None:
            entries.append((trade_date, shares, high, low, amount, currency))
    if not entries:
        return None
    if submitted:
        exact = next((entry for entry in entries if entry[0] == submitted), None)
        if exact:
            return exact
    return sorted(entries, key=lambda item: item[0])[-1]


def parse_us_buybacks_from_text(raw_text: str) -> list[ParsedUsBuyback]:
    compact = " ".join(raw_text.split())
    pattern = re.compile(
        r"([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})\s+"
        r"([0-9][0-9,]*)\s+On another stock exchange\s+"
        r"(Nasdaq Global Select Market)\s+"
        r"(USD)\s+([0-9]+(?:\.[0-9]+)?)\s+"
        r"USD\s+([0-9]+(?:\.[0-9]+)?)\s+"
        r"USD\s+([0-9][0-9,]*(?:\.[0-9]+)?)",
        re.I,
    )
    rows = []
    for match in pattern.finditer(compact):
        trade_date = parse_textual_date(match)
        shares = parse_decimal(match.group(2))
        high_price = parse_decimal(match.group(5))
        low_price = parse_decimal(match.group(6))
        amount = parse_decimal(match.group(7))
        if trade_date and shares is not None and high_price is not None and low_price is not None and amount is not None:
            rows.append(
                ParsedUsBuyback(
                    trade_date=trade_date,
                    exchange=match.group(3),
                    shares=shares,
                    amount=amount,
                    currency=match.group(4).upper(),
                    high_price=high_price,
                    low_price=low_price,
                )
            )
    return rows
