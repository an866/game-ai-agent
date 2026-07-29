"""AI 对话页 —— 自然语言交互"""

import asyncio
import streamlit as st
from src.ui.session_state import add_chat_message, get_chat_history

st.title("AI 对话")

st.caption("支持快捷指令: `/price 游戏名` `/recommend 游戏名` `/news 关键词` `/search 游戏名`")

# 显示历史消息
history = get_chat_history()

# ── 页面首次加载时从 DB 恢复历史消息 ──
if not history:
    from src.agents.memory import ConversationMemory
    from src.ui.session_state import run_async_safe
    # 简单模式无多会话，用 "default" session_id
    memory = ConversationMemory()
    db_messages = run_async_safe(memory.load_recent("default", limit=20))
    if db_messages:
        st.session_state["chat_messages"] = db_messages
        history = db_messages

for msg in history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 输入框
if prompt := st.chat_input("输入你的问题..."):
    add_chat_message("user", prompt)
    # ── 持久化 ──
    from src.agents.memory import ConversationMemory
    from src.ui.session_state import run_async_safe
    mem = ConversationMemory()
    run_async_safe(mem.save_message("default", "user", prompt))

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            try:
                from src.agents.graph import chat
                # 使用压缩后的 context
                chat_summary = st.session_state.get("chat_summary")
                ctx_history = history[:-1] if len(history) > 1 else None
                response = asyncio.run(chat(prompt, ctx_history, summary=chat_summary))
                st.markdown(response)
                add_chat_message("assistant", response)
                # ── 持久化 + 压缩检测 ──
                run_async_safe(mem.save_message("default", "assistant", response))
                current_msgs = st.session_state.get("chat_messages", [])
                if mem.should_compress(len(current_msgs)):
                    compacted, new_summary = run_async_safe(
                        mem.compress(current_msgs)
                    )
                    st.session_state["chat_messages"] = compacted
                    st.session_state["chat_summary"] = new_summary
            except Exception as e:
                error_msg = f"出错了: {str(e)}"
                st.error(error_msg)
                add_chat_message("assistant", error_msg)

# 侧边栏：对话历史
with st.sidebar:
    st.subheader("对话历史")
    if st.button("清除历史"):
        st.session_state["chat_messages"] = []
        st.rerun()
    st.caption(f"共 {len(history)} 条消息")
