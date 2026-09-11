"""游戏新闻面板 —— 双 Tab：语义检索 + 最新 RSS（迁移自 _pages/news.py）"""

import streamlit as st
from loguru import logger

from src.ui import ui_state
from src.ui.session_state import run_async_safe
from src.ui.components._loading import show_loading
from src.ui.components._error import show_error
from src.ui.components.rss_card import render_news_doc, render_rss_article

GAME_FILTERS = ["全部", "原神", "鸣潮", "Steam", "独立游戏"]
SOURCE_FILTERS = ["全部", "HoYoLAB", "Steam", "游民星空", "3DM", "机核", "IGN", "PC Gamer"]
DAYS_MAP = {"全部": None, "最近 3 天": 3, "最近 7 天": 7, "最近 30 天": 30}


def normalize_filters(game: str, source: str, days: str) -> dict:
    return {
        "game": None if game == "全部" else game,
        "source": None if source == "全部" else source,
        "days": DAYS_MAP.get(days),
    }


@st.cache_data(ttl=1800, show_spinner=False)
def _load_rss() -> list | None:
    try:
        from src.tools.rss_feed import RSSFetchAllTool
        return run_async_safe(RSSFetchAllTool()._arun())
    except Exception as exc:
        logger.warning(f"RSS 加载失败: {exc}")
        return None


def render_news_panel() -> None:
    """新闻面板：搜索 + 最新资讯双 Tab"""
    st.markdown("### 游戏新闻")
    if st.button("← 返回对话", key="back_news", use_container_width=True):
        ui_state.set_tab("chat")
        st.rerun()

    tab1, tab2 = st.tabs(["🔍 新闻搜索", "📰 最新资讯"])

    with tab1:
        state = ui_state.get_panel_state("news")
        col1, col2, col3 = st.columns(3)
        with col1:
            game_filter = st.selectbox("游戏筛选", GAME_FILTERS)
        with col2:
            source_filter = st.selectbox("来源筛选", SOURCE_FILTERS)
        with col3:
            days_filter = st.selectbox("时间范围", list(DAYS_MAP.keys()), index=2)

        news_query = st.text_input("搜索关键词", placeholder="输入关键词或自然语言查询...")
        if news_query and st.button("搜索新闻", type="primary"):
            with show_error("检索失败"):
                with show_loading("检索中..."):
                    import asyncio
                    from src.rag.retriever import search_news
                    f = normalize_filters(game_filter, source_filter, days_filter)

                    async def _search():
                        return await asyncio.wait_for(
                            search_news(news_query, k=10,
                                        source_filter=f["source"],
                                        game_filter=f["game"],
                                        days_filter=f["days"]),
                            timeout=12.0,
                        )

                    try:
                        docs = run_async_safe(_search(), timeout=20)
                    except Exception as exc:
                        logger.warning(f"新闻语义检索失败: {exc}")
                        docs = []
                    state = {**state, "docs": docs, "query": news_query}
                    ui_state.set_panel_state("news", state)
                    st.rerun()

        docs = state.get("docs")
        if docs:
            st.subheader(f"找到 {len(docs)} 条相关新闻")
            for doc in docs:
                render_news_doc(doc)
        elif state.get("query") and not news_query:
            st.info("未找到相关新闻，尝试修改搜索条件")

    with tab2:
        if st.button("刷新新闻"):
            _load_rss.clear()
            st.rerun()
        articles = _load_rss()
        if articles is None:
            st.info("RSS 新闻源暂不可用，请稍后重试")
        elif articles:
            for article in articles[:15]:
                render_rss_article(article)
        else:
            st.info("暂无最新资讯")