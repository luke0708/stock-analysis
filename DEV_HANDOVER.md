# 开发者交接文档 (DEV_HANDOVER)

本文档面向开发者/AI 助手，关注“怎么改”和“当前状态”。

## 1. 架构与数据流

### 分层结构
- **Data**：`stock_analysis/data/` 数据源与清洗。
- **Analysis**：`stock_analysis/analysis/` 指标、资金流、异常检测与 AI 客户端。
- **UI**：`stock_analysis/ui/` Streamlit 页面入口与交互。
- **Visualization**：`stock_analysis/visualization/` Plotly 图表生成。

### 核心数据流
1. UI 触发获取数据（AkShare/Tushare/YFinance）。
2. `DataCleaner` 统一清洗与标准化。
3. Tick 场景：`TickDataCleaner`/`TickFlowAnalyzer`/`TickAggregator` 产出 tick_summary 与窗口序列。
4. `FlowAnalyzer` 计算资金流向 + `flow_quality`。
5. `AnomalyDetector` 识别异常窗口与波动。
6. `PriceRangeAnalyzer` 计算价格区间工具箱（Pivot/ATR/Donchian）。
7. `ChartGenerator` 渲染图表，Streamlit 输出。

## 2. 运行入口与约定

- GUI 启动：`启动分析系统.command`
- CLI 启动：`streamlit run stock_analysis/ui/unified_app.py`
- 备用入口：`python run.py`

环境变量（`.env`）：
- `TUSHARE_TOKEN`：可选高质量数据源
- `DEEPSEEK_API_KEY`：AI 智能投顾

## 3. 关键文件索引

| 模块 | 文件路径 | 说明 |
| :--- | :--- | :--- |
| 入口 | `stock_analysis/ui/unified_app.py` | 导航与页面路由 |
| 个股分析 | `stock_analysis/ui/analysis_page.py` | 核心页面与图表组合 |
| 多股对比 | `stock_analysis/ui/comparison_page.py` | FlowAnalyzer + 对比图表 |
| 实时预警 | `stock_analysis/ui/alert_page.py` | 自动刷新与交易时段控制 |
| 全球市场 | `stock_analysis/ui/global_markets_page.py` | YFinance + A 股指数 |
| AI 智能投顾 | `stock_analysis/ui/future_features.py` | DeepSeek 调用、新闻补充、追问 |
| 资金流 | `stock_analysis/analysis/flows.py` | 资金流算法与粒度识别 |
| 异动检测 | `stock_analysis/analysis/anomaly.py` | 动态阈值大单与波动 |
| 价格区间 | `stock_analysis/analysis/price_range.py` | Pivot/ATR/Donchian 工具箱 |
| 图表 | `stock_analysis/visualization/charts.py` | Plotly 图表生成 |
| 数据清洗 | `stock_analysis/data/cleaner.py` | 缺失值与异常修复 |
| 预加载 | `stock_analysis/core/prefetch.py` | 市场页后台预取 |

## 4. 当前状态

### 已稳定功能
- 个股资金流向分析（回退最近交易日 + 实际日期显示）。
- 多股对比：使用 FlowAnalyzer + 对比图表。
- 市场全景：板块热点、龙虎榜、要闻、板块分析。
- 全球市场：A 股指数 + 美股/港股（YFinance）。
- 实时预警：多股监控、连续触发、交易时段自动暂停。
- AI 智能投顾：结构化提示词 + 预设档位 + 追问模式 + 可选新闻补充。
- Tick 链路：tick_summary/tick_window_series、异常高亮、原始最大成交榜。
- CSV 导入：自动识别代码与日期，支持分钟/Tick 数据导入。

### 已知技术债 / 风险点
1. **方向可靠性**：tick 中性盘占比高或方向推断比例高时，资金方向置信度下降。
2. **数据源稳定性**：AkShare 偶发超时，需更稳健的重试策略。
3. **新闻覆盖**：个股新闻来自 AkShare，存在延迟或缺失。
4. **性能**：市场热点/资讯加载速度仍受网络影响。

## 5. 下一步建议

- 引入 Tick 数据源时，优先规范列名映射到 `FlowAnalyzer`。
- 在 AI 侧继续强化“数据质量/来源”提示，减少误判。
- 市场页进一步拆分耗时操作到按需加载或异步队列。
- 明确 `direction_coverage/neutral_ratio` 的降级阈值与提示规则（覆盖率=买卖盘成交额/总成交额，中性盘占比=中性盘成交额/总成交额）。

## 6. AI 输出口径与覆盖率（开发者版）

### 6.1 资金方向口径
- 净流入仅使用买盘/卖盘，中性盘方向为 0。
- `neutral_ratio` 与 `direction_coverage` 用于解释买卖盘合计与总成交额的差异。
- `direction_reliability` 受 `quality_flags` 与 `inferred_ratio` 影响，低可靠时需降级结论。
- 降级阈值指：当方向覆盖率过低或中性盘占比过高时，AI 输出需弱化方向结论并提示口径限制。

### 6.2 盘中 vs 日线
- `today_partial` 为盘中快照，禁止与日线量能直接对比。
- 盘中仍可引用成交额/成交笔数/VWAP，但需注明快照性质。

### 6.3 异动口径
- `anomaly_highlights` 为加权筛选关键异动（体现盘中节奏）。
- `largest_trades_raw` 为全天原始最大成交榜单（含中性盘，不代表方向强弱）。
- AI 解读需区分两类数据来源。

### 6.4 均线关系
- 均线关系必须引用 `daily_trend.is_above_maX` 与 `close_vs_maX_pct`，避免模型自行比较数值。
