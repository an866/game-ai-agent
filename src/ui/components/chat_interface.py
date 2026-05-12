"""对话界面组件 —— 消息气泡、流式输出、快捷指令"""

import asyncio
import streamlit as st


def render_message(role: str, content: str):
    """渲染单条消息气泡"""
    with st.chat_message(role):
        st.markdown(content)


def render_chat_history(messages: list[dict]):
    """渲染完整的对话历史"""
    for msg in messages:
        render_message(msg["role"], msg["content"])


def render_quick_commands():
    """渲染快捷指令按钮"""
    st.caption("快捷指令:")
    cols = st.columns(4)
    commands = [
        ("/price", "查价格"),
        ("/recommend", "推荐游戏"),
        ("/news", "最新新闻"),
        ("/search", "搜索游戏"),
    ]
    for i, (cmd, label) in enumerate(commands):
        with cols[i]:
            if st.button(label, key=f"cmd_{cmd}"):
                st.session_state["pending_command"] = cmd
                st.rerun()


async def stream_chat_response(graph, message: str, history: list[dict]):
    """流式对话（占位 —— Streamlit 原生不支持 SSE，用模拟方式）"""
    from src.agents.graph import chat

    response = await chat(message, history)
    return response
