from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import DB_PATH


SCHEMA = """
create table if not exists buyback_programs (
  company_code text primary key,
  company_name text not null,
  program_name text not null,
  start_date text not null,
  end_date text,
  limit_amount text,
  limit_currency text,
  limit_shares text,
  basis text not null,
  source_url text not null,
  source_title text,
  source_date text,
  period_label text,
  limit_label text,
  status text not null,
  note text not null
);

create table if not exists buyback_filings (
  id text primary key,
  company_code text not null,
  trade_date text,
  release_time text not null,
  title text not null,
  pdf_url text not null,
  pdf_sha256 text,
  shares text,
  amount text,
  currency text,
  high_price text,
  low_price text,
  parser_status text not null,
  parser_note text,
  raw_text_path text,
  created_at text not null
);

create table if not exists market_data (
  id text primary key,
  company_code text not null,
  trade_date text not null,
  turnover text,
  currency text,
  primary_source text not null,
  check_source text,
  diff_ratio text,
  status text not null,
  note text,
  created_at text not null
);

create table if not exists us_buyback_filings (
  id text primary key,
  company_code text not null,
  trade_date text not null,
  filing_date text not null,
  accession_number text not null,
  exhibit_name text not null,
  exchange text not null,
  shares text,
  amount text,
  currency text,
  high_price text,
  low_price text,
  source_url text not null,
  parser_status text not null,
  created_at text not null
);

create table if not exists daily_metrics (
  id text primary key,
  company_code text not null,
  trade_date text not null,
  buyback_amount text,
  buyback_shares text,
  buyback_currency text,
  daily_average_price_hkd text,
  cumulative_amount_hkd text,
  cumulative_shares text,
  average_price_hkd text,
  progress_ratio text,
  turnover_hkd text,
  buyback_turnover_ratio text,
  anomaly_note text,
  updated_at text not null
);

create table if not exists publish_runs (
  id text primary key,
  run_at text not null,
  mode text not null,
  target_date text not null,
  status text not null,
  article_path text,
  error_info text
);

create table if not exists run_state (
  key text primary key,
  value text not null,
  updated_at text not null
);
"""


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("pragma table_info(buyback_programs)").fetchall()}
    for name in ("source_title", "source_date", "period_label", "limit_label"):
        if name not in columns:
            conn.execute(f"alter table buyback_programs add column {name} text")
    metric_columns = {row["name"] for row in conn.execute("pragma table_info(daily_metrics)").fetchall()}
    for name in ("buyback_shares", "daily_average_price_hkd"):
        if name not in metric_columns:
            conn.execute(f"alter table daily_metrics add column {name} text")
    conn.commit()
