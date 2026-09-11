"""概览面板 —— 统计卡 + 快捷入口 + 热门游戏

切换慢的主因：首次 get_doc_count 会拉 HuggingFace 向量模型，
且 DB/折扣/Steam 在线串行。现已并行 + 单源超时 + 更长 cache。
"""

import asyncio

import streamlit as st

from src.services.dashboard_service import get_dashboard_stats, get_hot_players
from src.ui import ui_state
from src.ui.session_state import run_async_safe
from src.ui.components.metric_card import render_metric_card


def normalize_stats(stats: dict) -> dict:
    """统计字典规整（缺省值补齐）"""
    return {
        "watchlist": stats.get("watchlist", 0),
        "alerts": stats.get("alerts", 0),
        "news_count": stats.get("news_count", 0),
        "best_deal": stats.get("best_deal", "-"),
    }


@st.cache_data(ttl=180, show_spinner=False)
def _load_overview(_cache_buster: int = 0) -> tuple[dict, list]:
    """统计 + 热门在线并行加载（一次桥接，避免两次 run_async_safe 叠等）"""

    async def _run():
        stats, hot = await asyncio.gather(
            get_dashboard_stats(),
            get_hot_players(),
            return_exceptions=True,
        )
        if isinstance(stats, Exception):
            from loguru import logger
            logger.warning(f"概览 stats 失败: {stats}")
            stats = {}
        if isinstance(hot, Exception):
            from loguru import logger
            logger.warning(f"概览 hot 失败: {hot}")
            hot = []
        return stats, hot

    stats, hot = run_async_safe(_run(), timeout=35)
    return normalize_stats(stats or {}), hot or []


def _open_panel(tab: str) -> None:
    ui_state.set_tab(tab)
    st.rerun()


def render_overview_panel() -> None:
    """概览：返回条 + 四统计卡 + 快捷入口四卡 + 热门在线"""
    back_col, title_col = st.columns([1, 5])
    with back_col:
        if st.button("← 返回对话", key="back_overview", use_container_width=True):
            ui_state.set_tab("chat")
            st.rerun()
    with title_col:
        st.markdown("### 🏠 概览")

    try:
        stats, hot = _load_overview()
    except Exception:
        stats, hot = normalize_stats({}), []

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_metric_card("活跃监控", str(stats["watchlist"]), "🎯")
    with c2:
        render_metric_card("待读告警", str(stats["alerts"]), "🔔")
    with c3:
        render_metric_card("新闻库", f"{stats['news_count']:,}", "📰")
    with c4:
        render_metric_card("今日最低折扣", stats["best_deal"], "💰")

    st.divider()
    st.subheader("快捷操作")
    q1, q2, q3, q4 = st.columns(4)
    with q1:
        if st.button("🔍 搜游戏", key="ov_search", use_container_width=True):
            _open_panel("search")
    with q2:
        if st.button("💰 价格监控", key="ov_price", use_container_width=True):
            _open_panel("price")
    with q3:
        if st.button("🎯 找推荐", key="ov_recommend", use_container_width=True):
            _open_panel("recommend")
    with q4:
        if st.button("📰 看新闻", key="ov_news", use_container_width=True):
            _open_panel("news")

    st.divider()
    st.subheader("热门游戏在线")
    if hot:
        for game in hot:
            st.markdown(f"- **{game['name']}** — 在线: {game['players']}")
    else:
        st.info("热门数据暂不可用")
