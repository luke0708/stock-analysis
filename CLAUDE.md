# A股资金流向智能分析系统 — CLAUDE.md

## 项目定位

A 股资金流向 + AI 投顾工具，Streamlit Web UI，本地运行。
核心价值：tick 级别资金流向分析 + DeepSeek 驱动的个股 AI 建议。

## 启动方式

```bash
# 方式 1（推荐，macOS）
open 启动分析系统.command

# 方式 2
cd /Users/wangluke/Localprojects/读取股票当天数据
source .venv/bin/activate
streamlit run stock_analysis/ui/unified_app.py
```

默认访问 http://localhost:8501

## 架构概览（v4.0）

```
stock_analysis/
├── ui/
│   ├── unified_app.py        # 路由入口，导航 4 项
│   ├── analysis_page.py      # 旗舰：个股资金流向（1247 行）
│   ├── ai_advisor.py         # AI 投顾 + 复盘日志（1650+ 行）
│   └── beta_task_page.py     # 决策面板 Beta（冻结，1364 行）
├── analysis/
│   ├── ai_client.py          # DeepSeek HTTP 客户端
│   ├── advice_journal.py     # 复盘日志 DAO（SQLite）
│   ├── prompts/              # Prompt 版本化管理
│   │   ├── registry.py       # CURRENT_VERSION = "v1"
│   │   └── v1.py             # 静态规则：BASE_CONSTRAINTS / FOCUS_MAP 等
│   ├── flows.py              # 主力/散户资金流计算
│   ├── tick_cleaner.py       # tick 数据清洗
│   ├── tick_aggregator.py    # tick → 分钟聚合
│   ├── tick_flow.py          # tick 级资金流
│   ├── tick_anomaly.py       # tick 异动检测
│   ├── anomaly.py            # bar 级异动
│   ├── order_strength.py     # 买卖压力比
│   ├── indicators.py         # 技术指标
│   └── price_range.py        # 支撑/压力区间
├── data/
│   ├── providers/
│   │   ├── akshare_provider.py  # 主力数据源（唯一主源，不可删）
│   │   └── tushare_provider.py  # 备用（UI 可配置切换）
│   ├── cache_schema.py       # stock_cache.db DDL（L1/L2/L4 三层）
│   ├── cache_store.py        # 数据访问层，透明缓存 + L2 写入
│   ├── cleaner.py
│   ├── news_provider.py
│   └── stock_list.py
├── ml/                       # 训练数据骨架（占位，数据累积后实现）
│   ├── export_training_set.py
│   └── label_backfiller.py
├── core/
│   ├── config.py             # 全局设置（路径、Tushare token）
│   ├── cache_manager.py
│   └── storage.py
├── tasks/                    # Beta 任务队列（冻结）
├── bridge/                   # Beta 子进程桥接（冻结）
└── visualization/

data/
├── stock_cache.db            # 数据沉淀层（L1 原始 + L2 衍生 + L4 标签）
├── analysis_tasks.db         # Beta 任务队列 DB（冻结）
├── advice_journal.db         # AI 投顾复盘日志（L3，独立）
└── stock_industry_map.csv

vendor/daily_stock_analysis/  # Beta 依赖的原算法（冻结）
股票分析算法/                  # Beta 算法规则参考（冻结）
```

## 导航结构

```
📈 个股资金流向   ← 默认，主力功能
🤖 AI 投顾       ← 最高优先级
🧩 决策面板 Beta（冻结）
⚙️ 系统管理
```

## 大模型使用

### 调用入口（共 3 处）

| 位置 | 文件:行 | 用途 |
|---|---|---|
| AI 投顾 — 主建议 | `ai_advisor.py:1046` | 完整个股分析，含 prompt 版本 |
| AI 投顾 — 追问 | `ai_advisor.py:1144` | 基于同一数据快照继续对话 |
| 图表解读 | `analysis_page.py:711` | 轻量版，仅基于当日图表数据 |

### 模型配置

