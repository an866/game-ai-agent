"""AI 对话页 —— 自然语言交互（流式输出）"""

import streamlit as st
from src.ui.session_state import (
    init_chat_sessions, create_chat_session, get_active_messages,
    add_chat_session_message, switch_session,
)

# ── 记忆持久化辅助函数 ──

def _after_message(sid: str, role: str, content: str):
    """消息添加后的持久化 + 压缩检查"""
    from src.agents.memory import ConversationMemory
    from src.ui.session_state import run_async_safe
    mem = ConversationMemory()
    run_async_safe(mem.save_message(sid, role, content))
    sessions = st.session_state["chat_sessions"]
    current_msgs = sessions[sid]["messages"]
    if mem.should_compress(len(current_msgs)):
        existing = sessions[sid].get("summary")
        compacted, new_summary = run_async_safe(
            mem.compress(current_msgs, existing_summary=existing)
        )
        sessions[sid]["messages"] = compacted
        sessions[sid]["summary"] = new_summary
        # ── 画像提取 ──
        if new_summary:
            profile = run_async_safe(mem.extract_profile(new_summary))
            if profile and any(profile.values()):
                run_async_safe(mem.save_profile(sid, profile))


st.title("AI 对话")

st.caption("支持快捷指令: `/price 游戏名` `/recommend 游戏名` `/news 关键词` `/search 游戏名`")

init_chat_sessions()

# 确保至少有一个活跃会话
if not st.session_state.get("active_session_id") or not st.session_state["chat_sessions"]:
    create_chat_session()

history = get_active_messages()

# ── 页面首次加载时从 DB 恢复历史消息 ──
if not history:
    sid = st.session_state.get("active_session_id")
    if sid:
        from src.agents.memory import ConversationMemory
        from src.ui.session_state import run_async_safe

        memory = ConversationMemory()
        db_messages = run_async_safe(memory.load_recent(sid, limit=20))
        if db_messages:
            sessions = st.session_state["chat_sessions"]
            sessions[sid]["messages"] = db_messages
            # 更新标题为第一条用户消息的前 30 字
            for m in db_messages:
                if m["role"] == "user":
                    sessions[sid]["title"] = m["content"][:30]
                    break
            history = db_messages

# 显示当前会话历史消息
for msg in history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("输入你的问题..."):
    add_chat_session_message("user", prompt)
    _after_message(st.session_state["active_session_id"], "user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        progress_placeholder = st.empty()
        output_placeholder = st.empty()
        full_text = ""

        try:
            from src.agents.graph import chat_stream, NODE_LABELS
            from src.utils.stream_bridge import stream_sync

            sid = st.session_state.get("active_session_id")
            chat_summary = st.session_state["chat_sessions"][sid].get("summary") if sid else None
            for event in stream_sync(
                lambda: chat_stream(
                    prompt,
                    history[:-1] if len(history) > 1 else None,
                    summary=chat_summary,
                )
            ):
                if event["type"] == "progress":
                    label = NODE_LABELS.get(event["node"], "")
                    if label:
                        progress_placeholder.caption(label)

                elif event["type"] == "clear":
                    full_text = ""
                    output_placeholder.empty()

                elif event["type"] == "token":
                    full_text += event["content"]
                    output_placeholder.markdown(full_text + "▌")

                elif event["type"] == "done":
                    progress_placeholder.empty()
                    response = event.get("response", "")
                    if response:
                        output_placeholder.markdown(response)
                        add_chat_session_message("assistant", response)
                        _after_message(st.session_state["active_session_id"], "assistant", response)
                    else:
                        output_placeholder.markdown("抱歉，出错了。")
                        add_chat_session_message("assistant", "抱歉，出错了。")
                        _after_message(st.session_state["active_session_id"], "assistant", "抱歉，出错了。")

                elif event["type"] == "error":
                    progress_placeholder.empty()
                    error_msg = f"出错了: {event['message']}"
                    output_placeholder.error(error_msg)
                    add_chat_session_message("assistant", error_msg)
                    _after_message(st.session_state["active_session_id"], "assistant", error_msg)
                    break

        except Exception as e:
            progress_placeholder.empty()
            error_msg = f"出错了: {str(e)}"
            st.error(error_msg)
            add_chat_session_message("assistant", error_msg)
            _after_message(st.session_state["active_session_id"], "assistant", error_msg)

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
        has_summary = bool(session.get("summary"))
        summary_indicator = " 📋" if has_summary else ""

        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(
                f"{prefix}{title} ({msg_count // 2}轮){summary_indicator}",
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
