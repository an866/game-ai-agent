"""RSS / 新闻卡片组件（V2：变量化）"""

import streamlit as st


def render_news_doc(doc) -> None:
    """RAG 检索结果卡片"""
    meta = doc.metadata
    st.markdown(
        f"""<div style="background: var(--panel); border: 1px solid var(--border);
                    border-radius: var(--radius); padding: 12px 14px; margin-bottom: 10px;">
          <div style="color: var(--text); font-weight: 600;">{meta.get('title', '无标题')}</div>
          <div style="color: var(--text-dim); font-size: 12px;">来源: {meta.get('source_name', '未知')} | 日期: {meta.get('published_date', '未知')} | 语言: {meta.get('language', '未知')}</div>
          <div style="color: var(--text); font-size: 13px; margin-top: 6px;">{doc.page_content[:300]}{'...' if len(doc.page_content) > 300 else ''}</div>
        </div>""",
        unsafe_allow_html=True,
    )
    if meta.get("source_url"):
        st.link_button("阅读原文", meta["source_url"])


def render_rss_article(article: dict) -> None:
    """RSS 文章卡片"""
    st.markdown(
        f"""<div style="background: var(--panel); border: 1px solid var(--border);
                    border-radius: var(--radius); padding: 12px 14px; margin-bottom: 10px;">
          <div style="color: var(--text); font-weight: 600;">{article.get('title', '无标题')}</div>
          <div style="color: var(--text-dim); font-size: 12px;">来源: {article.get('source_name', article.get('source', '未知'))} | {article.get('published', '未知')}</div>
          {('<div style="color: var(--text); font-size: 13px; margin-top: 6px;">' + article['summary'][:200] + '</div>') if article.get('summary') else ''}
        </div>""",
        unsafe_allow_html=True,
    )
    if article.get("link"):
        st.link_button("阅读原文", article["link"])