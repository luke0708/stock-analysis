# 部署手册 (Deployment)

本文档面向运维与部署人员，说明系统如何安装、启动与运行。

## 1. 本地运行（macOS 推荐）

### 1.1 环境准备
- Python 3.9+
- Git

### 1.2 安装依赖（本地 venv）
```bash
cd 读取股票当天数据
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 1.3 环境变量（可选）
在项目根目录创建 `.env`：
```ini
TUSHARE_TOKEN=your_token_here
DEEPSEEK_API_KEY=your_key_here
```

### 1.4 启动方式
推荐使用脚本（会自动清理旧进程并占用 8501 端口）：
```bash
./启动分析系统.command
```

或使用命令行启动：
```bash
streamlit run stock_analysis/ui/unified_app.py
```

浏览器访问 `http://localhost:8501`。

## 2. 后台运行（可选）

如需后台常驻，建议直接使用 Streamlit 命令并在项目根目录执行：
```bash
nohup streamlit run stock_analysis/ui/unified_app.py --server.port=8501 >/tmp/streamlit.log 2>&1 &
```

查看端口占用：
```bash
lsof -i:8501
```

## 3. Streamlit Cloud 部署 (推荐)

最适合分享和展示的免费方案。

### 3.1 准备工作
- GitHub 账号
- Streamlit Cloud 账号

### 3.2 部署步骤
1. **推送到 GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   # 替换为你的仓库地址
   git remote add origin https://github.com/YOUR_USERNAME/stock-analysis.git
   git push -u origin main
   ```

2. **在 Streamlit Cloud 创建应用**
   - 访问 [share.streamlit.io](https://share.streamlit.io)
   - 点击 "New app"
   - 选择 Repository: `stock-analysis`
   - Main file path: `stock_analysis/ui/unified_app.py`
   - 点击 "Deploy"

3. **配置 Secrets (环境变量)**
   - 在应用管理界面点击 "Advanced settings" -> "Secrets"
   - 添加配置：
     ```toml
     TUSHARE_TOKEN = "your_token_here"
     DEEPSEEK_API_KEY = "your_key_here"
     ```

**优缺点**：
- ✅ 完全免费，自动 HTTPS，随时随地访问
- ❌ 资源有限 (1GB RAM)，休眠后需冷启动

## 4. Docker（可选）

```dockerfile
FROM python:3.9-slim

COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "stock_analysis/ui/unified_app.py"]
```

运行：
```bash
docker build -t stock-analysis .
docker run -p 8501:8501 stock-analysis
```

## 5. 运行入口速查

- GUI 启动：`./启动分析系统.command`
- CLI 启动：`streamlit run stock_analysis/ui/unified_app.py`
- 备用入口：`python run.py`