- **客户端**：`stock_analysis/analysis/ai_client.py`
- **默认模型**：`deepseek-v4-flash`（1元/M输入，2元/M输出）
- **可选模型**：`deepseek-v4-pro`（AI 投顾页 UI 选择，深度分析用，3-12 倍贵）
- **图表解读 / 追问**：硬编码 flash，无需切换
- **Endpoint**：`DEEPSEEK_BASE_URL`（默认 `https://api.deepseek.com/v1`），兼容 OpenAI 接口格式
- **API Key 读取顺序**：`DEEPSEEK_API_KEY` → `DEEPSEEK_KEY` → `AI_API_KEY`（均从 `.env` 读取）

### Prompt 版本化

```
stock_analysis/analysis/prompts/
├── registry.py   # CURRENT_VERSION = "v1"，切换版本改这里
└── v1.py         # BASE_CONSTRAINTS（9 条静态规则）+ FOCUS_MAP + STYLE_MAP
```

**升级 prompt 流程**：
1. 复制 `v1.py` → `v2.py`，修改规则
2. `registry.py` 改 `CURRENT_VERSION = "v2"`
3. 每条 AI 建议自动标注版本号，历史记录互不干扰

### 复盘追踪

`data/advice_journal.db` 记录所有 AI 建议，字段含：
`stock_code / analysis_date / prompt_version / advice_text / actual_next_day_pct / actual_5d_pct`

T+1 / T+5 回填：在 AI 投顾页底部点「刷新 T+1/T+5 数据」，或手动跑：

```bash
python3 -c "
from stock_analysis.analysis.advice_journal import AdviceJournal
n = AdviceJournal().follow_up_pending()
print(f'已更新 {n} 条')
"
```

## 数据源

- **主力**：`AkShareProvider` — 所有页面默认使用
- **备用**：`TushareProvider` — 在个股资金流向页可手动切换（需输入 token）
- **全局市场**：`yfinance`（已删除独立页面，如需恢复在 global_markets_page.py 里直接 import）

## 环境变量（.env）

```
AI_API_KEY=sk-xxx          # DeepSeek API Key（必需）
TUSHARE_TOKEN=xxx          # 可选，个股流向页手动切换时用
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1   # 可选，换自定义 endpoint
```

## 开发约定

- **Python 版本**：3.9+，虚拟环境在 `.venv/`
- **启动调试**：直接 `streamlit run stock_analysis/ui/unified_app.py`
- **新增分析模块**：放 `stock_analysis/analysis/`，在 `analysis_page.py` 或 `ai_advisor.py` 里 import
- **修改 prompt 规则**：只动 `stock_analysis/analysis/prompts/` 里的版本文件，不要直接改 `_build_prompts`
- **Beta 面板**：`tasks/` `bridge/` `vendor/` 均为冻结状态，非必要不修改

## 数据沉淀层（stock_cache.db）

`data/stock_cache.db` 分三层，与 `advice_journal.db` 独立并存：

| 层 | 表 | 内容 | 新鲜度 |
|---|---|---|---|
| L1 | `daily_ohlc` | 日线 OHLC（qfq） | T-1 及之前永久；当日盘中不入库 |
| L1 | `minute_bars` | 历史分钟线 | 历史永久；当日不入库 |
| L1 | `stock_meta` | 股票元信息 | 每天刷新 1 次 |
| L1 | `stock_news` | 个股新闻 | 1 小时 TTL |
| L2 | `trend_signal_snapshot` | trend_signal 引擎输出 | 按 analysis_date 永久，同日覆盖 |
| L2 | `flow_summary_daily` | 资金流汇总快照 | 同上 |
| L2 | `price_range_snapshot` | 支撑/压力区间 | 同上 |
| L4 | `labels` | T+1/T+5/T+20 涨跌幅 | 回填后永久 |

数据访问入口：`stock_analysis/data/cache_store.py` → `CacheStore`

## 上轮变更对照（v2 → v3）

