# 股票资金流向分析系统

实时分钟级资金流向分析工具，支持多维度技术指标和可视化。

## 功能特点

- 📊 实时数据获取（Tushare Pro / AkShare）
- 💰 资金流向分析（主力vs散户）
- 📈 技术指标计算（VWAP、MA、累计涨跌幅）
- 🎯 异常检测（大单、价格跳跃）
- 📉 买卖盘强度分析
- 🎨 丰富的交互式图表

## 在线访问

部署后的应用地址：`https://your-app.streamlit.app`

## 本地运行

```bash
# 1. 克隆项目
git clone <your-repo-url>
cd 读取股票当天数据

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置Tushare Token（可选）
# 创建 .env 文件并添加：
# TUSHARE_TOKEN=your_token_here

# 4. 运行
streamlit run stock_analysis/ui/app.py
```

## 部署到 Streamlit Cloud

1. 推送代码到 GitHub
2. 访问 https://share.streamlit.io
3. 连接 GitHub 仓库
4. 设置 Main file: `stock_analysis/ui/app.py`
5. 在 Secrets 中配置 `TUSHARE_TOKEN`（如果使用 Tushare）

## 集成到其他网页

作为 iframe 嵌入：

```html
<iframe 
  src="https://your-app.streamlit.app" 
  width="100%" 
  height="900px"
  frameborder="0">
</iframe>
```

## 技术栈

- Python 3.9+
- Streamlit
- Pandas, Plotly
- AkShare / Tushare Pro

## 许可

MIT License

## 免责声明

本工具仅供学习参考，不构成投资建议。股市有风险，投资需谨慎。
