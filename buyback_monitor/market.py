from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import Company


@dataclass
class MarketPoint:
    trade_date: str
    turnover: Decimal | None
    currency: str
    source: str
    status: str
    note: str


def fetch_yahoo_turnover_symbol(symbol: str, start_date: str, end_date: str | None = None, currency: str = "HKD") -> list[MarketPoint]:
    end = date.fromisoformat(end_date) if end_date else date.today()
    start = date.fromisoformat(start_date)
    period1 = int(datetime.combine(start, time.min, tzinfo=timezone.utc).timestamp())
    period2 = int(datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc).timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"period1": period1, "period2": period2, "interval": "1d"}
    try:
        request = Request(url + "?" + urlencode(params), headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=12) as response:
            result = response.read().decode("utf-8")
        import json

        result = json.loads(result)["chart"]["result"][0]
    except Exception as exc:
        return [MarketPoint(start.isoformat(), None, currency, "Yahoo chart", "failed", f"行情抓取失败：{exc}")]

    timestamps = result.get("timestamp") or []
    quotes = result.get("indicators", {}).get("quote", [{}])[0]
    closes = quotes.get("close") or []
    volumes = quotes.get("volume") or []
    points: list[MarketPoint] = []
    for ts, close, volume in zip(timestamps, closes, volumes, strict=False):
        if close is None or volume is None:
            continue
        trade_day = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        turnover = Decimal(str(close)) * Decimal(str(volume))
        points.append(
            MarketPoint(
                trade_date=trade_day,
                turnover=turnover,
                currency=currency,
                source="Yahoo chart close*volume",
                status="estimated",
                note="第一版用收盘价乘成交量估算成交额；后续应替换为授权成交额源。",
            )
        )
    return points


def fetch_yahoo_turnover(company: Company, start_date: str, end_date: str | None = None) -> list[MarketPoint]:
    return fetch_yahoo_turnover_symbol(company.yahoo_symbol, start_date, end_date, "HKD")
