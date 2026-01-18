# 部署指南 (Deployment Guide)

本指南详细介绍了将 **A股资金流向智能分析系统** 部署到不同环境的方法。

## 📋 目录
1. [本地部署 (Local)](#1-本地部署-local)
2. [Streamlit Cloud 部署 (推荐)](#2-streamlit-cloud-部署-推荐)
3. [Docker 部署](#3-docker-部署)
4. [服务器部署 (Nginx)](#4-服务器部署-nginx)
5. [网页集成指南](#5-网页集成指南)

---

## 1. 本地部署 (Local)

最简单的方式，适合个人开发和使用。

### 1.1 环境要求
- Python 3.9+
- Git

### 1.2 启动步骤
1. **克隆项目**
   ```bash
   git clone <your-repo-url>
   cd 读取股票当天数据
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **配置 Token (可选)**
   创建 `.env` 文件并添加 Tushare Token：
   ```ini
   TUSHARE_TOKEN=your_token_here
   ```

4. **运行应用**
   使用便捷脚本：
   ```bash
   ./启动分析系统.command
   ```
   或者使用命令行：
   ```bash
   streamlit run stock_analysis/ui/unified_app.py
   ```

**优缺点**：
- ✅ 数据完全私密，本地运行速度快
- ❌ 需要保持电脑开启

---

## 2. Streamlit Cloud 部署 (推荐)

最适合分享和展示的免费方案。

### 2.1 准备工作
- GitHub 账号
- Streamlit Cloud 账号

### 2.2 部署步骤
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
     ```

**优缺点**：
- ✅ 完全免费，自动 HTTPS，随时随地访问
- ❌ 资源有限 (1GB RAM)，休眠后需冷启动

---

## 3. Docker 部署

适合团队协作或不仅限于 Streamlit 环境。

### 3.1 Dockerfile
项目根目录已包含标准 `Dockerfile`：
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "stock_analysis/ui/unified_app.py"]
```

### 3.2 运行
```bash
# 构建镜像
docker build -t stock-analysis .

# 运行容器
docker run -p 8501:8501 -e TUSHARE_TOKEN=your_token stock-analysis
```

---

## 4. 服务器部署 (Nginx)

适合生产环境，需要自备 Linux 服务器。

### 4.1 Systemd 服务配置
创建 `/etc/systemd/system/stock-analysis.service`:
```ini
[Unit]
Description=Stock Analysis App
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/stock-analysis
Environment="PATH=/var/www/stock-analysis/venv/bin"
Environment="TUSHARE_TOKEN=your_token"
ExecStart=/var/www/stock-analysis/venv/bin/streamlit run stock_analysis/ui/unified_app.py --server.port 8501

[Install]
WantedBy=multi-user.target
```

### 4.2 Nginx 反向代理
`/etc/nginx/sites-available/stock-analysis`:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

---

## 5. 网页集成指南

如果您现有的网站想嵌入此分析工具，可以使用 iframe 集成。

```html
<div class="analysis-container">
  <iframe 
    src="https://your-app-name.streamlit.app?embed=true"
    width="100%" 
    height="800px"
    frameborder="0"
    style="border: 1px solid #e1e4e8; border-radius: 8px;">
  </iframe>
</div>
```
