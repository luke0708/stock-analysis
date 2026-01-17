#!/usr/bin/env python
"""
快速测试新功能
测试板块热点、龙虎榜、新闻功能
"""
import sys
sys.path.insert(0, '.')

print("="*70)
print("  🚀 新功能快速测试")
print("="*70)

# 测试1: 板块热点
print("\n[1/3] 测试板块热点功能")
print("-"*70)

try:
    from stock_analysis.analysis.market_hotspot import MarketHotspotAnalyzer, format_hotspot_summary
    
    analyzer = MarketHotspotAnalyzer()
    
    # 获取热门概念
    concepts = analyzer.get_hot_concepts(top_n=5)
    print(f"✅ 获取到 {len(concepts)} 个热门概念")
    print(concepts[['板块名称', '涨跌幅', '领涨股票']].to_string(index=False))
    
    # 市场情绪
    sentiment = analyzer.analyze_market_sentiment()
    print(f"\n市场情绪: {sentiment.get('market_sentiment')}")
    print(f"上涨/下跌: {sentiment.get('rising_count')}/{sentiment.get('falling_count')}")
    
except Exception as e:
    print(f"❌ 失败: {e}")

# 测试2: 龙虎榜
print("\n[2/3] 测试龙虎榜功能")
print("-"*70)

try:
    from stock_analysis.analysis.dragon_tiger import DragonTigerAnalyzer, format_lhb_summary
    
    analyzer = DragonTigerAnalyzer()
    
    # 获取最近龙虎榜
    lhb = analyzer.get_recent_lhb(days=3)
    print(f"✅ 获取到 {len(lhb)} 条龙虎榜记录")
    
    if not lhb.empty:
        print(f"涉及股票: {lhb['名称'].unique()[:5].tolist()}")
        
        # 统计
        stats = analyzer.get_lhb_statistics(lhb)
        print(f"买入总额: ¥{stats.get('buy_amount_total', 0)/1e8:.2f}亿")
        print(f"卖出总额: ¥{stats.get('sell_amount_total', 0)/1e8:.2f}亿")
    
except Exception as e:
    print(f"❌ 失败: {e}")

# 测试3: 新闻
print("\n[3/3] 测试新闻功能")
print("-"*70)

try:
    from stock_analysis.data.news_provider import StockNewsProvider, format_news_summary
    
    provider = StockNewsProvider()
    
    # 获取贵州茅台新闻
    news = provider.get_stock_news("600519", limit=5)
    print(f"✅ 获取到 {len(news)} 条新闻")
    
    if not news.empty:
        for idx, row in news.head(3).iterrows():
            print(f"  [{row['发布时间']}] {row['新闻标题']}")
    
except Exception as e:
    print(f"❌ 失败: {e}")

print("\n" + "="*70)
print("  ✅ 测试完成！")
print("="*70)
print("\n下一步: 启动应用查看新功能")
print("./启动分析系统.command")
