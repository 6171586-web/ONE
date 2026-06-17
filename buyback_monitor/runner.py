from __future__ import annotations

import argparse
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from .config import ACTIVE_COMPANIES, DATA_DIR
from .db import connect
from .fx import fetch_hkd_per_usd
from .hkex import fetch_filings, parse_buyback_pdf, parse_us_buybacks_from_text
from .market import fetch_yahoo_turnover, fetch_yahoo_turnover_symbol
from .report import write_daily_report, write_dashboard, write_site
from .wechat import publish_article


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def dec(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def upsert_programs(conn):
    for company in ACTIVE_COMPANIES:
        p = company.program
        conn.execute(
            """
            insert into buyback_programs (
              company_code, company_name, program_name, start_date, end_date,
              limit_amount, limit_currency, limit_shares, basis, source_url,
              source_title, source_date, period_label, limit_label, status, note
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(company_code) do update set
              company_name=excluded.company_name,
              program_name=excluded.program_name,
              start_date=excluded.start_date,
              end_date=excluded.end_date,
              limit_amount=excluded.limit_amount,
              limit_currency=excluded.limit_currency,
              limit_shares=excluded.limit_shares,
              basis=excluded.basis,
              source_url=excluded.source_url,
              source_title=excluded.source_title,
              source_date=excluded.source_date,
              period_label=excluded.period_label,
              limit_label=excluded.limit_label,
              status=excluded.status,
              note=excluded.note
            """,
            (
                company.code,
                company.name_cn,
                p.name,
                p.start_date,
                p.end_date,
                dec(p.limit_amount),
                p.limit_currency,
                dec(p.limit_shares),
                p.basis,
                p.source_url,
                p.source_title,
                p.source_date,
                p.period_label,
                p.limit_label,
                p.status,
                p.note,
            ),
        )
    conn.commit()


def existing_filing_status(conn, filing_id: str):
    return conn.execute(
        "select parser_status, pdf_sha256 from buyback_filings where id = ?",
        (filing_id,),
    ).fetchone()


def collect_filings(conn, update_mode: str) -> None:
    for company in ACTIVE_COMPANIES:
        try:
            filings = fetch_filings(company, company.program.start_date)
        except Exception as exc:
            print(f"{company.code} HKEXnews 抓取失败：{exc}")
            continue
        for filing in filings:
            filing_id = f"{company.code}:{filing.pdf_url.rsplit('/', 1)[-1]}"
            current = existing_filing_status(conn, filing_id)
            if update_mode == "incremental" and current and current["parser_status"] == "ok" and current["pdf_sha256"]:
                continue
            parsed = parse_buyback_pdf(filing.pdf_url, company.code)
            conn.execute(
                """
                insert into buyback_filings values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                  trade_date=excluded.trade_date,
                  release_time=excluded.release_time,
                  title=excluded.title,
                  pdf_url=excluded.pdf_url,
                  pdf_sha256=excluded.pdf_sha256,
                  shares=excluded.shares,
                  amount=excluded.amount,
                  currency=excluded.currency,
                  high_price=excluded.high_price,
                  low_price=excluded.low_price,
                  parser_status=excluded.parser_status,
                  parser_note=excluded.parser_note,
                  raw_text_path=excluded.raw_text_path
                """,
                (
                    filing_id,
                    company.code,
                    parsed.trade_date,
                    filing.release_time,
                    filing.title,
                    filing.pdf_url,
                    parsed.pdf_sha256,
                    dec(parsed.shares),
                    dec(parsed.amount),
                    parsed.currency,
                    dec(parsed.high_price),
                    dec(parsed.low_price),
                    parsed.status,
                    parsed.note,
                    parsed.raw_text_path,
                    now_iso(),
                ),
            )
        conn.commit()


def market_start_date(conn, company) -> str:
    row = conn.execute(
        "select max(trade_date) as last_trade_date from market_data where company_code = ?",
        (company.code,),
    ).fetchone()
    if row and row["last_trade_date"]:
        last = date.fromisoformat(row["last_trade_date"])
        return max(date.fromisoformat(company.program.start_date), last - timedelta(days=7)).isoformat()
    return company.program.start_date


def collect_market(conn, update_mode: str) -> None:
    for company in ACTIVE_COMPANIES:
        start_date = company.program.start_date if update_mode == "audit" else market_start_date(conn, company)
        points = fetch_yahoo_turnover(company, start_date)
        for point in points:
            point_id = f"{company.code}:{point.trade_date}:{point.source}"
            conn.execute(
                """
                insert into market_data values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                  turnover=excluded.turnover,
                  currency=excluded.currency,
                  status=excluded.status,
                  note=excluded.note,
                  created_at=excluded.created_at
                """,
                (
                    point_id,
                    company.code,
                    point.trade_date,
                    dec(point.turnover),
                    point.currency,
                    point.source,
                    None,
                    None,
                    point.status,
                    point.note,
                    now_iso(),
                ),
            )
        conn.commit()


def collect_us_buybacks(conn, update_mode: str) -> None:
    for company in ACTIVE_COMPANIES:
        if company.code != "02015":
            continue
        if update_mode == "audit":
            conn.execute("delete from us_buyback_filings where company_code = ?", (company.code,))
        filing_rows = conn.execute(
            "select release_time, pdf_url, raw_text_path from buyback_filings where company_code = ? and raw_text_path is not null",
            (company.code,),
        ).fetchall()
        for filing in filing_rows:
            if update_mode == "incremental":
                existing = conn.execute(
                    "select 1 from us_buyback_filings where company_code = ? and source_url = ? limit 1",
                    (company.code, filing["pdf_url"]),
                ).fetchone()
                if existing:
                    continue
            try:
                raw_text = Path(filing["raw_text_path"]).read_text(encoding="utf-8")
            except Exception:
                continue
            for row in parse_us_buybacks_from_text(raw_text):
                row_id = f"{company.code}:us:{row.trade_date}:{filing['pdf_url'].rsplit('/', 1)[-1]}:{row.amount}"
                filing_date = filing["release_time"][:10]
                conn.execute(
                    """
                    insert into us_buyback_filings values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    on conflict(id) do update set
                      trade_date=excluded.trade_date,
                      filing_date=excluded.filing_date,
                      exchange=excluded.exchange,
                      shares=excluded.shares,
                      amount=excluded.amount,
                      currency=excluded.currency,
                      high_price=excluded.high_price,
                      low_price=excluded.low_price,
                      source_url=excluded.source_url,
                      parser_status=excluded.parser_status,
                      created_at=excluded.created_at
                    """,
                    (
                        row_id,
                        company.code,
                        row.trade_date,
                        filing_date,
                        filing["pdf_url"].rsplit("/", 1)[-1],
                        "HKEX/SEC 6-K PDF",
                        row.exchange,
                        dec(row.shares),
                        dec(row.amount),
                        row.currency,
                        dec(row.high_price),
                        dec(row.low_price),
                        filing["pdf_url"],
                        "ok",
                        now_iso(),
                    ),
                )
        conn.commit()


def decimal_or_zero(value) -> Decimal:
    return Decimal(str(value)) if value not in (None, "") else Decimal("0")


def rebuild_metrics(conn) -> None:
    conn.execute("delete from daily_metrics")
    for company in ACTIVE_COMPANIES:
        filings = conn.execute(
            """
            select * from buyback_filings
            where company_code = ?
            order by coalesce(trade_date, substr(release_time, 1, 10)), release_time
            """,
            (company.code,),
        ).fetchall()
        market_rows = conn.execute(
            "select * from market_data where company_code = ? order by trade_date",
            (company.code,),
        ).fetchall()
        market_by_date = {row["trade_date"]: row for row in market_rows}
        dates = sorted({row["trade_date"] for row in market_rows if row["trade_date"]} | {row["trade_date"] for row in filings if row["trade_date"]})
        cumulative_amount = Decimal("0")
        cumulative_shares = Decimal("0")
        filings_by_date = {}
        for row in filings:
            if row["trade_date"]:
                filings_by_date.setdefault(row["trade_date"], []).append(row)
        for trade_day in dates:
            day_amount = Decimal("0")
            day_shares = Decimal("0")
            currency = "HKD"
            source_url = None
            notes = []
            for filing in filings_by_date.get(trade_day, []):
                day_amount += decimal_or_zero(filing["amount"])
                day_shares += decimal_or_zero(filing["shares"])
                currency = filing["currency"] or currency
                source_url = filing["pdf_url"]
                if filing["parser_status"] != "ok":
                    notes.append(filing["parser_note"] or "回购 PDF 部分字段待复核")
            cumulative_amount += day_amount
            cumulative_shares += day_shares
            daily_avg_price = day_amount / day_shares if day_shares else None
            avg_price = cumulative_amount / cumulative_shares if cumulative_shares else None
            progress = None
            if company.program.basis == "amount" and company.program.limit_amount:
                if company.program.limit_currency in (None, "HKD"):
                    progress = cumulative_amount / company.program.limit_amount
                else:
                    notes.append(f"计划上限币种为 {company.program.limit_currency}，当前累计金额为 HKD，进度待接入汇率后换算。")
            elif company.program.basis == "shares" and company.program.limit_shares:
                progress = cumulative_shares / company.program.limit_shares
            elif company.program.basis == "none":
                notes.append(company.program.note)
            market = market_by_date.get(trade_day)
            turnover = decimal_or_zero(market["turnover"]) if market else Decimal("0")
            if market and market["status"] != "ok":
                notes.append(market["note"] or "成交额待复核")
            ratio = day_amount / turnover if turnover else None
            conn.execute(
                """
                insert into daily_metrics (
                  id, company_code, trade_date, buyback_amount, buyback_shares,
                  buyback_currency, daily_average_price_hkd, cumulative_amount_hkd,
                  cumulative_shares, average_price_hkd, progress_ratio, turnover_hkd,
                  buyback_turnover_ratio, anomaly_note, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{company.code}:{trade_day}",
                    company.code,
                    trade_day,
                    dec(day_amount),
                    dec(day_shares),
                    currency,
                    dec(daily_avg_price),
                    dec(cumulative_amount),
                    dec(cumulative_shares),
                    dec(avg_price),
                    dec(progress),
                    dec(turnover) if turnover else None,
                    dec(ratio),
                    "；".join(dict.fromkeys([n for n in notes if n])),
                    now_iso(),
                ),
            )
    conn.commit()


def build_payload(conn) -> dict:
    fx = fetch_hkd_per_usd()
    payload = {
        "generated_at": now_iso(),
        "fx": {
            "hkd_per_usd": dec(fx.hkd_per_usd),
            "source": fx.source,
            "note": fx.note,
        },
        "companies": [],
    }
    for company in ACTIVE_COMPANIES:
        rows = conn.execute(
            "select * from daily_metrics where company_code = ? order by trade_date",
            (company.code,),
        ).fetchall()
        filing_sources = {
            row["trade_date"]: row["pdf_url"]
            for row in conn.execute("select trade_date, pdf_url from buyback_filings where company_code = ?", (company.code,)).fetchall()
            if row["trade_date"]
        }
        metrics = []
        for row in rows:
            metrics.append(
                {
                    "trade_date": row["trade_date"],
                    "buyback_amount": row["buyback_amount"],
                    "buyback_shares": row["buyback_shares"],
                    "buyback_currency": row["buyback_currency"],
                    "daily_average_price_hkd": row["daily_average_price_hkd"],
                    "cumulative_amount_hkd": row["cumulative_amount_hkd"],
                    "cumulative_shares": row["cumulative_shares"],
                    "average_price_hkd": row["average_price_hkd"],
                    "progress_ratio": row["progress_ratio"],
                    "turnover_hkd": row["turnover_hkd"],
                    "buyback_turnover_ratio": row["buyback_turnover_ratio"],
                    "anomaly_note": row["anomaly_note"],
                    "source_url": filing_sources.get(row["trade_date"]),
                }
            )
        summary = metrics[-1] if metrics else {
            "cumulative_amount_hkd": None,
            "cumulative_shares": None,
            "daily_average_price_hkd": None,
            "average_price_hkd": None,
            "progress_ratio": None,
            "anomaly_note": company.program.note,
        }
        us_rows = conn.execute(
            "select * from us_buyback_filings where company_code = ? order by trade_date",
            (company.code,),
        ).fetchall()
        us_market_by_date = {}
        if company.us_yahoo_symbol and us_rows:
            us_market_by_date = {
                point.trade_date: point
                for point in fetch_yahoo_turnover_symbol(company.us_yahoo_symbol, company.program.start_date, currency="USD")
                if point.turnover
            }
        us_ads_ratio = company.program.us_ordinary_shares_per_ads or Decimal("1")
        us_metrics = []
        for row in us_rows:
            shares = decimal_or_zero(row["shares"])
            amount = decimal_or_zero(row["amount"])
            ads = shares / us_ads_ratio if shares and us_ads_ratio else Decimal("0")
            avg_ordinary = amount / shares if amount and shares else None
            avg_ads = amount / ads if amount and ads else None
            high_price = decimal_or_zero(row["high_price"])
            low_price = decimal_or_zero(row["low_price"])
            us_market = us_market_by_date.get(row["trade_date"])
            us_turnover = us_market.turnover if us_market else None
            us_turnover_ratio = amount / us_turnover if amount and us_turnover else None
            us_metrics.append(
                {
                    "trade_date": row["trade_date"],
                    "filing_date": row["filing_date"],
                    "exchange": row["exchange"],
                    "ordinary_shares": row["shares"],
                    "shares": row["shares"],
                    "ads": dec(ads) if ads else None,
                    "ordinary_shares_per_ads": dec(us_ads_ratio),
                    "amount": row["amount"],
                    "currency": row["currency"],
                    "high_price": row["high_price"],
                    "low_price": row["low_price"],
                    "high_price_ads": dec(high_price * us_ads_ratio) if high_price else None,
                    "low_price_ads": dec(low_price * us_ads_ratio) if low_price else None,
                    "average_price": dec(avg_ordinary),
                    "average_price_ads": dec(avg_ads),
                    "turnover": dec(us_turnover),
                    "turnover_currency": us_market.currency if us_market else None,
                    "buyback_turnover_ratio": dec(us_turnover_ratio),
                    "turnover_source": us_market.source if us_market else None,
                    "turnover_note": us_market.note if us_market else None,
                    "source_url": row["source_url"],
                }
            )
        us_total_amount = sum((decimal_or_zero(row["amount"]) for row in us_rows), Decimal("0"))
        us_total_shares = sum((decimal_or_zero(row["shares"]) for row in us_rows), Decimal("0"))
        us_total_ads = us_total_shares / us_ads_ratio if us_total_shares and us_ads_ratio else Decimal("0")
        us_average_price = us_total_amount / us_total_shares if us_total_shares else None
        us_average_price_ads = us_total_amount / us_total_ads if us_total_ads else None
        us_latest_date = us_metrics[-1]["trade_date"] if us_metrics else None
        us_reconcile = None
        if company.program.us_amount and company.program.us_as_of and us_rows:
            daily_through_snapshot = sum(
                (decimal_or_zero(row["amount"]) for row in us_rows if row["trade_date"] <= company.program.us_as_of),
                Decimal("0"),
            )
            hkd_through_snapshot = sum(
                (decimal_or_zero(row["buyback_amount"]) for row in rows if row["trade_date"] <= company.program.us_as_of),
                Decimal("0"),
            )
            hkd_through_snapshot_usd = hkd_through_snapshot / fx.hkd_per_usd if fx.hkd_per_usd else Decimal("0")
            all_market_daily_sum = daily_through_snapshot + hkd_through_snapshot_usd
            diff = all_market_daily_sum - company.program.us_amount
            us_reconcile = {
                "snapshot_date": company.program.us_as_of,
                "official_amount": dec(company.program.us_amount),
                "nasdaq_daily_sum_amount": dec(daily_through_snapshot),
                "hk_daily_sum_usd": dec(hkd_through_snapshot_usd),
                "daily_sum_amount": dec(all_market_daily_sum),
                "diff_amount": dec(diff),
                "diff_ratio": dec(diff / company.program.us_amount) if company.program.us_amount else None,
                "source_title": company.program.us_source_title,
                "source_url": company.program.us_source_url,
            }
        hkd_cumulative = decimal_or_zero(summary.get("cumulative_amount_hkd"))
        hk_total_shares = decimal_or_zero(summary.get("cumulative_shares"))
        hkd_as_usd = hkd_cumulative / fx.hkd_per_usd if fx.hkd_per_usd else Decimal("0")
        total_usd = us_total_amount + hkd_as_usd
        combined_shares = us_total_shares + hk_total_shares
        hk_share_ratio = hk_total_shares / company.program.share_base if company.program.share_base else None
        us_share_ratio = us_total_shares / company.program.share_base if company.program.share_base and us_total_shares else None
        combined_share_ratio = combined_shares / company.program.share_base if company.program.share_base and combined_shares else None
        combined_progress = None
        if company.program.limit_currency == "USD" and company.program.limit_amount:
            combined_progress = total_usd / company.program.limit_amount
        hk_increment_after_us_snapshot = None
        if company.program.us_amount and company.program.us_as_of:
            increment = sum(
                decimal_or_zero(row["buyback_amount"])
                for row in rows
                if row["trade_date"] and row["trade_date"] > company.program.us_as_of
            )
            hk_increment_after_us_snapshot = dec(increment)

        payload["companies"].append(
            {
                "code": company.code,
                "name_cn": company.name_cn,
                "name_en": company.name_en,
                "program": {
                    "name": company.program.name,
                    "start_date": company.program.start_date,
                    "end_date": company.program.end_date,
                    "basis": company.program.basis,
                    "note": company.program.note,
                    "source_url": company.program.source_url,
                    "source_title": company.program.source_title,
                    "source_date": company.program.source_date,
                    "period_label": company.program.period_label,
                    "limit_label": company.program.limit_label,
                    "security_scope": security_scope(company.program.limit_label),
                    "market_buckets": [
                        {
                            "id": "hk",
                            "label": "港股 / HKEX",
                            "amount_field": "cumulative_amount_hkd",
                            "currency": "HKD",
                            "status": "active",
                        },
                        {
                            "id": "us_ads",
                            "label": "官方全市场快照（含 ADS）",
                            "amount": dec(company.program.us_amount),
                            "currency": company.program.us_currency,
                            "shares": dec(company.program.us_shares),
                            "ads": dec(company.program.us_ads),
                            "ordinary_shares_per_ads": dec(company.program.us_ordinary_shares_per_ads),
                            "daily_total_amount": dec(us_total_amount) if us_metrics else None,
                            "daily_total_shares": dec(us_total_shares) if us_metrics else None,
                            "daily_total_ads": dec(us_total_ads) if us_metrics else None,
                            "average_price": dec(us_average_price),
                            "average_price_ads": dec(us_average_price_ads),
                            "daily_latest_date": us_latest_date,
                            "as_of": company.program.us_as_of,
                            "source_url": company.program.us_source_url,
                            "source_title": company.program.us_source_title,
                            "status": "official_snapshot" if company.program.us_amount else "not_found",
                            "note": company.program.us_note or "未找到官方美股/ADS回购数据；不与港股金额合并。",
                        },
                    ],
                    "dedup_total": {
                        "as_of": company.program.us_as_of,
                        "official_all_market_amount": dec(company.program.us_amount),
                        "official_all_market_currency": company.program.us_currency,
                        "hk_increment_after_snapshot_hkd": hk_increment_after_us_snapshot,
                        "note": "为避免重复计算，合计采用官方全市场累计快照加快照日之后的 HKEX 港股增量；不把快照日前 HKEX 日回购再次相加。",
                    } if company.program.us_amount else None,
                    "reconciliation": {
                        "us_daily_vs_official_snapshot": us_reconcile,
                    },
                },
                "summary": summary,
                "combined_summary": {
                    "hkd_amount_usd": dec(hkd_as_usd),
                    "us_amount_usd": dec(us_total_amount) if us_metrics else None,
                    "total_amount_usd": dec(total_usd) if us_metrics or hkd_cumulative else None,
                    "progress_ratio": dec(combined_progress),
                    "hk_share_ratio": dec(hk_share_ratio),
                    "us_share_ratio": dec(us_share_ratio),
                    "combined_share_ratio": dec(combined_share_ratio),
                    "combined_shares": dec(combined_shares),
                    "share_base": dec(company.program.share_base),
                    "hkd_per_usd": dec(fx.hkd_per_usd),
                    "fx_source": fx.source,
                    "fx_note": fx.note,
                },
                "metrics": metrics,
                "us_metrics": us_metrics,
            }
        )
    return payload


def security_scope(limit_label: str) -> str:
    lowered = limit_label.lower()
    if "class a" in lowered and "ads" in lowered:
        return "Class A ordinary shares and/or ADSs"
    if "class b" in lowered:
        return "Class B ordinary shares"
    if "shares" in lowered:
        return "Ordinary shares"
    return "Shares"


def write_run_state(conn, key: str, value: str) -> None:
    conn.execute(
        """
        insert into run_state values (?, ?, ?)
        on conflict(key) do update set value=excluded.value, updated_at=excluded.updated_at
        """,
        (key, value, now_iso()),
    )
    conn.commit()


def run(mode: str, update_mode: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect()
    upsert_programs(conn)
    collect_filings(conn, update_mode)
    collect_us_buybacks(conn, update_mode)
    collect_market(conn, update_mode)
    rebuild_metrics(conn)
    payload = build_payload(conn)
    write_dashboard(payload)
    write_site()
    report_path = write_daily_report(payload, mode)
    result = publish_article(f"港股回购计划监控日报 {date.today().isoformat()}", report_path)
    conn.execute(
        "insert into publish_runs values (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), now_iso(), mode, date.today().isoformat(), result.status, str(report_path), result.error),
    )
    write_run_state(conn, "last_update_mode", update_mode)
    write_run_state(conn, "last_successful_run_at", now_iso())
    conn.commit()
    print(json.dumps({"site": "site/index.html", "report": str(report_path), "update_mode": update_mode, "publish_status": result.status, "publish_error": result.error}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--mode", choices=["evening", "morning", "manual"], default="manual")
    run_parser.add_argument("--update-mode", choices=["incremental", "audit"], default="incremental")
    args = parser.parse_args()
    if args.command == "run":
        run(args.mode, args.update_mode)


if __name__ == "__main__":
    main()
