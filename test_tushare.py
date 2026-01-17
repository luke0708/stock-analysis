#!/usr/bin/env python
import os
import tushare as ts

# 测试环境变量和 Tushare 连接
print("=" * 50)
print("Tushare Token 验证")
print("=" * 50)

token = os.getenv("TUSHARE_TOKEN")
if token:
    print(f"✅ 环境变量已设置")
    print(f"Token 长度: {len(token)} 字符")
    print(f"Token 前5位: {token[:5]}...")
    
    try:
        print("\n正在测试 Tushare 连接...")
        ts.set_token(token)
        pro = ts.pro_api()
        
        # 测试获取股票基本信息
        df = pro.stock_basic(ts_code='300661.SZ', fields='ts_code,name')
        
        if not df.empty:
            print(f"✅ Tushare 连接成功！")
            print(f"测试股票: {df.iloc[0]['name']} ({df.iloc[0]['ts_code']})")
        else:
            print("⚠️ 连接成功但未获取到数据")
            
    except Exception as e:
        print(f"❌ Tushare 连接失败: {str(e)}")
        if "token" in str(e).lower():
            print("提示: Token 可能无效，请检查是否复制完整")
else:
    print("❌ 未检测到环境变量 TUSHARE_TOKEN")
    print("请运行: export TUSHARE_TOKEN='你的token'")
