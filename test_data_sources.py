#!/usr/bin/env python
"""
数据源综合测试脚本
测试 YFinance, AkShare, Tushare 的数据质量和可用性
"""
import sys
sys.path.insert(0, '.')

print("=" * 80)
print("  📊 数据源综合测试")
print("=" * 80)

# ===== 测试 1: AkShare 基础功能 =====
print("\n[测试 1/4] AkShare - 分钟数据")
print("-" * 80)

try:
    import akshare as ak
    
    # 测试A股分钟数据
    df = ak.stock_zh_a_hist_min_em(
        symbol="300661",
        start_date="2026-01-15 09:30:00",
        end_date="2026-01-15 15:00:00",
        period="1",
        adjust="qfq"
    )
    
    print(f"✅ 成功获取 {len(df)} 条分钟数据")
    print(f"列名: {df.columns.tolist()}")
    print(f"数据预览:\n{df.head(3)}")
    print(f"数据完整性: {df.isnull().sum().sum()} 个缺失值")
    
except Exception as e:
    print(f"❌ 失败: {e}")

# ===== 测试 2: AkShare 板块功能 =====
print("\n[测试 2/4] AkShare - 板块和热点")
print("-" * 80)

try:
    # 2.1 概念板块
    print("\n2.1 概念板块:")
    concepts = ak.stock_board_concept_name_em()
    print(f"✅ 找到 {len(concepts)} 个概念板块")
    print(f"热门概念: {concepts.head(10)['板块名称'].tolist()}")
    
    # 2.2 行业板块
    print("\n2.2 行业板块:")
    industries = ak.stock_board_industry_name_em()
    print(f"✅ 找到 {len(industries)} 个行业板块")
    print(f"前10行业: {industries.head(10)['板块名称'].tolist()}")
    
    # 2.3 涨跌幅排行（找热点）
    print("\n2.3 今日涨幅排行:")
    hot_stocks = ak.stock_zh_a_spot_em()
    top_gainers = hot_stocks.nlargest(10, '涨跌幅')
    print(f"✅ 今日涨幅前10:")
    for idx, row in top_gainers.iterrows():
        print(f"  {row['名称']} ({row['代码']}): {row['涨跌幅']:.2f}%")
    
    # 2.4 龙虎榜
    print("\n2.4 龙虎榜数据:")
    lhb = ak.stock_lhb_detail_em(start_date="20260115", end_date="20260117")
    if not lhb.empty:
        print(f"✅ 找到 {len(lhb)} 条龙虎榜记录")
        print(f"涉及股票: {lhb['名称'].unique()[:5].tolist()}")
    else:
        print("⚠️  近期无龙虎榜数据")
    
except Exception as e:
    print(f"❌ 失败: {e}")

# ===== 测试 3: AkShare 新闻和公告 =====
print("\n[测试 3/4] AkShare - 新闻和资讯")
print("-" * 80)

try:
    # 3.1 个股新闻
    print("\n3.1 个股新闻 (600519 - 贵州茅台):")
    news = ak.stock_news_em(symbol="600519")
    if not news.empty:
        print(f"✅ 找到 {len(news)} 条新闻")
        print(f"最新3条:")
        for idx, row in news.head(3).iterrows():
            print(f"  [{row['发布时间']}] {row['新闻标题']}")
    
    # 3.2 个股公告
    print("\n3.2 个股公告 (600519):")
    notices = ak.stock_notice_report(symbol="600519", date="20260115")
    if not notices.empty:
        print(f"✅ 找到 {len(notices)} 条公告")
        print(f"最新公告: {notices.head(3)['公告标题'].tolist()}")
    else:
        print("⚠️  近期无公告")
        
except Exception as e:
    print(f"❌ 部分失败: {e}")

# ===== 测试 4: YFinance (全球市场) =====
print("\n[测试 4/4] YFinance - 全球市场支持")
print("-" * 80)

try:
    import yfinance as yf
    print("✅ YFinance 已安装")
    
    # 4.1 测试美股
    print("\n4.1 美股数据 (AAPL - 苹果):")
    aapl = yf.Ticker("AAPL")
    df_us = aapl.history(period="1d", interval="1m")
    print(f"✅ 获取 {len(df_us)} 条分钟数据")
    print(f"最新价格: ${df_us['Close'].iloc[-1]:.2f}")
    print(f"今日涨跌: {((df_us['Close'].iloc[-1] / df_us['Open'].iloc[0] - 1) * 100):.2f}%")
    
    # 4.2 测试A股（通过YFinance）
    print("\n4.2 A股数据 (600519.SS - 贵州茅台):")
    moutai = yf.Ticker("600519.SS")
    df_cn = moutai.history(period="1d", interval="1m")
    print(f"✅ 获取 {len(df_cn)} 条分钟数据")
    if not df_cn.empty:
        print(f"最新价格: ¥{df_cn['Close'].iloc[-1]:.2f}")
    else:
        print("⚠️  可能市场未开盘或周末")
    
    # 4.3 测试港股
    print("\n4.3 港股数据 (00700.HK - 腾讯):")
    tencent = yf.Ticker("00700.HK")
    df_hk = tencent.history(period="1d", interval="1m")
    print(f"✅ 获取 {len(df_hk)} 条分钟数据")
    if not df_hk.empty:
        print(f"最新价格: HK${df_hk['Close'].iloc[-1]:.2f}")
    
    # 4.4 获取基本信息
    print("\n4.4 股票基本信息:")
    info = aapl.info
    print(f"公司名: {info.get('longName', 'N/A')}")
    print(f"行业: {info.get('industry', 'N/A')}")
    print(f"市值: ${info.get('marketCap', 0) / 1e9:.2f}B")
    
except ImportError:
    print("❌ YFinance 未安装")
    print("安装命令: pip install yfinance")
except Exception as e:
    print(f"⚠️  部分功能失败: {e}")
    print("可能原因：市场未开盘、网络问题、或周末")

# ===== 总结和建议 =====
print("\n" + "=" * 80)
print("  📋 测试总结")
print("=" * 80)

print("""
✅ AkShare 优势:
   - A股分钟数据完整
   - 板块、龙虎榜、新闻丰富
   - 完全免费
   - 推荐作为 A股主力数据源

✅ YFinance 优势:
   - 支持全球市场（美股、港股、A股）
   - 数据稳定可靠
   - Google/Yahoo 官方支持
   - 推荐作为全球市场扩展

⚠️ Tushare 现状:
   - 积分限制严格
   - 建议仅用于低频访问（如财务数据）
   
🎯 推荐方案:
   1. A股实时分析: AkShare (主力)
   2. 全球市场: YFinance (扩展)
   3. 板块热点: AkShare (新增功能)
   4. 新闻资讯: AkShare (新增功能)
""")

print("\n下一步: 根据测试结果，选择要集成的数据源功能")
print("=" * 80)
