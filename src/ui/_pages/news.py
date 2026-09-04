"""游戏新闻页"""

import streamlit as st
from loguru import logger
from src.ui.session_state import run_async_safe
from src.ui.components._loading import show_loading
from src.ui.components._error import show_error
from src.ui.components.rss_card import render_news_doc, render_rss_article

st.title("游戏新闻")

tab1, tab2 = st.tabs(["新闻搜索", "最新资讯"])

with tab1:
    st.subheader("搜索新闻")

    col1, col2, col3 = st.columns(3)
    with col1:
        game_filter = st.selectbox("游戏筛选", ["全部", "原神", "鸣潮", "Steam", "独立游戏"])
    with col2:
        source_filter = st.selectbox("来源筛选", ["全部", "HoYoLAB", "Steam", "游民星空", "3DM", "机核", "IGN", "PC Gamer"])
    with col3:
        days_filter = st.selectbox("时间范围", ["全部", "最近 3 天", "最近 7 天", "最近 30 天"], index=2)

    news_query = st.text_input("搜索关键词", placeholder="输入关键词或自然语言查询...")

    if news_query and st.button("搜索新闻", type="primary"):
        with show_error("检索失败"):
            with show_loading("检索中..."):
                from src.rag.retriever import search_news

                gf = None if game_filter == "全部" else game_filter
                sf = None if source_filter == "全部" else source_filter
                df_map = {"全部": None, "最近 3 天": 3, "最近 7 天": 7, "最近 30 天": 30}
                df = df_map.get(days_filter)

                docs = run_async_safe(search_news(
                    news_query,
                    k=10,
                    source_filter=sf,
                    game_filter=gf,
                    days_filter=df,
                ))

                if docs:
                    st.subheader(f"找到 {len(docs)} 条相关新闻")
                    for doc in docs:
                        render_news_doc(doc)
                else:
                    st.info("未找到相关新闻，尝试修改搜索条件")
    elif not news_query:
        st.info("输入关键词后点击搜索")

with tab2:
    st.subheader("最新资讯")

    @st.cache_data(ttl=1800, show_spinner=False)
    def load_rss():
        try:
            from src.tools.rss_feed import RSSFetchAllTool
            tool = RSSFetchAllTool()
            return run_async_safe(tool._arun())
        except Exception as exc:
            logger.warning(f"RSS 加载失败: {exc}")
            return None

    if st.button("刷新新闻"):
        st.cache_data.clear()
        st.rerun()

    articles = load_rss()
    if articles is None:
        st.info("RSS 新闻源暂不可用，请稍后重试")
    elif articles:
        for article in articles[:15]:
            render_rss_article(article)
    else:
        st.info("暂无最新资讯")
