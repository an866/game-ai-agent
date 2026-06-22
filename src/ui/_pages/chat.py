"""AI 对话页 —— 自然语言交互"""

import streamlit as st
from src.ui.session_state import (
    init_chat_sessions, create_chat_session, get_active_messages,
    add_chat_session_message, switch_session, run_async_safe
)

st.title("AI 对话")

st.caption("支持快捷指令: `/price 游戏名` `/recommend 游戏名` `/news 关键词` `/search 游戏名`")

init_chat_sessions()

# 确保至少有一个活跃会话
if not st.session_state.get("active_session_id") or not st.session_state["chat_sessions"]:
    create_chat_session()

history = get_active_messages()

# 显示当前会话历史消息
for msg in history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("输入你的问题..."):
    add_chat_session_message("user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)

    placeholder = st.empty()
    placeholder.info(":hourglass: 思考中，请稍候...")

    try:
        from src.agents.graph import chat
        response = run_async_safe(chat(prompt, history[:-1] if len(history) > 1 else None))
    except Exception as e:
        response = f"出错了: {str(e)}"

    placeholder.empty()
    with st.chat_message("assistant"):
        st.markdown(response)
    add_chat_session_message("assistant", response)

# ---------- 侧边栏：对话历史 ----------

with st.sidebar:
    st.subheader("对话历史")

    if st.button("+ 新对话", use_container_width=True):
        create_chat_session()
        st.rerun()

    st.divider()

    sessions = st.session_state.get("chat_sessions", {})
    active = st.session_state.get("active_session_id")

    for sid in list(sessions.keys()):
        session = sessions[sid]
        is_active = sid == active
        prefix = "▸ " if is_active else "  "
        title = session.get("title", "未命名对话")
        msg_count = len(session.get("messages", []))

        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(
                f"{prefix}{title} ({msg_count // 2}轮)",
                key=f"sess_{sid}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                switch_session(sid)
                st.rerun()
        with col2:
            if not is_active and st.button("🗑", key=f"del_{sid}", help="删除此对话"):
                del sessions[sid]
                if sid == active:
                    st.session_state["active_session_id"] = next(iter(sessions)) if sessions else None
                st.rerun()
