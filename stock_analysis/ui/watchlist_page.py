"""
自选股页面
管理用户关注的股票列表
"""
import streamlit as st
import pandas as pd
from stock_analysis.core.storage import StorageManager
from stock_analysis.data.stock_list import get_stock_provider

def show_watchlist_page():
    st.header("📋 我的自选股")
    
    storage = StorageManager()
    watchlist = storage.load_watchlist()
    
    if not watchlist:
        st.info("👋 您还没有添加自选股")
        st.markdown("在 **个股分析** 页面搜索股票并点击 '❤️ 加入自选' 即可添加")
        return

    # 转换为DataFrame展示
    df = pd.DataFrame(watchlist)
    
    # 获取最新行情 (可选，这里先简单展示列表)
    # 若要展示行情，需调用 akshare 批量获取，或者遍历获取
    
    # 简易表格展示
    st.markdown("### 已关注股票")
    
    # 使用列布局显示，每行一个股票，带操作按钮
    for i, stock in enumerate(watchlist):
        col1, col2, col3, col4 = st.columns([2, 4, 3, 2])
        
        with col1:
            st.markdown(f"**{stock['code']}**")
        with col2:
            st.text(stock['name'])
        with col3:
            st.caption(stock.get('added_at', '')[:10])
        with col4:
            if st.button("🗑️", key=f"del_{stock['code']}"):
                storage.remove_from_watchlist(stock['code'])
                st.success(f"已移除 {stock['name']}")
                st.rerun()
                
    st.markdown("---")
    
    # 导出导入功能 (解决云端存储问题)
    with st.expander("💾 数据备份与恢复 (云端/本地)"):
        st.caption("如果您在 Streamlit Cloud 使用，请定期备份数据，因为重启会丢失本地文件。")
        
        # 导出
        import json
        json_str = json.dumps({'stocks': watchlist}, ensure_ascii=False, indent=2)
        st.download_button(
            label="📤 导出自选股 (JSON)",
            data=json_str,
            file_name="my_watchlist.json",
            mime="application/json"
        )
        
        # 导入
        uploaded_file = st.file_uploader("📥 导入自选股 (JSON)", type=['json'])
        if uploaded_file is not None:
            try:
                data = json.load(uploaded_file)
                if 'stocks' in data:
                    storage.save_watchlist(data['stocks'])
                    st.success("✅ 导入成功！")
                    st.rerun()
            except Exception as e:
                st.error(f"导入失败: {e}")
