"""价格监控页"""

import asyncio
import streamlit as st
import pandas as pd

st.title("价格监控")

tab1, tab2, tab3 = st.tabs(["添加监控", "监控列表", "告警历史"])

with tab1:
    st.subheader("添加价格监控")
    with st.form("add_watchlist"):
        game_name = st.text_input("游戏名称", placeholder="输入 Steam 游戏完整名称")
        target_price = st.number_input("目标价格 (人民币)", min_value=0.0, step=10.0, format="%.2f")
        submitted = st.form_submit_button("添加监控", type="primary")
        if submitted and game_name:
            try:
                from src.data.database import async_session_factory
                from src.data.repository import WatchlistRepository

                async def add():
                    async with async_session_factory() as session:
                        repo = WatchlistRepository(session)
                        await repo.add(game_name=game_name, target_price=target_price)
                        return True

                asyncio.run(add())
                st.success(f"已添加监控: {game_name} @ ¥{target_price:.2f}")
                st.session_state["watchlist_cache"] = None  # 刷新缓存
            except Exception as e:
                st.error(f"添加失败: {e}")

with tab2:
    st.subheader("当前监控")
    try:
        from src.data.database import async_session_factory
        from src.data.repository import WatchlistRepository

        async def load():
            async with async_session_factory() as session:
                repo = WatchlistRepository(session)
                return await repo.get_all_active()

        if st.button("刷新列表"):
            st.session_state["watchlist_cache"] = None
            st.rerun()

        if st.session_state.get("watchlist_cache") is None:
            with st.spinner("加载中..."):
                st.session_state["watchlist_cache"] = asyncio.run(load())

        items = st.session_state.get("watchlist_cache", [])
        if items:
            df = pd.DataFrame([
                {
                    "游戏": item.game_name,
                    "目标价": f"¥{float(item.target_price):.2f}",
                    "状态": item.status,
                    "创建时间": str(item.created_at)[:19],
                }
                for item in items
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("暂无监控项目")
    except Exception as e:
        st.error(f"加载失败: {e}")

with tab3:
    st.subheader("告警记录")
    try:
        from src.data.database import async_session_factory
        from src.data.repository import PriceAlertRepository

        async def load_alerts():
            async with async_session_factory() as session:
                repo = PriceAlertRepository(session)
                return await repo.get_unread(20)

        if st.button("刷新告警"):
            st.session_state["price_alerts_cache"] = None
            st.rerun()

        if st.session_state.get("price_alerts_cache") is None:
            with st.spinner("加载中..."):
                st.session_state["price_alerts_cache"] = asyncio.run(load_alerts())

        alerts = st.session_state.get("price_alerts_cache", [])
        if alerts:
            df = pd.DataFrame([
                {
                    "当前价": f"¥{float(a.current_price):.2f}",
                    "目标价": f"¥{float(a.target_price):.2f}",
                    "商店": a.store_name,
                    "触发时间": str(a.triggered_at)[:19],
                }
                for a in alerts
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("暂无未读告警")
    except Exception as e:
        st.error(f"加载失败: {e}")
