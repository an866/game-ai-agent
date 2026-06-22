"""首页 —— 仪表盘概览"""

import streamlit as st
from src.ui.session_state import run_async_safe
from src.data.database import async_session_factory
from src.data.repository import WatchlistRepository, PriceAlertRepository


@st.cache_data(ttl=60, show_spinner=False)
def load_stats():
    """加载首页统计数据"""
    async def _load():
        async with async_session_factory() as session:
            watchlist_count = await WatchlistRepository(session).get_count()
            alerts_count = await PriceAlertRepository(session).get_count_unread()
            return {"watchlist": watchlist_count, "alerts": alerts_count}

    return run_async_safe(_load())


st.title("游戏 AI 助手")
st.markdown("PC 游戏信息查询 | 价格追踪 | 新闻聚合 | 智能推荐")

stats = load_stats()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(label="活跃监控", value=stats["watchlist"])
with col2:
    st.metric(label="待读告警", value=stats["alerts"])
with col3:
    st.metric(label="新闻库", value="-")
with col4:
    st.metric(label="今日最低折扣", value="-")

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

hot_games = [
    {"name": "Counter-Strike 2", "players": "1,500,000+", "appid": 730},
    {"name": "Dota 2", "players": "600,000+", "appid": 570},
    {"name": "PUBG: BATTLEGROUNDS", "players": "400,000+", "appid": 578080},
    {"name": "Apex Legends", "players": "250,000+", "appid": 1172470},
    {"name": "原神", "players": "网游", "appid": None},
]

for game in hot_games:
    st.markdown(f"- **{game['name']}** — 在线: {game['players']}")
