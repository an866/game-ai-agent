"""首页 —— 仪表盘概览"""

import streamlit as st
from src.ui.session_state import run_async_safe
from src.services.dashboard_service import get_dashboard_stats, get_hot_players


@st.cache_data(ttl=120, show_spinner=False)
def load_stats(_cache_buster: int = 0) -> dict:
    """加载首页仪表盘统计数据（缓存 120 秒）"""
    return run_async_safe(get_dashboard_stats())


@st.cache_data(ttl=300, show_spinner=False)
def load_hot_games(_cache_buster: int = 0) -> list[dict]:
    """加载热门游戏实时在线人数（缓存 5 分钟）"""
    return run_async_safe(get_hot_players())


st.title("游戏 AI 助手")
st.markdown("PC 游戏信息查询 | 价格追踪 | 新闻聚合 | 智能推荐")

stats = load_stats()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(label="活跃监控", value=stats["watchlist"])
with col2:
    st.metric(label="待读告警", value=stats["alerts"])
with col3:
    st.metric(label="新闻库", value=stats.get("news_count", 0), help="已索引的新闻文档数")
with col4:
    st.metric(label="今日最低折扣", value=stats.get("best_deal", "-"))

st.divider()

st.subheader("快捷操作")

quick_col1, quick_col2, quick_col3, quick_col4 = st.columns(4)

with quick_col1:
    if st.button("查游戏信息", use_container_width=True):
        st.switch_page("search")

with quick_col2:
    if st.button("看最新折扣", use_container_width=True):
        st.switch_page("price_watch")

with quick_col3:
    if st.button("找类似游戏", use_container_width=True):
        st.switch_page("recommend")

with quick_col4:
    if st.button("看游戏新闻", use_container_width=True):
        st.switch_page("news")

st.divider()

st.subheader("热门游戏")

hot_games = load_hot_games()
for game in hot_games:
    st.markdown(f"- **{game['name']}** — 在线: {game['players']}")