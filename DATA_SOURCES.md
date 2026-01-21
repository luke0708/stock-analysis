# 数据源调用清单

本文件用于定位项目内所有“下载/拉取数据”的调用点，便于替换 AkShare 等数据源。

## 优先替换顺序（建议）

1. **主链路 Tick/分钟数据**  
   优先替换 `AkShareProvider.get_tick_data()`，因为这是绝大部分页面与分析的入口。  
   影响文件：`stock_analysis/data/providers/akshare_provider.py`、`stock_analysis/ui/analysis_page.py`

2. **日线历史数据**  
   影响趋势/区间/AI 解读。优先替换 `get_history_data()`。  
   影响文件：`stock_analysis/data/providers/akshare_provider.py`、`stock_analysis/ui/future_features.py`

3. **实时监控与预取情绪**  
   `alert_page` 与 `market_hotspot` 的失败会影响体验，但不阻塞主分析。  
   影响文件：`stock_analysis/ui/alert_page.py`、`stock_analysis/analysis/market_hotspot.py`

4. **股票列表/搜索**  
   影响用户体验但不影响核心分析。  
   影响文件：`stock_analysis/data/stock_list.py`

5. **新闻与全球市场**  
   可放到最后替换。  
   影响文件：`stock_analysis/data/news_provider.py`、`stock_analysis/ui/global_markets_page.py`

## 可替代源建议（按功能）

> 以下是常见替代思路，具体可用性需测试与合规评估。

- **A 股分钟/日线**
  - Tushare（已内置，免费账户分钟数据受限）
  - BaoStock / JoinQuant（需新增 provider）
  - 东方财富/同花顺公开接口（稳定性需评估）

- **A 股行情快照/情绪**
  - 东方财富行情接口（替代 `stock_zh_a_spot_em`）
  - 雪球行情（需鉴权/限频评估）

- **新闻**
  - 东方财富财经新闻 / 证券时报 RSS（需解析）

## 建议补充的检查点

- **时间戳一致性**：不同源的时间格式/时区差异会影响分时聚合与热力图。
- **成交额单位**：有的源为“元/千元/万元”，需在清洗阶段统一。
- **涨跌幅口径**：部分源返回“涨跌幅%”已是百分数，需避免二次乘 100。
- **交易日回退**：源不完整时，确保 `requested_date/actual_date` 标注一致。

## 接口字段映射建议（统一口径）

> 目标：所有数据源统一为当前代码期望的标准列名，避免改动分析与图表逻辑。

### Tick/分钟级数据（逐笔或 1 分钟）

标准列名（必须）：
- `时间`（datetime）
- `成交价格` 或 `收盘`（float）
- `成交量`（int/float）
- `成交额` 或 `成交额(元)`（float）

可选列名：
- `性质`（买盘/卖盘/中性盘）

常见字段映射：
- 时间：`成交时间` / `时间` / `trade_time` / `datetime`
- 价格：`成交价格` / `价格` / `最新价` / `close`
- 量：`成交量` / `vol` / `volume`
- 额：`成交额` / `成交金额` / `amount`
- 性质：`性质` / `type`

### 日线历史数据

标准列名（必须）：
- `日期`
- `开盘` / `最高` / `最低` / `收盘`
- `成交量`（股）
- `成交额`（元）

常见字段映射：
- 日期：`日期` / `date` / `trade_date`
- 开盘：`open`
- 最高：`high`
- 最低：`low`
- 收盘：`close`
- 成交量：`vol` / `volume`
- 成交额：`amount`

### 行情快照/情绪（市场全表）

标准列名（至少）：
- `涨跌幅`（百分数）
- `名称`

常见字段映射：
- `涨跌幅` / `pct_chg` / `change_pct`
- `名称` / `name`

### 新闻

标准列名：
- `发布时间`
- `新闻标题`
- `新闻内容`
## Tick/分钟数据（核心链路）

- `stock_analysis/ui/analysis_page.py`
  - `fetch_data()` → `AkShareProvider.get_tick_data()` / `TushareProvider.get_tick_data()`
- `stock_analysis/ui/comparison_page.py`
  - `provider.get_tick_data(code, date_str)`
- `stock_analysis/data/providers/akshare_provider.py`
  - `get_tick_data()` → `ak.stock_zh_a_tick_tx_js` + 历史回退
- `stock_analysis/data/providers/tushare_provider.py`
  - `get_tick_data()` → `ts.pro_bar(..., freq="1min")`

## 日线历史数据

- `stock_analysis/ui/future_features.py`
  - `_load_daily_history()` → `AkShareProvider.get_history_data()`
- `stock_analysis/data/providers/akshare_provider.py`
  - `get_history_data()` → `ak.stock_zh_a_hist`
- `stock_analysis/data/providers/tushare_provider.py`
  - `get_history_data()` → `self.pro.daily`
- `stock_analysis/data/providers/yfinance_provider.py`
  - `get_history_data()` → `yfinance`

## 实时行情/监控

- `stock_analysis/ui/alert_page.py`
  - `provider.get_realtime_data(code)`
- `stock_analysis/data/providers/akshare_provider.py`
  - `get_realtime_data()` → `get_tick_data(today)`
- `stock_analysis/data/providers/tushare_provider.py`
  - `get_realtime_data()` → `get_tick_data(today)`

## 市场情绪/热点

- `stock_analysis/analysis/market_hotspot.py`
  - `analyze_market_sentiment()` → `ak.stock_zh_a_spot_em()`
- `stock_analysis/core/prefetch.py`
  - 预取：`MarketHotspotAnalyzer.get_hot_industries()` / `analyze_market_sentiment()`

## 股票列表/搜索

- `stock_analysis/data/stock_list.py`
  - `get_stock_provider()` 内部使用 AkShare 搜索接口
- `stock_analysis/ui/analysis_page.py`
  - `stock_provider.search()`（由 `stock_list.py` 决定来源）

## 新闻数据

- `stock_analysis/data/news_provider.py`
  - `get_market_news()` / `get_stock_news()`
- `stock_analysis/ui/market_page.py`
  - `StockNewsProvider.get_market_news()`
- `stock_analysis/ui/future_features.py`
  - `StockNewsProvider.get_stock_news()`

## 全球市场（非 A 股）

- `stock_analysis/ui/global_markets_page.py`
  - `yfinance` 拉取指数/ETF
