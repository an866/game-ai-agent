"""Streamlit 跨页面会话状态管理"""

import streamlit as st


def init_session_state():
    """初始化共享会话状态"""
    defaults = {
        "chat_messages": [],
        "watchlist_cache": None,
        "price_alerts_cache": None,
        "search_results": None,
        "recommend_results": None,
        "agent_graph": None,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


def get_chat_history() -> list[dict]:
    """获取对话历史列表（用于展示历史记录）"""
    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []
    return st.session_state["chat_messages"]


def add_chat_message(role: str, content: str):
    """添加一条对话消息"""
    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []
    st.session_state["chat_messages"].append({"role": role, "content": content})
