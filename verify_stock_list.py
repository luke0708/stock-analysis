import akshare as ak
import time

print("开始获取A股列表...")
start = time.time()
try:
    df = ak.stock_zh_a_spot_em()
    print(f"获取成功！耗时: {time.time() - start:.2f}秒")
    print(f"总数量: {len(df)}")
    print("列名:", df.columns.tolist())
    print("前5行预览:")
    print(df[['代码', '名称']].head())
except Exception as e:
    print(f"获取失败: {e}")
