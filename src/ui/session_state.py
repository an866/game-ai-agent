"""Streamlit 跨页面会话状态管理"""

import asyncio
import concurrent.futures
import streamlit as st


def run_async_safe(coro):
    """在 Streamlit 的同步上下文中安全运行 async 协程。

    在独立线程中创建新事件循环执行，不调用 loop.close()
    以避免触发 SQLAlchemy 连接池清理时的事件循环已关闭错误。
    事件循环在进程退出时由 OS 回收。
    """
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
        # NOTE: 不调用 loop.close() — SQLAlchemy 异步引擎在析构时
        # 会尝试清理连接池，需要事件循环仍然存活。

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run).result()


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


def init_chat_sessions():
    """初始化对话会话列表（支持多轮对话管理）"""
    if "chat_sessions" not in st.session_state:
        st.session_state["chat_sessions"] = {}
    if "active_session_id" not in st.session_state:
        st.session_state["active_session_id"] = None


def create_chat_session() -> str:
    """创建新对话会话，返回 session_id"""
    import uuid
    sid = str(uuid.uuid4())[:8]
    st.session_state["chat_sessions"][sid] = {
        "title": "新对话",
        "messages": [],
        "summary": None,
    }
    st.session_state["active_session_id"] = sid
    return sid


def get_active_messages() -> list[dict]:
    """获取当前活跃会话的消息列表"""
    init_chat_sessions()
    sid = st.session_state.get("active_session_id")
    if sid and sid in st.session_state["chat_sessions"]:
        return st.session_state["chat_sessions"][sid]["messages"]
    return []


def add_chat_session_message(role: str, content: str):
    """向当前活跃会话添加消息"""
    messages = get_active_messages()
    if role == "user" and not messages:
        sid = st.session_state["active_session_id"]
        st.session_state["chat_sessions"][sid]["title"] = content[:30]
    messages.append({"role": role, "content": content})


def switch_session(sid: str):
    """切换到指定会话"""
    st.session_state["active_session_id"] = sid
