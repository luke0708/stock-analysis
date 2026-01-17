#!/usr/bin/env python
"""
增强功能测试脚本
测试所有新增的分析和可视化功能
"""
import sys
sys.path.insert(0, '.')

from stock_analysis.data.providers.akshare_provider import AkShareProvider
from stock_analysis.data.cleaner import DataCleaner, get_quality_summary
from stock_analysis.analysis.timeseries import TimeSeriesAnalyzer, format_timeseries_summary
from stock_analysis.analysis.indicators import IndicatorCalculator
from stock_analysis.analysis.anomaly import AnomalyDetector
from stock_analysis.analysis.order_strength import OrderStrengthAnalyzer, format_strength_summary

print("=" * 70)
print("  股票分析系统增强功能测试")
print("=" * 70)

# 1. 获取数据
print("\n[1/6] 获取测试数据...")
provider = AkShareProvider()
df = provider.get_tick_data("300661", "20260115")

if df.empty:
    print("❌ 数据获取失败")
    sys.exit(1)

print(f"✅ 成功获取 {len(df)} 条数据")

# 2. 数据清洗
print("\n[2/6] 测试数据清洗...")
cleaner = DataCleaner()
df_clean, quality_report = cleaner.clean(df)
print(get_quality_summary(quality_report))

# 3. 计算技术指标
print("\n[3/6] 测试技术指标计算...")
indicator_calc = IndicatorCalculator()
df_with_indicators = indicator_calc.calculate_all(df_clean)
ind_summary = indicator_calc.get_summary(df_with_indicators)

print(f"VWAP: ¥{ind_summary.get('vwap', 0):.2f}")
print(f"MA5: ¥{ind_summary.get('ma5', 0):.2f}")
print(f"价格 vs VWAP: {ind_summary.get('price_vs_vwap', 0):+.2f}%")

# 4. 分时走势分析
print("\n[4/6] 测试分时走势分析...")
ts_analyzer = TimeSeriesAnalyzer()
ts_result = ts_analyzer.analyze(df_with_indicators)
print(format_timeseries_summary(ts_result))

# 5. 异常检测
print("\n[5/6] 测试异常检测...")
anomaly_detector = AnomalyDetector()
anomalies = anomaly_detector.detect_all(df_with_indicators)

print(f"大单数量: {anomalies['summary']['large_order_count']}")
print(f"价格跳跃: {anomalies['summary']['price_spike_count']}")
print(f"成交量激增: {anomalies['summary']['volume_surge_count']}")
print(f"最长连涨: {anomalies['summary']['longest_rise_streak']} 分钟")

# 6. 买卖盘强度
print("\n[6/6] 测试买卖盘强度分析...")
strength_analyzer = OrderStrengthAnalyzer()
strength_result = strength_analyzer.analyze(df_with_indicators)
print(format_strength_summary(strength_result))

# 总结
print("\n" + "=" * 70)
print("  ✅ 所有功能测试通过！")
print("=" * 70)
print("\n下一步: 运行 ./启动分析系统.command 查看可视化效果")
