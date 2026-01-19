# Tick 数据处理与分析算法设计（初稿）

> 目标：仅在“当日实时数据”场景使用 tick 作为资金流向与 AI 分析输入；历史仍使用分钟数据，确保稳定性与兼容性。

## 1. 目标与范围

- 产品核心：个股资金流向分析，tick 级数据提供真实“性质”，更贴近资金流动。
- 适用范围：当日实时 tick；历史场景继续使用分钟数据。
- 设计原则：双通道  
  - 价格/指标：分钟 OHLC（稳定、复用现有指标与图表）  
  - 资金流/买卖盘：tick（真实性更强）

## 2. 总体架构与数据流

- 触发条件：`分析日期 == 当日` 且 `tick 可用` 时启用 tick 流程。
- 数据流（实时）：  
  1) Provider 返回 raw tick  
  2) TickDataCleaner 清洗与标准化  
  3) TickFlowAnalyzer / TickAnomaly 产出资金流与异动  
  4) TickAggregator 生成窗口级数据  
  5) 图表与 AI 使用 tick 摘要  
- 数据流（历史）：使用现有分钟链路，不改变。

## 3. 数据口径与字段规范

### 3.1 原始字段（标准化后）

- `时间`（datetime）
- `成交价格`（float）
- `成交量`（float/int）
- `成交额`（float）
- `性质`（买盘/卖盘/中性盘）
- 可选：`价格变动`

### 3.2 衍生字段

- `成交额(元)`：若缺失，则 `成交额(元) = 成交量 * 成交价格`
- `方向`：买盘=+1，卖盘=-1，中性=0
- `净流入额`：`成交额(元) * 方向`
- `trade_count`：按窗口统计成交笔数
- `VWAP`：`sum(成交额) / max(sum(成交量), 1)`

### 3.3 口径与单位约束

- 成交量单位（手/股）必须统一，并在 `quality_flags` 标注。
- `性质` 来源需标注（原始字段/推断），避免误导 AI。
- `buy_ratio/sell_ratio` 分母是否包含中性盘需统一定义（默认不包含中性盘）。

## 4. Tick 数据清洗（TickDataCleaner）

1. 时间字段  
   - 若仅有 HH:MM:SS，补齐日期（使用当日日期）  
   - 转为 `datetime`，丢弃无法解析的行
2. 数值字段  
   - `成交价格/成交量/成交额` 转为数值  
   - 缺失 `成交额` 时按价格*量补算
3. 去重与排序  
   - 避免简单 “时间+价格+量” 去重误删  
   - 优先使用逐笔序号/成交序列（若有）
4. 交易时段过滤  
   - A 股交易时段：`09:30-11:30`，`13:00-15:00`  
   - 集合竞价（09:25）默认不纳入窗口图表
5. 异常值处理  
   - 价格<=0 或 成交量<0 直接剔除  
   - 极端跳变仅标记，不直接删除

## 5. Tick 分析与聚合

### 5.1 TickFlowAnalyzer（资金流）

- `buy_amount` / `sell_amount`：按性质累加  
- `net_inflow = buy_amount - sell_amount`  
- `buy_ratio/sell_ratio`：按统一口径计算  
- `OFI = (buy_amount - sell_amount) / max(buy_amount + sell_amount, 1)`  
- `large_order_threshold = max(200000, 90%分位成交额)`  
  - 输出：大单数量、总额、净流入

### 5.2 TickAnomaly（异动）

- 大单冲击：成交额超过阈值  
- 突发成交密度：短时间成交笔数显著高于均值  
- 净流入突变：`net_inflow` 窗口间跳变过大

### 5.3 TickAggregator（面向展示）

按窗口聚合（1/5/10 分钟）生成图表输入：
- `time_window`
- `buy_amount` / `sell_amount` / `net_inflow`
- `buy_count` / `sell_count` / `neutral_count` / `trade_count`
- `OFI` / `VWAP`
- `price_open/high/low/close`、`range_pct`

## 6. 图表算法设计（tick 口径）

### 6.0 公共聚合规则（tick -> 窗口）

- 窗口默认：  
  - 高频趋势：1 分钟  
  - 强度/对比：5 分钟  
  - 热力/概览：10 分钟  
- 关键字段：  
  - `turnover = buy_amount + sell_amount`  
  - `OFI = (buy_amount - sell_amount) / max(turnover, 1)`  
  - `range_pct = (price_high - price_low) / max(VWAP, 1) * 100`
- 对极端值：按 95 分位 clip，避免图表压扁。

### 图 1：Tick 累计净流入曲线（资金流主线）

- 输入：tick 明细或 1 分钟 `net_inflow`
- 算法：按时间排序 `cumsum(net_inflow)`  
- 细节：可对曲线做 5 分钟 EMA 平滑  
- 输出：`时间`、`累计净流入`

