# 📈 A股资金流向智能分析系统 (Stock Flow Analysis)

一个基于 Streamlit 的现代化股票分析平台，专注于资金流向的可视化分析。整合 AkShare 和 Tushare 双数据源，提供个股资金博弈、即时热点追踪及多股对比分析功能。

![Version](https://img.shields.io/badge/version-2.2-blue) ![Python](https://img.shields.io/badge/python-3.9%2B-green) ![License](https://img.shields.io/badge/license-MIT-orange)

---

## ✨ 核心功能

- **📊 个股全景分析**: 累计资金流、日内热力图、买卖力道分析。
- **🔥 市场热点追踪**: 实时板块排行、涨停板分析、龙虎榜追踪。
- **⚖️ 多股对比 (Pro)**: 双股票走势叠加与资金流同步对比。
- **🛠 专业工具箱**: 本地自选股、CSV导入导出、智能缓存管理。

## 📚 文档索引

本项目的文档结构已经过整理，请查阅以下指南：

| 文档名称 | 内容说明 |
| :--- | :--- |
| **[📘 用户手册 (User Manual)](USER_MANUAL.md)** | **强烈推荐阅读**。包含从入门到精通的所有使用方法、图表算法原理及常见问题。 |
| **[🚀 部署指南 (Deployment)](DEPLOYMENT_GUIDE.md)** | 包含本地运行、Streamlit Cloud 云端部署、Docker 及服务器部署教程。 |
| **[🗺️ 开发路线图 (Roadmap)](ROADMAP.md)** | 项目的近期计划（历史回测、AI分析）与长期规划。 |

## 🏎️ 快速开始

### 1. 环境准备
确保已安装 Python 3.9+ 和 Git。

### 2. 安装运行
```bash
# 克隆项目
git clone <your-repo-url>
cd 读取股票当天数据

# 安装依赖
pip install -r requirements.txt

# 启动系统 (Mac/Linux)
./启动分析系统.command

# 或者通用启动命令
streamlit run stock_analysis/ui/unified_app.py
```

## 🔐 数据源配置

本系统开箱即用（默认 AkShare）。如需更高质量数据，推荐配置 **Tushare Pro**：
1. 注册 [Tushare Pro](https://tushare.pro/register) 获取 Token。
2. 在项目根目录创建 `.env` 文件：`TUSHARE_TOKEN=your_token`。
3. 详见 [用户手册 - 数据源配置](USER_MANUAL.md#5-数据源配置-tushare)。

---

## 🏗️ 项目结构

```
stock_analysis/
├── analysis/       # 核心分析逻辑 (资金流、指标、异常检测)
├── data/           # 数据层 (AkShare/Tushare 提供者、清洗器)
├── ui/             # 界面层 (Streamlit 页面、组件)
├── visualization/  # 可视化层 (Plotly 图表生成器)
└── core/           # 基础设施 (配置、缓存、存储)
```

## 🤝 贡献与反馈

欢迎提交 Issue 或 PR。新功能建议请参考 [Roadmap](ROADMAP.md)。

License: MIT