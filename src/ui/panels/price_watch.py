"""价格监控面板 —— 添加/列表/告警三 Tab（迁移自 _pages/price_watch.py）"""

import pandas as pd
import streamlit as st

from src.services.watchlist_service import (
    add_watch, list_watches, delete_watch, list_unread_alerts, mark_all_alerts_read,
)
from src.ui import ui_state
from src.ui.session_state import run_async_safe


@st.cache_data(ttl=5, show_spinner=False)
def _load_watchlist(_cache_buster: int = 0) -> list[dict]:
    """加载活跃监控列表（service 失败时返回 []，不会抛）"""
    return run_async_safe(list_watches())


@st.cache_data(ttl=5, show_spinner=False)
def _load_alerts(_cache_buster: int = 0) -> list[dict]:
    """加载未读告警"""
    return run_async_safe(list_unread_alerts())


def watch_rows_to_dicts(rows: list[dict]) -> list[dict]:
    """规整监控行（测试辅助）"""
    return [
        {
            "id": r["id"],
            "game_name": r["game_name"],
            "target_price": float(r["target_price"]),
            "status": r["status"],
            "created_at": r.get("created_at", "-"),
        }
        for r in rows
    ]


def render_price_panel() -> None:
    """价格监控面板：三 Tab（添加监控 / 监控列表 / 告警历史）"""
    st.markdown("### 价格监控")
    if st.button("← 返回对话", key="back_price", use_container_width=True):
        ui_state.set_tab("chat")
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["➕ 添加监控", "📋 监控列表", "🔔 告警历史"])

    with tab1:
        with st.form("add_watchlist"):
            game_name = st.text_input("游戏名称", placeholder="输入 Steam 游戏完整名称")
            target_price = st.number_input("目标价格 (人民币)", min_value=0.0,
                                           step=10.0, format="%.2f")
            submitted = st.form_submit_button("添加监控", type="primary")
            if submitted and game_name:
                ok = run_async_safe(add_watch(game_name, target_price))
                if ok:
                    st.success(f"已添加监控: {game_name} @ ¥{target_price:.2f}")
                    _load_watchlist.clear()
                else:
                    st.error("添加失败，请检查数据库连接或日志")

    with tab2:
        col_btn1, col_btn2 = st.columns([1, 5])
        with col_btn1:
            if st.button("刷新", key="refresh_watchlist"):
                _load_watchlist.clear()
        items = watch_rows_to_dicts(_load_watchlist())
        if items:
            for item in items:
                col1, col2, col3, col4, col5 = st.columns([3, 2, 1.5, 1.5, 1])
                with col1:
                    st.markdown(f"**{item['game_name']}**")
                with col2:
                    st.markdown(f"目标价 <span style='color:var(--ok);'>¥{item['target_price']:.2f}</span>",
                                unsafe_allow_html=True)
                with col3:
                    label = "活跃" if item["status"] == "active" else item["status"]
                    st.caption(f"状态: {label}")
                with col4:
                    st.caption(item["created_at"])
                with col5:
                    delete_key = f"confirm_del_{item['id']}"
                    if delete_key not in st.session_state:
                        st.session_state[delete_key] = False
                    if st.button("删除", key=f"btn_{item['id']}"):
                        st.session_state[delete_key] = True
                    if st.session_state.get(delete_key):
                        # 对话框是 fragment，事件触发在循环结束后——必须用默认参数按值绑定
                        # (直接闭包循环变量会删到最后一行，AppTest 无法覆盖此类缺陷)
                        @st.dialog("确认删除")
                        def confirm_del(item=item, delete_key=delete_key):
                            st.warning(f"确定要移除 **{item['game_name']}** 的监控吗？")
                            c1, c2 = st.columns(2)
                            with c1:
                                if st.button("确认删除", type="primary", use_container_width=True):
                                    ok = run_async_safe(delete_watch(item["id"]))
                                    if ok:
                                        _load_watchlist.clear()
                                        st.session_state[delete_key] = False
                                        st.rerun()
                                    else:
                                        st.error("删除失败，请查看日志")
                            with c2:
                                if st.button("取消", use_container_width=True):
                                    st.session_state[delete_key] = False
                                    st.rerun()
                        confirm_del()
                st.divider()
        else:
            st.info("暂无监控项目")

    with tab3:
        col_btn1, col_btn2 = st.columns([1, 5])
        with col_btn1:
            if st.button("刷新", key="refresh_alerts"):
                _load_alerts.clear()
        with col_btn2:
            if st.button("全部已读", key="mark_all_read"):
                run_async_safe(mark_all_alerts_read())
                _load_alerts.clear()
                st.rerun()
        alerts = _load_alerts()
        if alerts:
            df = pd.DataFrame(alerts)
            df.columns = ["当前价 ¥", "目标价 ¥", "商店", "触发时间"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("暂无未读告警")