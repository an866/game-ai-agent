"""Streamlit 多页应用入口"""

import streamlit as st
from src.ui.session_state import init_session_state, init_chat_sessions

st.set_page_config(
    page_title="游戏 AI 助手",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session_state()
init_chat_sessions()

pg = st.navigation(
    [
        st.Page("_pages/home.py", title="首页", icon="🏠", url_path="home"),
        st.Page("_pages/chat.py", title="AI 对话", icon="💬", url_path="chat"),
        st.Page("_pages/search.py", title="游戏搜索", icon="🔍", url_path="search"),
        st.Page("_pages/price_watch.py", title="价格监控", icon="💰", url_path="price_watch"),
        st.Page("_pages/recommend.py", title="游戏推荐", icon="🎯", url_path="recommend"),
        st.Page("_pages/news.py", title="游戏新闻", icon="📰", url_path="news"),
    ],
    position="sidebar",
    expanded=True,
)
pg.run()