### 图 2：买卖盘强度对比（窗口堆叠）

- 输入：5 分钟 `buy_amount` / `sell_amount`
- 算法：  
  - `buy_strength = buy_amount / max(turnover, 1)`  
  - `sell_strength = sell_amount / max(turnover, 1)`
- 展示：堆叠柱（买上卖下）+ 可选净流入折线

### 图 3：订单流失衡（OFI）走势

- 输入：1 或 5 分钟 `OFI`
- 算法：`OFI` 计算后进行 clip  
- 展示：折线 + 0 轴，正负区域颜色区分

### 图 4：大单追踪散点（与价格叠加）

- 输入：tick 明细（时间、价格、成交额、性质）
- 算法：  
  - `large_order_threshold = max(200000, 90%分位成交额)`  
  - top N（如 20）按成交额排序  
  - `marker_size = sqrt(成交额 / median_成交额)`
- 展示：分钟价格线 + 大单散点（买红、卖绿）

### 图 5：日内资金流热力（强弱分布）

- 输入：10 分钟 `net_inflow` / `turnover`
- 算法：`flow_ratio = net_inflow / max(turnover, 1)`，按 95 分位 clip  
- 展示：热力条或色彩柱状图

### 图 6：成交密度与短时波动（节奏感）

- 输入：1 或 5 分钟 `trade_count` / `range_pct`
- 算法：  
  - 成交密度：`trade_count`  
  - 波动率：`range_pct`  
  - 可选：`density_z = (trade_count - mean) / std`
- 展示：双轴折线或柱+线组合

> 价格相关图（K 线、VWAP、指标）继续使用分钟 OHLC，不改。
> tick 缺失或异常时，资金流图表回退到分钟逻辑并提示原因。

## 7. AI 输入数据设计（当日实时才用 tick）

### 7.1 设计原则

- 不传全量 tick，避免 token 过大  
- 使用“窗口级摘要 + 大单样本 + 关键指标”  
- 历史仍用分钟 summary，保持模型输入稳定  
- 显式标注数据口径与质量

### 7.2 数据结构（建议）

```json
{
  "data_scope": {
    "date": "YYYYMMDD",
    "source": "tick|minute",
    "tick_available": true,
    "window_minutes": 5,
    "market_hours_only": true,
    "quality_flags": ["missing_fields", "fallback_to_minute"]
  },
  "minute_summary": {
    "open": 0,
    "close": 0,
    "high": 0,
    "low": 0,
    "turnover": 0,
    "vwap": 0,
    "price_change_pct": 0
  },
  "tick_summary": {
    "trade_count": 0,
    "buy_count": 0,
    "sell_count": 0,
    "neutral_count": 0,
    "buy_amount": 0,
    "sell_amount": 0,
    "net_inflow": 0,
    "buy_ratio": 0,
    "sell_ratio": 0,
    "ofi_latest": 0,
    "ofi_trend_last_5": [0, 0, 0, 0, 0],
    "large_orders_top5": [
      {"time": "HH:MM:SS", "amount": 0, "price": 0, "side": "买盘|卖盘"}
    ],
    "burst_windows": [
      {"time_window": "HH:MM", "trade_count": 0, "net_inflow": 0}
    ]
  },
  "tick_window_series": [
    {
      "time_window": "HH:MM",
      "buy_amount": 0,
      "sell_amount": 0,
      "net_inflow": 0,
      "turnover": 0,
      "ofi": 0,
      "trade_count": 0,
      "range_pct": 0
    }
  ],
  "anomaly_notes": [
    "净流入突变发生于 10:15",
    "大单集中出现在 14:05-14:20"
  ]
}
```

### 7.3 字段口径说明

- `buy_ratio = buy_amount / max(buy_amount + sell_amount, 1)`  
- `ofi_latest` 来自最新窗口 `OFI`  
- `ofi_trend_last_5` 为最近 5 个窗口 `OFI` 序列  
- `burst_windows` 使用 `trade_count` 或 `turnover` 的 95 分位阈值筛选  
- `quality_flags` 说明缺失字段、回退原因、异常时段

### 7.4 采样与压缩策略

- `tick_window_series` 仅保留最近 N 个窗口（建议 20-40）  
- `large_orders_top5` 按成交额排序取样  
- 仅在当日实时且 tick 可用时附带 `tick_summary`

## 8. 集成与回退策略

- `AkShareProvider` 保留 raw tick，写入 `raw_tick` 与 `quality_flags`。
- 当日实时：资金流图表与 AI 使用 tick；价格/指标仍用分钟。
- 历史：保持原分钟逻辑，不引入 tick 依赖。
- 回退：tick 缺失/字段不全/非交易时段 -> 自动回退分钟并提示。
- 性能：必须聚合后再渲染，避免全量 tick 直接绘图。

