"""RSS / 新闻卡片组件"""

import streamlit as st


def render_news_doc(doc) -> None:
    """RAG 检索结果卡片（标题/来源/日期/摘要 + 原文链接）"""
    meta = doc.metadata
    with st.container(border=True):
        st.markdown(f"#### {meta.get('title', '无标题')}")
        st.caption(
            f"来源: {meta.get('source_name', '未知')} | "
            f"日期: {meta.get('published_date', '未知')} | "
            f"语言: {meta.get('language', '未知')}"
        )
        content = doc.page_content
        st.markdown(content[:300] + ("..." if len(content) > 300 else ""))
        if meta.get("source_url"):
            st.link_button("阅读原文", meta["source_url"])


def render_rss_article(article: dict) -> None:
    """RSS 文章卡片（标题/来源/摘要 + 原文链接）"""
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