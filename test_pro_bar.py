#!/usr/bin/env python
"""
测试 Tushare 分钟数据接口（用于实际使用的接口）
"""
import tushare as ts
from datetime import datetime

token = "365fe8d7fde6ef7897999508672ff31a9a3184147207497fef4e64c5"

print("="*60)
print("🧪 测试 Tushare Pro_bar 接口")
print("="*60)

try:
    ts.set_token(token)
    pro = ts.pro_api()
    
    print("\n正在获取 300661.SZ 的分钟数据...")
    print("(这是系统实际使用的接口)\n")
    
    # 测试 pro_bar (这是我们实际用的接口)
    df = ts.pro_bar(
        ts_code='300661.SZ', 
        freq='1min',
        start_date='20260115',
        end_date='20260115',
        adj='qfq'
    )
    
    if df is not None and not df.empty:
        print(f"✅ 成功！获取到 {len(df)} 条分钟数据")
        print("\n数据预览:")
        print(df.head(3))
        print("\n" + "="*60)
        print("🎉 Tushare Pro 完全可用！")
        print("="*60)
        print("\n下一步:")
        print("1. 启动应用: ./启动分析系统.command")
        print("2. 在界面选择 'Tushare Pro (推荐)'")
        print("3. 开始高质量数据分析！")
    else:
        print("⚠️  Token 有效，但未获取到数据")
        print("可能原因: 今天是周末，使用历史日期试试")
        
except Exception as e:
    print(f"❌ 错误: {e}")
    
    if "权限" in str(e) or "积分" in str(e):
        print("\n💡 积分不足提示:")
        print("- 完善个人资料可获得额外积分")
        print("- 或继续使用 AkShare 备用数据源")
