"""游戏新闻页"""

import asyncio
import streamlit as st

st.title("游戏新闻")

# 搜索栏
news_query = st.text_input("搜索新闻", placeholder="输入关键词或自然语言查询...")

col1, col2, col3 = st.columns(3)
with col1:
    game_filter = st.selectbox("游戏筛选", ["全部", "原神", "鸣潮", "Steam", "独立游戏"])
with col2:
    source_filter = st.selectbox("来源筛选", ["全部", "HoYoLAB", "Steam", "游民星空", "3DM", "机核", "IGN", "PC Gamer"])
with col3:
    days_filter = st.selectbox("时间范围", ["最近 3 天", "最近 7 天", "最近 30 天", "全部"])

if st.button("搜索"):
    with st.spinner("检索新闻中..."):
        try:
            from src.rag.retriever import search_news

            gf = None if game_filter == "全部" else game_filter
            sf = None if source_filter == "全部" else source_filter

            docs = asyncio.run(search_news(
                news_query or "最新游戏新闻",
                k=10,
                game_filter=gf,
                source_filter=sf,
            ))

            st.subheader(f"找到 {len(docs)} 条相关新闻")
            for doc in docs:
                meta = doc.metadata
                with st.container(border=True):
                    st.markdown(f"#### {meta.get('title', '无标题')}")
                    st.caption(
                        f"来源: {meta.get('source_name', '未知')} | "
                        f"日期: {meta.get('published_date', '未知')} | "
                        f"语言: {meta.get('language', '未知')}"
                    )
                    st.markdown(doc.page_content[:300] + ("..." if len(doc.page_content) > 300 else ""))
                    if meta.get("source_url"):
                        st.link_button("阅读原文", meta["source_url"])
        except Exception as e:
            st.error(f"检索失败: {e}")

# 默认展示最新新闻
if not news_query:
    st.divider()
    st.subheader("最新资讯")

    try:
        from src.tools.rss_feed import RSSFetchAllTool

        if st.button("刷新新闻"):
            st.cache_data.clear()

        @st.cache_data(ttl=1800)
        def load_rss():
            tool = RSSFetchAllTool()
            return asyncio.run(tool._arun())

        articles = load_rss()
        for article in articles[:15]:
            with st.container(border=True):
                st.markdown(f"**{article.get('title', '无标题')}**")
                st.caption(
                    f"来源: {article.get('source_name', article.get('source', '未知'))} | "
                    f"{article.get('published', '未知')}"
                )
                if article.get("summary"):
                    st.markdown(article["summary"][:200])
                if article.get("link"):
                    st.link_button("阅读原文", article["link"])
    except Exception:
        st.info("新闻加载功能需要配置 API 后再使用")
