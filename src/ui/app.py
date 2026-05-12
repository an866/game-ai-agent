"""Streamlit 多页应用入口"""

import streamlit as st
from src.ui.session_state import init_session_state

st.set_page_config(
    page_title="游戏 AI 助手",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session_state()

pages = [
    st.Page("src/ui/pages/home.py", title="首页", icon=""),
    st.Page("src/ui/pages/chat.py", title="AI 对话", icon=""),
    st.Page("src/ui/pages/search.py", title="游戏搜索", icon=""),
    st.Page("src/ui/pages/price_watch.py", title="价格监控", icon=""),
    st.Page("src/ui/pages/recommend.py", title="游戏推荐", icon=""),
    st.Page("src/ui/pages/news.py", title="游戏新闻", icon=""),
]

pg = st.navigation(pages, position="sidebar", expanded=True)
pg.run()
