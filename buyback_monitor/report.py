from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from html import escape
from pathlib import Path

from .config import REPORTS_DIR, SITE_DIR


def decimal_to_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(Decimal(value))
    except Exception:
        return None


def write_dashboard(payload: dict) -> Path:
    data_dir = SITE_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "dashboard.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_site() -> Path:
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    path = SITE_DIR / "index.html"
    path.write_text(SITE_HTML, encoding="utf-8")
    return path


def format_money(value: str | None, currency: str = "HKD") -> str:
    if value is None:
        return "-"
    amount = Decimal(value)
    if abs(amount) >= Decimal("100000000"):
        return f"{currency} {amount / Decimal('100000000'):.2f} 亿"
    if abs(amount) >= Decimal("10000"):
        return f"{currency} {amount / Decimal('10000'):.2f} 万"
    return f"{currency} {amount:.2f}"


def format_price(value: str | None, currency: str = "HKD/股") -> str:
    if value is None:
        return "-"
    return f"{currency} {Decimal(value):.4f}"


def format_pct(value: str | None) -> str:
    if value is None:
        return "-"
    return f"{Decimal(value) * Decimal('100'):.2f}%"


def write_daily_report(payload: dict, mode: str) -> Path:
    run_date = date.today().isoformat()
    out_dir = REPORTS_DIR / run_date
    latest_dir = REPORTS_DIR / "latest"
    out_dir.mkdir(parents=True, exist_ok=True)
    latest_dir.mkdir(parents=True, exist_ok=True)
    html = build_report_html(payload, mode)
    path = out_dir / "report.html"
    latest = latest_dir / "report.html"
    path.write_text(html, encoding="utf-8")
    latest.write_text(html, encoding="utf-8")
    return path


