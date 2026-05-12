"""AI 对话页 —— 自然语言交互"""

import asyncio
import streamlit as st
from src.ui.session_state import add_chat_message, get_chat_history

st.title("AI 对话")

st.caption("支持快捷指令: `/price 游戏名` `/recommend 游戏名` `/news 关键词` `/search 游戏名`")

# 显示历史消息
history = get_chat_history()
for msg in history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 输入框
if prompt := st.chat_input("输入你的问题..."):
    add_chat_message("user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            try:
                from src.agents.graph import chat
                response = asyncio.run(chat(prompt, history[:-1] if len(history) > 1 else None))
                st.markdown(response)
                add_chat_message("assistant", response)
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
