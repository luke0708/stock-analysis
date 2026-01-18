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

## 3. Streamlit Cloud（展示/共享）

1. 推送代码到 GitHub。
2. 在 Streamlit Cloud 创建应用，入口文件填 `stock_analysis/ui/unified_app.py`。
3. 在 Secrets 中配置 `TUSHARE_TOKEN`、`DEEPSEEK_API_KEY`（如需）。

## 4. Docker（可选）

```dockerfile
FROM python:3.9-slim
WORKDIR /app
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