| 类型 | 之前 | 现在 |
|---|---|---|
| 导航 | 9 个并列页面，4 个分组 | 4 项扁平：资金流向 / AI 投顾 / Beta 决策（冻结）/ 系统管理 |
| 主文件 | future_features.py 2638 行 | ai_advisor.py 1652 行（删 986 行死代码） |
| 删除页面 | dashboard / global_markets / comparison / watchlist / alert / market 共 6 个 | 全部删除 |
| 删除分析模块 | market_hotspot.py / dragon_tiger.py | 全部删除 |
| AI 投顾 prompt | 散落在 `_build_prompts` 函数里 | 抽到 `prompts/v1.py`，registry 切换版本 |
| AI 投顾复盘 | 无 | `data/advice_journal.db` + UI 复盘 tab + T+1/T+5 回填 |
| 默认模型 | deepseek-v4-pro（12元/M） | deepseek-v4-flash（1元/M，省 10-12 倍） |
| Token 优化 | tick_window 40 条 / daily 20 条 | tick_window 20 条 / daily 10 条（输入 -24%） |
| 单次成本 | ~0.14 元 | ~0.012 元 |

## 上轮变更对照（v3 → v4）

| 类型 | 之前 | 现在 |
|---|---|---|
| 数据生命周期 | API 拉取 → 内存 → 显示 → 丢弃 | 落库到 stock_cache.db，下次直接命中 |
| 日线缓存 | `@st.cache_data` 每次进程内复用 | SQLite 持久化，重启后仍有效 |
| 新闻缓存 | 无缓存，每次请求 AkShare | 1 小时 TTL，过期才重拉 |
| L2 衍生数据 | 两个页面各自计算，结果不共享 | trend_signal / flow_summary / price_range 落 L2，可跨页面复用 |
| 训练数据 | 无积累机制 | L4 labels 表预留，6-12 个月后可训练 |
| ml 骨架 | 无 | stock_analysis/ml/ 占位，TODO 已记录 |

## 未来需要 stockdb 提供的接口

当本项目训练数据导出需求出现时（5000 只 × N 年规模），可能需要 stockdb 侧扩展：

1. **批量日线**：`db.daily_batch(codes: List[str], start, end)`
   单只 `db.daily` 已足够 cache_store 当前用，但训练集需要 5000+ 只，单只循环慢
2. **复权字段统一**：`db.daily(..., adjust='qfq')`
   stockdb 当前返回不复权，与本项目 AkShare qfq 不一致，需加参数
3. **全市场分钟级历史归档**：确认 `db.minutes_history` 覆盖范围

需要时请去 `/Users/wangluke/Localprojects/stock-data/` 设计相应代码。

## 当前状态（2026-05-12）

### 完成（v3）

- 大瘦身：删 6 个冷门页面 + market_hotspot/dragon_tiger + prefetch.py + yfinance_provider
- future_features.py → ai_advisor.py，清 986 行死代码
- AI 投顾强化：Prompt 版本化 + 复盘日志（SQLite + UI）
- Beta 面板冻结 banner

### 完成（v4）

- 数据沉淀层 stock_cache.db：L1 原始缓存 + L2 衍生快照 + L4 训练标签
- cache_store.py：透明缓存，日线/新闻/元信息自动持久化
- AI 投顾接入：`_load_daily_history` / `_load_stock_news` 走 cache_store；trend_signal 落 L2
- 个股资金流向接入：flow_summary / price_range 落 L2
- ml/ 骨架：export_training_set.py + label_backfiller.py 占位

### 后续待做

| 优先级 | 任务 |
|---|---|
| 高 | 基于复盘 T+1 数据调优 prompt → v2 |
| 高 | 个股资金流向 → AI 投顾「一键跳转+触发」按钮 |
| 中 | T+1/T+5/T+20 labels 自动回填（参考 advice_journal.follow_up_pending） |
| 中 | T+1 回填自动化（launchd 定时，每天 16:00）|
| 低 | 训练集导出 CLI 实现（数据累积 6 个月后）|
| 低 | Beta 面板最终决断（稳定后删 tasks/bridge/vendor）|
