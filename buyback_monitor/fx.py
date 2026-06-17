from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class FxRate:
    hkd_per_usd: Decimal
    source: str
    note: str


def fetch_hkd_per_usd() -> FxRate:
    url = "https://query1.finance.yahoo.com/v8/finance/chart/HKD=X?range=5d&interval=1d"
    try:
        with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
        closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        values = [Decimal(str(value)) for value in closes if value is not None]
        if values:
            return FxRate(values[-1], "Yahoo Finance HKD=X", "用于把港股 HKD 回购金额折算为 USD 计算计划进度。")
    except Exception as exc:
        return FxRate(Decimal("7.8"), "fallback 7.8", f"汇率抓取失败，暂用 7.8：{exc}")
    return FxRate(Decimal("7.8"), "fallback 7.8", "汇率源无可用收盘价，暂用 7.8。")