def build_report_html(payload: dict, mode: str) -> str:
    generated_at = escape(payload["generated_at"])
    rows = []
    for company in payload["companies"]:
        summary = company["summary"]
        anomaly = escape(summary.get("anomaly_note") or "")
        rows.append(
            "<tr>"
            f"<td>{escape(company['name_cn'])}<br><small>{escape(company['code'])}</small></td>"
            f"<td>{escape(company['program']['name'])}<br><small>{escape(company['program']['period_label'])}</small><br><a href=\"{escape(company['program']['source_url'])}\">原始公告</a></td>"
            f"<td>{format_money(summary.get('cumulative_amount_hkd'))}<br><small>仅港股 / HKEX，不含 ADS</small></td>"
            f"<td>{escape(str(summary.get('cumulative_shares') or '-'))}</td>"
            f"<td>{format_price(summary.get('daily_average_price_hkd'))}</td>"
            f"<td>{format_price(summary.get('average_price_hkd'))}</td>"
            f"<td>{format_pct(summary.get('progress_ratio'))}</td>"
            f"<td>{anomaly or '无'}</td>"
            "</tr>"
        )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>港股回购计划监控日报</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #162033; line-height: 1.65; }}
    h1 {{ font-size: 24px; margin: 0 0 8px; }}
    h2 {{ font-size: 18px; margin-top: 24px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
    th, td {{ border: 1px solid #d8dee9; padding: 8px; vertical-align: top; }}
    th {{ background: #f3f6fb; text-align: left; }}
    small, .muted {{ color: #687386; }}
  </style>
</head>
<body>
  <h1>港股回购计划监控日报</h1>
  <p class="muted">生成时间：{generated_at}；模式：{escape(mode)}。本文基于截至运行时可获取的 HKEXnews / 公司公告和行情数据生成；晚发公告会在次日复核后修正网页数据。</p>
  <h2>总览</h2>
  <table>
    <thead><tr><th>公司</th><th>计划</th><th>港股累计金额</th><th>港股累计股数</th><th>最新每股回购均价</th><th>累计平均价</th><th>进度</th><th>备注</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <h2>数据说明</h2>
  <p>回购数据优先来自 HKEXnews 的 Next Day Disclosure Return。港股与美股/ADS 回购金额分开统计，未接入 ADS 数据前不合并计算。成交额第一版为可访问行情源估算值，正式使用前建议替换为授权成交额数据源。</p>
</body>
</html>"""


SITE_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Divis AI 回购监控</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
  <style>
    :root {
      --bg: #f4f6f8;
      --panel: #ffffff;
      --ink: #111827;
      --muted: #667085;
      --line: #d7dde5;
      --blue: #1d4ed8;
      --blue-soft: #eaf1ff;
      --amber: #d97706;
      --green: #047857;
      --red: #b91c1c;
      --shadow: 0 1px 2px rgba(16, 24, 40, .05);
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--ink); }
    header { padding: 24px 28px 14px; border-bottom: 1px solid var(--line); background: #fbfcfe; }
    .header-inner { max-width: 1344px; margin: 0 auto; }
    h1 { margin: 0 0 6px; font-size: 26px; letter-spacing: 0; color: #0f172a; }
    .muted { color: var(--muted); }
    main { padding: 20px 28px 36px; max-width: 1400px; margin: 0 auto; }
    .toolbar { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
    button { border: 1px solid var(--line); background: #fff; color: var(--ink); padding: 8px 12px; border-radius: 6px; cursor: pointer; box-shadow: var(--shadow); }
    button:hover { border-color: #b8c4d4; background: #f9fbff; }
    button.active { background: var(--blue); color: #fff; border-color: var(--blue); }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
    .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; box-shadow: var(--shadow); }
    .metric { font-size: 20px; line-height: 1.25; font-weight: 700; margin: 4px 0; overflow-wrap: anywhere; }
    .label { font-size: 12px; color: var(--muted); font-weight: 600; }
    .progress { height: 8px; background: #e8edf5; border-radius: 999px; overflow: hidden; margin-top: 8px; }
    .bar { height: 100%; background: var(--green); width: 0%; }
    .program { margin-bottom: 14px; display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .source-line { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 6px; }
    .pill { display: inline-block; border: 1px solid var(--line); border-radius: 999px; padding: 2px 8px; color: var(--muted); font-size: 12px; }
    .facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 10px; }
    .fact { border-top: 1px solid var(--line); padding-top: 8px; }
    .fact strong { display: block; font-size: 13px; margin-bottom: 2px; }
    .notes { margin-top: 14px; }
    .charts { display: grid; grid-template-columns: 1fr; gap: 14px; margin-top: 14px; }
    table { border-collapse: collapse; width: 100%; background: #fff; margin-top: 14px; border: 1px solid var(--line); box-shadow: var(--shadow); }
    th, td { border-bottom: 1px solid var(--line); padding: 9px; text-align: left; font-size: 13px; vertical-align: top; }
    th { color: #475467; background: #eef3f8; font-weight: 600; }
    tbody tr:nth-child(even) { background: #fafcff; }
    .warn { color: var(--red); }
    .hidden { display: none; }
    a { color: var(--blue); text-decoration: none; }
    @media (max-width: 900px) { .charts, .program { grid-template-columns: 1fr; } header, main { padding-left: 16px; padding-right: 16px; } }
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <h1>Divis AI 回购监控</h1>
      <div class="muted" id="generated">加载中</div>
    </div>
  </header>
  <main>
    <div class="toolbar" id="companyTabs"></div>
    <section class="program" id="programInfo"></section>
    <section class="grid" id="summary"></section>
    <section class="charts">
      <div class="panel">
        <canvas id="amountChart"></canvas>
        <div class="muted" style="margin-top:8px">柱状图为每日回购金额，美股金额按当日运行汇率折算为 HKD 便于同轴比较；折线为当日平均回购价，港股为 HKD/股，美股为 USD/ADS。</div>
      </div>
    </section>
    <section class="notes" id="marketNotes"></section>
    <table>
      <thead>
        <tr><th rowspan="2">日期</th><th colspan="4">美股 / Nasdaq</th><th colspan="4">港股 / HKEX</th></tr>
        <tr><th>金额</th><th>ADS数</th><th>每ADS均价</th><th>回购/成交额</th><th>金额</th><th>股数</th><th>每股均价</th><th>回购/成交额</th></tr>
      </thead>
      <tbody id="detailRows"></tbody>
    </table>
  </main>
  <script>
    let dashboard, current, amountChart;
    const money = (v, unit='HKD') => {
      if (v === null || v === undefined) return '-';
      const n = Number(v);
      if (Math.abs(n) >= 1e8) return `${unit} ${(n / 1e8).toFixed(2)} 亿`;
      if (Math.abs(n) >= 1e4) return `${unit} ${(n / 1e4).toFixed(2)} 万`;
      return `${unit} ${n.toFixed(2)}`;
    };
    const pct = v => v === null || v === undefined ? '-' : `${(Number(v) * 100).toFixed(2)}%`;
    const price = (v, unit='HKD/股') => v === null || v === undefined ? '-' : `${unit} ${Number(v).toFixed(4)}`;
    const plainNumber = v => v === null || v === undefined ? '-' : Number(v).toLocaleString('zh-HK', { maximumFractionDigits: 0 });
    const findBucket = (c, id) => (c.program.market_buckets || []).find(b => b.id === id) || {};
    const limitText = c => c.program.limit_label
      .replace('Up to USD1.0 billion of Class A ordinary shares and/or ADSs', '最高 10 亿美元，可回购 Class A 普通股及/或 ADS')
      .replace('Up to HK$20 billion of Class B ordinary shares', '最高 200 亿港元，可回购 Class B 普通股')
      .replace(/Up to ([\\d,]+) shares, representing 10% of issued shares at mandate date/, '最多 $1 股，相当于授权日已发行股本的 10%');
    const periodText = c => c.program.period_label
      .replace('From approval date 2026-03-24 up to 2027-03-31', '自 2026-03-24 批准日起至 2027-03-31')
      .replace('Effective from 2026-06-02, over the next 12 months and until the 2027 AGM', '自 2026-06-02 生效，未来 12 个月并持续至 2027 年股东周年大会')
      .replace('2026 AGM approval date to next AGM / revocation / variation', '自 2026 年股东周年大会批准日起，至下届股东周年大会或授权被撤销/修改');
    const usBucketText = b => {
      if (b.daily_total_amount) {
        const ratio = b.ordinary_shares_per_ads ? `；1 ADS = ${Number(b.ordinary_shares_per_ads).toFixed(0)} 股 Class A 普通股` : '';
        return `${money(b.daily_total_amount, b.currency || 'USD')}；${plainNumber(b.daily_total_ads)} ADS；普通股口径 ${plainNumber(b.daily_total_shares)} 股；最新 ${b.daily_latest_date}${ratio}；来源为 SEC 6-K / Li Auto IR 附件`;
      }
      return '';
    };
    const dedupTotalText = c => {
      const us = findBucket(c, 'us_ads');
      if (us.daily_total_amount) {
        return `
          <div class="fact"><strong>当前合计</strong><span>${money(c.combined_summary.total_amount_usd, 'USD')}，其中美股/Nasdaq ${money(us.daily_total_amount, us.currency || 'USD')}，港股折美元 ${money(c.combined_summary.hkd_amount_usd, 'USD')}</span></div>
          <div class="fact"><strong>汇率口径</strong><span>USD/HKD ${Number(c.combined_summary.hkd_per_usd).toFixed(4)}；${c.combined_summary.fx_source}</span></div>
        `;
      }
      const t = c.program.dedup_total;
      if (!t) return '';
      return `
        <div class="fact"><strong>去重合计</strong><span>${money(t.official_all_market_amount, t.official_all_market_currency || 'USD')}（官方全市场，截至 ${t.as_of}） + ${money(t.hk_increment_after_snapshot_hkd)}（${t.as_of} 后港股增量）</span></div>
        <div class="fact"><strong>合计说明</strong><span>${t.note}</span></div>
      `;
    };
    const marketTitle = c => {
      const us = findBucket(c, 'us_ads');
      return us.daily_total_amount ? '港股和美股/ADS分开' : '港股口径';
    };
    const reconciliationText = c => {
      const item = c.program.reconciliation?.us_daily_vs_official_snapshot;
      if (!item) return '';
      return `<div class="fact"><strong>阶段性总额校验</strong><span>截至 ${item.snapshot_date}：逐日累计 ${money(item.daily_sum_amount, 'USD')}（Nasdaq ${money(item.nasdaq_daily_sum_amount, 'USD')} + 港股折美元 ${money(item.hk_daily_sum_usd, 'USD')}）；官方披露 ${money(item.official_amount, 'USD')}；差异 ${money(item.diff_amount, 'USD')}（${pct(item.diff_ratio)}）</span></div>`;
    };
    const latestBuybackText = c => {
      const hkRows = c.metrics.filter(d => Number(d.buyback_amount || 0) > 0 || Number(d.buyback_shares || 0) > 0);
      const usRows = c.us_metrics || [];
      const dates = [...new Set([...hkRows.map(d => d.trade_date), ...usRows.map(d => d.trade_date)])]
        .sort((a, b) => String(b).localeCompare(String(a)));
      if (!dates.length) return '<div class="muted">计划期内暂未抓到回购明细。</div>';
      const date = dates[0];
      const hk = hkRows.find(d => d.trade_date === date);
      const us = usRows.find(d => d.trade_date === date);
      return `
        <div class="fact"><strong>日期</strong><span>${date}</span></div>
        ${hk ? `<div class="fact"><strong>港股</strong><span>${money(hk.buyback_amount, hk.buyback_currency || 'HKD')}；${plainNumber(hk.buyback_shares)} 股；均价 ${price(hk.daily_average_price_hkd)}；占成交额 ${pct(hk.buyback_turnover_ratio)}</span></div>` : ''}
        ${us ? `<div class="fact"><strong>美股</strong><span>${money(us.amount, us.currency || 'USD')}；${plainNumber(us.ads)} ADS；均价 ${price(us.average_price_ads, `${us.currency || 'USD'}/ADS`)}</span></div>` : ''}
      `;
    };
    const renderMarketNotes = c => {
      const s = c.summary;
      const us = findBucket(c, 'us_ads');
      document.getElementById('marketNotes').innerHTML = `
        <div class="panel">
          <div class="label">数据口径与校验</div>
          <div class="facts">
            <div class="fact"><strong>市场口径</strong><span>${marketTitle(c)}。港股 / HKEX：${money(s.cumulative_amount_hkd)}，按每日 HKEX 披露累计。</span></div>
            ${usBucketText(us) ? `<div class="fact"><strong>美股 / ADS</strong><span>${usBucketText(us)}</span></div>` : ''}
            ${dedupTotalText(c) || `<div class="fact"><strong>合计</strong><span>${money(s.cumulative_amount_hkd)}</span></div>`}
            ${reconciliationText(c)}
          </div>
          ${us.source_url ? `<div style="margin-top:8px"><a href="${us.source_url}" target="_blank">${us.source_title || '美股/ADS官方来源'}</a></div>` : ''}
        </div>
      `;
    };
    function renderTabs() {
      const box = document.getElementById('companyTabs');
      box.innerHTML = '';
      dashboard.companies.forEach((c, i) => {
        const b = document.createElement('button');
        b.textContent = `${c.name_cn} ${c.code}`;
        b.className = i === current ? 'active' : '';
        b.onclick = () => { current = i; render(); };
        box.appendChild(b);
      });
    }
    function renderSummary(c) {
      const s = c.summary;
      const us = findBucket(c, 'us_ads');
      const combined = c.combined_summary || {};
      const displayProgress = combined.progress_ratio || s.progress_ratio;
      const progress = displayProgress == null ? 0 : Math.min(100, Number(displayProgress) * 100);
      const hasUsDaily = Boolean(us.daily_total_amount);
      document.getElementById('programInfo').innerHTML = `
        <div class="panel">
          <div class="label">本次回购计划原始公告</div>
          <div class="metric">${c.name_cn}回购计划</div>
          <div class="facts">
            <div class="fact"><strong>总金额 / 上限</strong><span>${limitText(c) || '-'}</span></div>
            <div class="fact"><strong>有效期</strong><span>${periodText(c) || '-'}</span></div>
            <div class="fact"><strong>公告日期</strong><span>${c.program.source_date || '-'}</span></div>
            <div class="fact"><strong>引用原文</strong><span><a href="${c.program.source_url}" target="_blank">${c.program.source_title || '原始公告'}</a></span></div>
          </div>
        </div>
        <div class="panel">
          <div class="label">计划进展</div>
          <div class="metric">${pct(displayProgress)}</div>
          <div class="progress"><div class="bar" style="width:${progress}%"></div></div>
          <div class="facts">
            <div class="fact"><strong>回购股数占总股本</strong><span>${pct(hasUsDaily ? combined.combined_share_ratio : combined.hk_share_ratio)}</span></div>
            <div class="fact"><strong>股本口径</strong><span>${hasUsDaily ? `普通股口径合计 ${plainNumber(combined.combined_shares)} 股 / 基数 ${plainNumber(combined.share_base)} 股` : `${combined.share_base ? `港股累计 ${plainNumber(s.cumulative_shares)} 股 / 基数 ${plainNumber(combined.share_base)} 股` : '暂无明确股本基数'}`}</span></div>
          </div>
          <div class="label" style="margin-top:14px">最近一日回购</div>
          <div class="facts">${latestBuybackText(c)}</div>
        </div>
      `;
      document.getElementById('summary').innerHTML = hasUsDaily ? `
        <div class="panel"><div class="label">港股回购汇总</div><div class="metric">${money(s.cumulative_amount_hkd)}</div><div class="muted">折美元 ${money(combined.hkd_amount_usd, 'USD')}；汇率 ${Number(combined.hkd_per_usd).toFixed(4)}</div></div>
        <div class="panel"><div class="label">港股累计平均成交价</div><div class="metric">${price(s.average_price_hkd)}</div><div class="muted">港股累计金额 / 港股累计股数</div></div>
        <div class="panel"><div class="label">美股回购汇总</div><div class="metric">${money(us.daily_total_amount, us.currency || 'USD')}</div><div class="muted">${plainNumber(us.daily_total_ads)} ADS；最新 ${us.daily_latest_date}</div></div>
        <div class="panel"><div class="label">美股累计平均成交价</div><div class="metric">${price(us.average_price_ads, `${us.currency || 'USD'}/ADS`)}</div><div class="muted">美股累计金额 / ADS 数</div></div>
        <div class="panel"><div class="label">合计回购金额</div><div class="metric">${money(combined.total_amount_usd, 'USD')}</div><div class="muted">港股折美元 + 美股美元</div></div>
      ` : `
        <div class="panel"><div class="label">港股回购汇总</div><div class="metric">${money(s.cumulative_amount_hkd)}</div><div class="muted">仅 HKEX 港股披露</div></div>
        <div class="panel"><div class="label">港股累计平均成交价</div><div class="metric">${price(s.average_price_hkd)}</div><div class="muted">港股累计金额 / 港股累计股数</div></div>
        <div class="panel"><div class="label">合计回购金额</div><div class="metric">${money(s.cumulative_amount_hkd)}</div><div class="muted">港股口径</div></div>
      `;
      renderMarketNotes(c);
    }
    function renderCharts(c) {
      const hkRows = c.metrics.filter(d => Number(d.buyback_amount || 0) > 0);
      const usRows = c.us_metrics || [];
      const hkByDate = Object.fromEntries(hkRows.map(d => [d.trade_date, d]));
      const usByDate = Object.fromEntries(usRows.map(d => [d.trade_date, d]));
      const labels = [...new Set([...hkRows.map(d => d.trade_date), ...usRows.map(d => d.trade_date)])].sort();
      const hkDaily = labels.map(date => hkByDate[date] ? Number(hkByDate[date].buyback_amount || 0) : null);
      const hkdPerUsd = Number(c.combined_summary?.hkd_per_usd || dashboard.fx?.hkd_per_usd || 0);
      const usDailyHkd = labels.map(date => usByDate[date] ? Number(usByDate[date].amount || 0) * hkdPerUsd : null);
      const hkAvgPrice = labels.map(date => hkByDate[date] ? Number(hkByDate[date].daily_average_price_hkd || 0) : null);
      const usAvgPriceAds = labels.map(date => usByDate[date] ? Number(usByDate[date].average_price_ads || 0) : null);
      if (amountChart) amountChart.destroy();
      amountChart = new Chart(document.getElementById('amountChart'), {
        type: 'bar',
        data: { labels, datasets: [
          { label: '港股每日回购金额 HKD', data: hkDaily, borderColor: '#1d4ed8', backgroundColor: '#1d4ed8', yAxisID: 'yHkd' },
          { label: '美股每日回购金额 折HKD', data: usDailyHkd, borderColor: '#d97706', backgroundColor: '#d97706', yAxisID: 'yHkd' },
          { type: 'line', label: '港股当日平均回购价 HKD/股', data: hkAvgPrice, borderColor: '#1d4ed8', backgroundColor: '#1d4ed8', pointRadius: 3, tension: .25, spanGaps: false, yAxisID: 'yPrice' },
          { type: 'line', label: '美股当日平均回购价 USD/ADS', data: usAvgPriceAds, borderColor: '#d97706', backgroundColor: '#d97706', pointRadius: 3, tension: .25, spanGaps: false, yAxisID: 'yPrice' }
        ]},
        options: {
          responsive: true,
          plugins: { legend: { position: 'bottom' }, title: { display: true, text: '每日回购金额与当日平均回购价' } },
          scales: {
            yHkd: { type: 'linear', position: 'left', title: { display: true, text: '回购金额 HKD' } },
            yPrice: { type: 'linear', position: 'right', title: { display: true, text: '平均回购价' }, grid: { drawOnChartArea: false } }
          }
        }
      });
    }
    function renderRows(c) {
      const hkRows = c.metrics
        .filter(d => Number(d.buyback_amount || 0) > 0 || Number(d.buyback_shares || 0) > 0)
      const usRows = c.us_metrics || [];
      const hkByDate = Object.fromEntries(hkRows.map(d => [d.trade_date, d]));
      const usByDate = Object.fromEntries(usRows.map(d => [d.trade_date, d]));
      const dates = [...new Set([...hkRows.map(d => d.trade_date), ...usRows.map(d => d.trade_date)])]
        .sort((a, b) => String(b).localeCompare(String(a)));
      document.getElementById('detailRows').innerHTML = dates.length ? dates.map(date => {
        const us = usByDate[date];
        const hk = hkByDate[date];
        return `
        <tr>
          <td>${date}</td>
          <td>${us ? money(us.amount, us.currency || 'USD') : '-'}</td>
          <td>${us ? plainNumber(us.ads) : '-'}</td>
          <td>${us ? price(us.average_price_ads, `${us.currency || 'USD'}/ADS`) : '-'}</td>
          <td>${us ? pct(us.buyback_turnover_ratio) : '-'}</td>
          <td>${hk ? money(hk.buyback_amount, hk.buyback_currency || 'HKD') : '-'}</td>
          <td>${hk ? plainNumber(hk.buyback_shares) : '-'}</td>
          <td>${hk ? price(hk.daily_average_price_hkd) : '-'}</td>
          <td>${hk ? pct(hk.buyback_turnover_ratio) : '-'}</td>
        </tr>`;
      }).join('') : '<tr><td colspan="9" class="muted">当前计划期内暂未抓到回购明细。</td></tr>';
    }
    function render() {
      const c = dashboard.companies[current];
      renderTabs();
      renderSummary(c);
      renderCharts(c);
      renderRows(c);
    }
    const dataUrl = `data/dashboard.json?v=${Date.now()}`;
    fetch(dataUrl, { cache: 'no-store' }).then(r => r.json()).then(data => {
      dashboard = data;
      current = 0;
      document.getElementById('generated').textContent = `生成时间：${data.generated_at}`;
      render();
    }).catch(err => {
      document.getElementById('generated').textContent = `加载失败：${err}`;
    });
  </script>
</body>
</html>
"""
