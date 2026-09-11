"""UI V2 会话状态 —— 异步桥 + 聊天会话系统

UI V2 之后页面状态统一走 ui_state.py（分区管理、切换不丢）；
本模块只保留两件事：
1. run_async_safe —— Streamlit 同步上下文安全运行 async 协程的桥；
2. 聊天会话系统（chat_sessions / active_session_id）。
"""

import streamlit as st
from src.utils.async_utils import run_coro_sync


def run_async_safe(coro, timeout: float = 120):
    """在 Streamlit 的同步上下文中安全运行 async 协程。

    实现见 src/utils/async_utils.run_coro_sync —— 进程级共享事件循环
    （永不 close；禁止在 loop 内再调本函数）。
    """
    return run_coro_sync(lambda: coro, timeout=timeout)


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
    _reset_chat_input()
    return sid


def _reset_chat_input() -> None:
    """切换/新建会话时清掉输入草稿与 pending，避免串会话"""
    st.session_state.pop("chat_input_v2", None)
    st.session_state.pop("_ds_pending_prompt", None)
    from src.ui import ui_state
    # last_submitted 按 sid 键控，这里无需清旧键；清空当前活跃的即可
    sid = st.session_state.get("active_session_id")
    if sid:
        ui_state.update_panel_state("chat", {f"last_submitted:{sid}": ""})


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
    _reset_chat_input()