## 9. 工程与性能注意（参考实现借鉴与修正）

### 9.1 可借鉴点

- 清洗/分析/聚合/可视化职责清晰，适合渐进落地  
- OFI、大单阈值、成交密度指标方向正确  
- 多窗口聚合覆盖图表需求  
- 热力图 + 大单追踪适合资金流主题

### 9.2 必须修正点

- 去重逻辑不能过粗，避免误删真实成交  
- 避免大量 `apply` 行级计算，优先向量化  
- 午间休市空桶要统一过滤  
- 口径（买卖比例、是否包含中性盘）必须统一  
- 单位一致性（手/股、元/千元）必须在清洗阶段统一  
- 价格底图与资金流统计严格分口径

## 10. 验证与测试建议

- 单元测试：时间补全与排序、成交额补算、OFI 计算、大单识别  
- 口径检查：tick 与分钟净流入方向一致性  
- 性能：10k+ tick 聚合与渲染耗时可接受

## 11. 成功标准

- 当日实时：资金流判断更灵敏，AI 解读更贴近盘感  
- 历史：无功能回退或图表错乱  
- 性能：渲染与分析响应时间可接受

## 12. 下一步落地指导（给模型写代码）

1. **定义入口与条件**  
   - 判断 `tick_available`（当日 + raw tick 存在）  
   - 不满足则直接走分钟逻辑
2. **新增模块（建议路径）**  
   - `stock_analysis/analysis/tick_cleaner.py`  
   - `stock_analysis/analysis/tick_flow.py`  
   - `stock_analysis/analysis/tick_aggregator.py`  
   - `stock_analysis/analysis/tick_anomaly.py`
3. **数据流改造顺序**  
   - Provider 保留 raw tick  
   - TickDataCleaner 输出标准 tick  
   - TickFlowAnalyzer 产出 summary 与大单列表  
   - TickAggregator 产出窗口级数据  
4. **图表与 AI 接入**  
   - 资金流图表改为使用 tick 聚合结果  
   - AI 预览追加 `tick_summary` 与 `tick_window_series`
5. **回退与提示**  
   - 缺字段或非交易时段触发回退，并写入 `quality_flags`
6. **测试清单**  
   - 参照第 10 节执行  
   - 增加手动案例（正常盘中、午间空窗、非交易日）

## 13. 实施记录（追加）

> 仅追加当前实现与进展，不改动上文设计指导。

### 13.1 六点决策摘要（精简版）

1. 集合竞价：单独保存；主图表默认不纳入，提供“显示集合竞价”开关；AI 摘要独立字段报告。  
2. 成交量单位：清洗阶段统一为“股”，AI `metadata` 明确 `volume_unit=shares`。  
3. 性质缺失：优先用原始性质；缺失时按价格变动阈值推断，并在摘要里标注推断比例。  
4. 窗口与平滑：OFI 1 分钟计算、5 分钟展示；累计净流入可做 EMA 平滑，其它序列保持原波动。  
5. 大单阈值与展示：`max(200000, 90分位)` + 早盘上调；展示 Top 15（时间权重）。  
6. AI 序列长度：默认保留 40 窗口，附 core20 与扩展 60 窗口入口。

### 13.2 Tick 新链路工作流程（当前实现）

1. Provider 返回 raw tick。  
2. `TickDataCleaner`：时间补全、交易时段过滤、成交量换算为股、性质规范化与推断、集合竞价分离。  
3. `TickFlowAnalyzer`：净流入/OFI/大单阈值与标记。  
4. `TickAggregator`：1/5/10 分钟窗口聚合与关键指标。  
5. `TickAnomaly`：成交密度与资金突变标记。  
6. UI 图表与 AI 摘要优先使用 tick；不满足条件回退分钟。

### 13.3 相关代码文件清单（Tick 独立链路）

- `stock_analysis/analysis/tick_cleaner.py`  
- `stock_analysis/analysis/tick_flow.py`  
- `stock_analysis/analysis/tick_aggregator.py`  
- `stock_analysis/analysis/tick_anomaly.py`  
- `stock_analysis/ui/analysis_page.py`  
- `stock_analysis/visualization/charts.py`  
- `stock_analysis/core/cache_manager.py`  
- `run.py`

### 13.4 当前进展与待办

- 已完成：tick 清洗/分析/聚合/异动模块；UI 接入 tick 图表与 AI 摘要；集合竞价显示开关；缓存中清理 tick 上下文。  
- 待修复：tick 聚合输出全 0（OFI/净流入/买卖压力）导致图表与 AI 序列异常。  
