#!/usr/bin/env python
"""
快速测试脚本 - 使用 AkShare 验证系统功能
"""
import sys
sys.path.insert(0, 'stock_analysis')

from stock_analysis.data.providers.akshare_provider import AkShareProvider
from stock_analysis.analysis.flows import FlowAnalyzer

print("="*60)
print("📊 系统功能测试 (使用 AkShare)")
print("="*60)

code = "300661"
date_str = "20260115"

print(f"\n测试股票: {code}")
print(f"测试日期: {date_str}\n")

# 1. 测试数据获取
print("1️⃣ 测试数据获取...")
provider = AkShareProvider()
df = provider.get_tick_data(code, date_str)

if df.empty:
    print("❌ 数据获取失败")
    sys.exit(1)

print(f"✅ 成功获取 {len(df)} 条数据")
print(f"数据列: {list(df.columns)}")
print(f"\n数据预览:")
print(df.head(3))

# 2. 测试资金流向分析
print("\n2️⃣ 测试资金流向分析...")
analyzer = FlowAnalyzer()
result = analyzer.calculate_flows(df)

print(f"✅ 分析完成")
print(f"总成交额: ¥{result.get('total_turnover', 0):,.0f}")
print(f"主力净流入: ¥{result.get('large_order_net_inflow', 0):,.0f}")
print(f"散户净流入: ¥{result.get('retail_net_inflow', 0):,.0f}")

print("\n" + "="*60)
print("✅ 系统功能正常！AkShare 可以作为备用数据源")
print("="*60)
print("\n💡 关于 Tushare Token:")
print("1. 请访问 https://tushare.pro 登录您的账号")
print("2. 检查账号是否已激活（新注册账号需要邮箱激活）")
print("3. 在个人中心页面重新复制 Token")
print("4. Token 应该是一串 40-60 个字符的字母数字组合")
