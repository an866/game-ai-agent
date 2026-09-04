"""价格监控页"""

import streamlit as st
import pandas as pd
from src.ui.session_state import run_async_safe

st.title("价格监控")

# ---- 数据库操作（缓存） ----

@st.cache_data(ttl=5, show_spinner=False)
def _load_watchlist(_cache_buster: int = 0) -> list:
    """加载活跃监控列表"""
    from src.deps import get_session_factory
    from src.data.repository import WatchlistRepository

    async def _run():
        async with get_session_factory()() as session:
            items = await WatchlistRepository(session).get_all_active()
            return [
                {
                    "id": item.id,
                    "game_name": item.game_name,
                    "target_price": float(item.target_price),
                    "status": item.status,
                    "created_at": str(item.created_at)[:10] if item.created_at else "-",
                }
                for item in items
            ]
    return run_async_safe(_run())


@st.cache_data(ttl=5, show_spinner=False)
def _load_alerts(_cache_buster: int = 0) -> list:
    """加载未读告警"""
    from src.deps import get_session_factory
    from src.data.repository import PriceAlertRepository

    async def _run():
        async with get_session_factory()() as session:
            items = await PriceAlertRepository(session).get_unread(20)
            return [
                {
                    "current_price": float(a.current_price),
                    "target_price": float(a.target_price),
                    "store_name": a.store_name,
                    "triggered_at": str(a.triggered_at)[:19] if a.triggered_at else "-",
                }
                for a in items
            ]
    return run_async_safe(_run())


# ---- UI ----

tab1, tab2, tab3 = st.tabs(["添加监控", "监控列表", "告警历史"])

with tab1:
    st.subheader("添加价格监控")
    with st.form("add_watchlist"):
        game_name = st.text_input("游戏名称", placeholder="输入 Steam 游戏完整名称")
        target_price = st.number_input("目标价格 (人民币)", min_value=0.0, step=10.0, format="%.2f")
        submitted = st.form_submit_button("添加监控", type="primary")
        if submitted and game_name:
            try:
                from src.deps import get_session_factory
                from src.data.repository import WatchlistRepository

                async def add():
                    async with get_session_factory()() as session:
                        repo = WatchlistRepository(session)
                        await repo.add(game_name=game_name, target_price=target_price)

                run_async_safe(add())
                st.success(f"已添加监控: {game_name} @ ¥{target_price:.2f}")
                _load_watchlist.clear()
            except Exception as e:
                st.error(f"添加失败: {e}")

with tab2:
    st.subheader("当前监控")
    try:
        from src.deps import get_session_factory
        from src.data.repository import WatchlistRepository

        async def delete_item(watchlist_id: int):
            async with get_session_factory()() as session:
                repo = WatchlistRepository(session)
                await repo.delete(watchlist_id)

        col_btn1, col_btn2 = st.columns([1, 5])
        with col_btn1:
            if st.button("刷新", key="refresh_watchlist"):
                _load_watchlist.clear()

        items = _load_watchlist()
        if items:
            for item in items:
                col1, col2, col3, col4, col5 = st.columns([3, 2, 1.5, 1.5, 1])
                with col1:
                    st.markdown(f"**{item['game_name']}**")
                with col2:
                    st.caption(f"目标价 ¥{item['target_price']:.2f}")
                with col3:
                    status_label = "活跃" if item['status'] == "active" else item['status']
                    st.caption(f"状态: {status_label}")
                with col4:
                    st.caption(item['created_at'])
                with col5:
                    delete_key = f"confirm_del_{item['id']}"
                    if delete_key not in st.session_state:
                        st.session_state[delete_key] = False

                    if st.button("删除", key=f"btn_{item['id']}"):
                        st.session_state[delete_key] = True

                    if st.session_state.get(delete_key):
                        @st.dialog(f"确认删除")
                        def confirm_del():
                            st.warning(f"确定要移除 **{item['game_name']}** 的监控吗？")
                            c1, c2 = st.columns(2)
                            with c1:
                                if st.button("确认删除", type="primary", use_container_width=True):
                                    run_async_safe(delete_item(item['id']))
                                    _load_watchlist.clear()
                                    st.session_state[delete_key] = False
                                    st.rerun()
                            with c2:
                                if st.button("取消", use_container_width=True):
                                    st.session_state[delete_key] = False
                                    st.rerun()
                        confirm_del()
                st.divider()
        else:
            st.info("暂无监控项目")
    except Exception as e:
        st.error(f"加载失败: {e}")

with tab3:
    st.subheader("告警记录")

    async def _mark_all_read():
        from src.data.repository import PriceAlertRepository
        async with get_session_factory()() as session:
            return await PriceAlertRepository(session).mark_all_read()

    try:
        col_btn1, col_btn2 = st.columns([1, 5])
        with col_btn1:
            if st.button("刷新", key="refresh_alerts"):
                _load_alerts.clear()
        with col_btn2:
            if st.button("全部已读", key="mark_all_read"):
                run_async_safe(_mark_all_read())
                _load_alerts.clear()
                st.rerun()

        alerts = _load_alerts()
        if alerts:
            df = pd.DataFrame(alerts)
            df.columns = ["当前价 ¥", "目标价 ¥", "商店", "触发时间"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("暂无未读告警")
    except Exception as e:
        st.error(f"加载失败: {e}")
