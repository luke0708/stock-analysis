# Streamlit Cloud 部署指南

## 📋 部署前准备清单

### 1. 确保所有文件就绪
- ✅ `requirements.txt` - 依赖列表
- ✅ `.streamlit/config.toml` - Streamlit配置
- ✅ `.gitignore` - Git忽略文件
- ✅ `README_DEPLOY.md` - 项目说明
- ✅ 所有代码文件

### 2. 测试本地运行
```bash
streamlit run stock_analysis/ui/app.py
```
确保没有错误。

---

## 🚀 部署步骤（10分钟）

### Step 1: 推送到 GitHub

```bash
# 1. 初始化 Git（如果还没有）
cd /Users/wangluke/Library/CloudStorage/OneDrive-共享的库-onedrive/Development/Projects/读取股票当天数据
git init

# 2. 添加所有文件
git add .

# 3. 提交
git commit -m "Initial commit - Stock analysis system"

# 4. 在 GitHub 创建新仓库
# 访问 https://github.com/new
# 仓库名建议：stock-analysis 或 stock-flow-analysis

# 5. 连接远程仓库（替换成您的仓库地址）
git remote add origin https://github.com/YOUR_USERNAME/stock-analysis.git

# 6. 推送
git branch -M main
git push -u origin main
```

### Step 2: 部署到 Streamlit Cloud

1. **访问** https://share.streamlit.io

2. **登录** 使用 GitHub 账号登录

3. **创建新应用**
   - 点击 "New app"
   - Repository: 选择刚才创建的仓库
   - Branch: `main`
   - Main file path: `stock_analysis/ui/app.py`
   - App URL: 会自动生成，如 `your-app-name.streamlit.app`

4. **配置 Secrets**（可选，用于 Tushare）
   - 点击 "Advanced settings"
   - 在 "Secrets" 中添加：
   ```toml
   TUSHARE_TOKEN = "your_tushare_token_here"
   ```

5. **点击 Deploy** 🚀

6. **等待部署**（2-3分钟）
   - 会看到构建日志
   - 成功后自动打开应用

---

## 📝 部署后的 URL

部署成功后，您会得到一个 URL，例如：
```
https://stock-analysis-xxx.streamlit.app
```

**保存这个 URL**，后面集成到主网页时需要用到。

---

## 🔧 常见问题

### Q1: 部署失败，提示模块找不到
**解决**: 确保 `requirements.txt` 包含所有依赖
```bash
# 本地测试生成
pip freeze > requirements.txt
```

### Q2: Tushare Token 不工作
**解决**: 
1. 检查 Secrets 中的 Token 是否正确
2. 或者在应用中手动输入 Token

### Q3: 应用运行慢
**解决**: 
1. Streamlit Cloud 免费版资源有限
2. 考虑升级或优化代码
3. 添加缓存装饰器 `@st.cache_data`

### Q4: 想要修改代码
**解决**:
```bash
# 本地修改代码
git add .
git commit -m "Update features"
git push

# Streamlit Cloud 会自动重新部署
```

---

## 🎯 下一步：集成到主网页

部署成功后，使用下面的代码集成到主网页：

```html
<!-- 在主网页添加新 tab -->
<div class="tab-panel" id="analysis-panel">
  <h2>📈 资金流向分析</h2>
  <iframe 
    src="https://your-app-xxx.streamlit.app"
    width="100%"
    height="900px"
    frameborder="0"
    style="border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
  </iframe>
</div>
```

详细集成代码见 `INTEGRATION_CODE.html`

---

## 📊 监控和管理

### 访问管理面板
https://share.streamlit.io/

可以查看：
- 应用状态
- 访问统计
- 日志输出
- 重启应用

### 更新应用
只需推送新代码到 GitHub：
```bash
git add .
git commit -m "Update"
git push
```
Streamlit Cloud 会自动重新部署。

---

## 💡 优化建议

### 1. 添加缓存
```python
@st.cache_data(ttl=300)  # 缓存5分钟
def get_stock_data(code, date):
    # ... 数据获取逻辑
    pass
```

### 2. 压缩依赖
只保留必要的库，减小部署包大小。

### 3. 错误处理
确保所有可能出错的地方都有 try-except。

---

准备好部署了吗？开始吧！🚀
