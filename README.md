# A股资金流向智能分析系统 (Stock Flow Analysis)

一个基于 Streamlit 的股票分析平台，聚焦资金流向与盘中节奏。默认使用 AkShare，支持可选的 Tushare 与全球市场数据源，并内置 AI 智能解读。

![Version](https://img.shields.io/badge/version-2.2-blue) ![Python](https://img.shields.io/badge/python-3.9%2B-green) ![License](https://img.shields.io/badge/license-MIT-orange)

---

## 核心能力

- 个股资金流向：净流入、热力图、主力/散户结构、异动追踪。
- 市场全景：板块热点、龙虎榜、市场情绪与资讯。
- 多股对比：双股票走势与资金流对照。
- 实时预警：多股监控、连续触发、交易时段自动暂停。
- 全球市场：A 股指数 + 美股/港股（YFinance）。
- AI 智能投顾：结构化解读 + 可选新闻补充 + 追问。
- 自选股：本地收藏常用标的。

## 快速开始

```bash
# 进入项目
cd 读取股票当天数据

# 安装依赖（请使用本地 venv）
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 启动系统（macOS 推荐）
./启动分析系统.command

# 或使用命令行启动
streamlit run stock_analysis/ui/unified_app.py
```

浏览器打开 `http://localhost:8501`。

## 数据源与密钥

- 默认数据源：AkShare（免注册）。
- 可选：Tushare（更稳定），在 `.env` 中配置 `TUSHARE_TOKEN=...`。
- AI 解读：在 `.env` 中配置 `DEEPSEEK_API_KEY=...`。

## 文档索引

| 文档名称 | 内容说明 |
| :--- | :--- |
| [用户手册](USER_MANUAL.md) | 面向最终用户的使用说明与页面导航。 |
| [部署手册](DEPLOYMENT.md) | 本地/云端运行与运维说明。 |
| [开发交接](DEV_HANDOVER.md) | 面向开发者的结构、入口与技术债。 |
| [规划路线](ROADMAP.md) | 产品优先级与迭代计划。 |

## 项目结构

```
stock_analysis/
├── analysis/       # 核心分析逻辑
├── data/           # 数据源与清洗
├── ui/             # Streamlit 页面
├── visualization/  # 图表生成
└── core/           # 缓存与基础设施
```

## 贡献与反馈

欢迎提交 Issue 或 PR。建议先阅读 `DEV_HANDOVER.md`。

License: MIT
