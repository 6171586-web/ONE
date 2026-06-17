# 回购计划监控

本项目生成一个本地静态网页和每日公众号日报，用于监控港股公司的当前回购计划。

## 监控对象

- 腾讯 `00700.HK`
- 小米 `01810.HK`
- 理想汽车 `02015.HK`
- 美团 `03690.HK` 暂未启用：当前未找到明确专项回购计划，后续出现计划后再加入。

## 快速开始

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m buyback_monitor run --mode evening
python -m http.server 8080 -d site
```

生成结果：

- 网页：`site/index.html`
- 数据：`site/data/dashboard.json`
- 日报：`reports/latest/report.html`
- 运行日志：`data/monitor.sqlite`

本地查看：

```bash
python -m http.server 8080 -d site
```

然后打开 `http://localhost:8080`。

## 运行模式

- 默认增量：`python -m buyback_monitor run --mode evening --update-mode incremental`
- 全量审计：`python -m buyback_monitor run --mode manual --update-mode audit`

日常自动化使用增量模式，只处理新增或失败公告；全量审计用于定期校验是否漏抓公告。

## 定时策略

- 晚间版：交易日 `21:30` 生成并尝试发布。
- 复核版：交易日次日 `08:30` 复核晚发公告并修正网页数据。

## 云端部署

仓库内置 GitHub Actions 工作流：`.github/workflows/deploy-pages.yml`。

运行方式：

- 手动运行：GitHub 仓库页面进入 `Actions`，选择 `Build and deploy buyback monitor`，点击 `Run workflow`。
- 自动运行：北京时间交易日 `21:30` 和次日 `08:30` 自动生成网页并部署到 GitHub Pages。

GitHub Pages 设置：

1. 进入仓库 `Settings`。
2. 打开 `Pages`。
3. `Build and deployment` 的 `Source` 选择 `GitHub Actions`。

运行缓存：

- `data/` 和 `reports/` 不提交到仓库。
- GitHub Actions 会用 cache 保存运行数据库、已下载公告和报告，降低重复抓取成本。
- 部署网页来自每次运行生成的 `site/` 目录。

## 微信公众号配置

如需尝试自动发布，设置以下环境变量：

```bash
export WECHAT_APP_ID="..."
export WECHAT_APP_SECRET="..."
export WECHAT_AUTHOR="..."
export WECHAT_THUMB_MEDIA_ID="..."
export WECHAT_ENABLE_PUBLISH="1"
```

如果未配置，系统仍会生成日报 HTML，并把公众号状态记录为 `skipped`。

## 数据口径

回购公告以 HKEXnews 的 Next Day Disclosure Return 和公司公告为主。港股和美股/ADS 回购金额分开统计，不跨市场合并；未接入 ADS 官方披露前，不计算合并金额进度。成交额第一版使用可访问行情源估算，并在数据中标明 `estimated`；后续可替换为正式授权行情源。
