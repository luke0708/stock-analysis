# 部署指南

## 本地部署（当前方式）

您目前使用的就是本地部署：
```bash
./启动分析系统.command
```

**优点**：
- 数据私密，不上传到云端
- 响应速度快
- 完全免费

**缺点**：
- 只能在本机使用
- 需要保持应用运行

---

## 云端部署选项

### 方案1：Streamlit Cloud（推荐，免费）

#### 步骤：

1. **准备代码**
```bash
# 1. 初始化git仓库（如果还没有）
git init
git add .
git commit -m "Initial commit"

# 2. 推送到GitHub
git remote add origin <你的GitHub仓库地址>
git push -u origin main
```

2. **部署到Streamlit Cloud**
- 访问 https://share.streamlit.io
- 登录GitHub账号
- 点击 "New app"
- 选择你的仓库
- Main file path: `stock_analysis/ui/app.py`
- 点击 "Deploy"

3. **配置环境变量**
在Streamlit Cloud设置中添加：
```
TUSHARE_TOKEN=你的token
```

**优点**：
- 完全免费
- 自动SSL证书
- 随时随地访问
- 自动更新

**限制**：
- 资源有限（1GB RAM）
- Public访问（可设置密码）

---

### 方案2：Docker 部署

创建 `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "stock_analysis/ui/app.py"]
```

运行：
```bash
# 构建
docker build -t stock-analysis .

# 运行
docker run -p 8501:8501 -e TUSHARE_TOKEN=你的token stock-analysis
```

---

### 方案3：服务器部署（需要有服务器）

#### 使用 Nginx + Streamlit

1. **安装依赖**
```bash
# 在服务器上
cd /var/www/stock-analysis
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. **使用 systemd 管理服务**

创建 `/etc/systemd/system/stock-analysis.service`:
```ini
[Unit]
Description=Stock Analysis App
After=network.target

[Service]
User=your_user
WorkingDirectory=/var/www/stock-analysis
Environment="PATH=/var/www/stock-analysis/venv/bin"
Environment="TUSHARE_TOKEN=你的token"
ExecStart=/var/www/stock-analysis/venv/bin/streamlit run stock_analysis/ui/app.py --server.port 8501

[Install]
WantedBy=multi-user.target
```

启动：
```bash
sudo systemctl enable stock-analysis
sudo systemctl start stock-analysis
```

3. **配置 Nginx 反向代理**

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

## 推荐部署方案对比

| 方案 | 成本 | 难度 | 适用场景 |
|------|------|------|----------|
| 本地部署 | 免费 | ⭐ | 个人使用 |
| Streamlit Cloud | 免费 | ⭐⭐ | 学习/展示 |
| Docker | 服务器成本 | ⭐⭐⭐ | 团队使用 |
| 服务器+Nginx | 服务器成本 | ⭐⭐⭐⭐ | 生产环境 |

---

## 🎯 我的建议

**对于您的使用场景**：

1. **短期/个人使用**: 继续使用本地部署即可
2. **想要分享**: 使用 Streamlit Cloud（免费且简单）
3. **团队协作**: 考虑Docker或服务器部署

**需要帮助选择或配置任何方案，请告诉我！**
