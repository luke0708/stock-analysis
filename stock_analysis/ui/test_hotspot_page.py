"""简化版市场热点页面 - 用于快速测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd

st.set_page_config(page_title="市场热点(简化版)", layout="wide", page_icon="🔥")

st.title("🔥 市场热点（简化测试版）")
st.caption("如果看到这个页面，说明Streamlit运行正常")

st.success("✅ 页面加载成功！")

# 测试导入
try:
    from stock_analysis.analysis.market_hotspot import MarketHotspotAnalyzer
    st.success("✅ market_hotspot 模块导入成功")
    
    # 测试获取数据
    with st.spinner("测试获取板块数据..."):
        hotspot = MarketHotspotAnalyzer()
        concepts = hotspot.get_hot_concepts(top_n=5)
        
        if not concepts.empty:
            st.success(f"✅ 成功获取 {len(concepts)} 个热门概念")
            st.dataframe(concepts[['板块名称', '涨跌幅', '领涨股票']])
        else:
            st.warning("数据为空")
            
except Exception as e:
    st.error(f"❌ 错误: {e}")
    import traceback
    st.code(traceback.format_exc())

st.info("如果以上测试都通过，可以使用完整版market_hotspot_page.py")
