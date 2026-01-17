#!/usr/bin/env python
"""
Tushare Token 更新助手
"""
import os
from pathlib import Path

print("="*60)
print("  Tushare Token 更新助手")
print("="*60)
print()
print("请按以下步骤操作：")
print()
print("1️⃣  访问 https://tushare.pro 并登录")
print()
print("2️⃣  登录后，在首页或个人中心找到 'Token' 或 'API Token'")
print("    通常显示为：token: xxxxxxxxxxxxxxxx")
print()
print("3️⃣  完整复制 Token（不要包含 'token:' 这几个字）")
print()
print("4️⃣  粘贴到下面：")
print()

new_token = input("请粘贴您的 Tushare Token: ").strip()

if not new_token:
    print("❌ Token 为空，退出")
    exit(1)

# 验证格式
if len(new_token) < 30:
    print(f"⚠️  警告: Token 长度只有 {len(new_token)} 字符，看起来太短了")
    confirm = input("是否继续？(y/n): ")
    if confirm.lower() != 'y':
        exit(1)

print()
print("正在验证 Token...")

# 快速验证
try:
    import tushare as ts
    ts.set_token(new_token)
    pro = ts.pro_api()
    df = pro.stock_basic(exchange='', list_status='L', fields='ts_code')
    
    if df is not None and not df.empty:
        print("✅ Token 验证成功！")
        print(f"成功获取到 {len(df)} 只股票信息")
        
        # 更新 .env 文件
        env_path = Path(__file__).parent / '.env'
        env_content = f"""# Tushare 配置
# Token 最后更新: {os.popen('date').read().strip()}
TUSHARE_TOKEN={new_token}
"""
        
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(env_content)
        
        print(f"✅ 已更新 .env 文件: {env_path}")
        print()
        print("🎉 完成！现在可以在网页中选择 'Tushare Pro' 数据源了")
        print()
        print("💡 重新启动应用:")
        print("   ./启动分析系统.command")
        
    else:
        print("⚠️  Token 设置成功，但未获取到数据")
        
except Exception as e:
    print(f"❌ Token 验证失败: {e}")
    print()
    print("可能的原因:")
    print("1. Token 格式错误（请重新复制）")
    print("2. 账号未激活（检查邮箱激活邮件）")
    print("3. 网络问题")
