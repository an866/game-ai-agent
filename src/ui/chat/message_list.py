"""消息流 —— DeepSeek 网页版形态

- 用户：右侧实心气泡（accent 渐变），HTML 转义
- 助手：左侧无重气泡，正文走 Streamlit Markdown（表格/列表可渲染）
- 流式光标用字符 ▌，避免 unsafe_allow_html 注入正文
"""

import html as _html

import streamlit as st

CURSOR = "▌"


def user_bubble_html(content: str) -> str:
    """用户消息气泡（右对齐、实心、圆角）"""
    safe = _html.escape(content)
    return (
        '<div class="ds-chat-row ds-chat-row-user">'
        f'  <div class="ds-bubble-user">{safe}</div>'
        "</div>"
    )


def assistant_markdown(content: str, with_cursor: bool = False) -> str:
    """助手正文：交给 st.markdown 渲染（无气泡壳）。"""
    body = content or ""
    if with_cursor:
        body = body + CURSOR
    return body


def bubble_html(role: str, content: str, safe_suffix: str = "") -> str:
    """兼容入口。

    user → 气泡 HTML（需 unsafe_allow_html）。
    assistant → Markdown 正文（safe_suffix 仅追加在文末，调用方保证安全）。
    """
    if role == "user":
        return user_bubble_html(content)
    return assistant_markdown(content) + (safe_suffix or "")


def append_token(full: str, chunk: str) -> str:
    return full + chunk


def render_message_list(messages: list[dict]) -> None:
    """渲染既有消息流（用户气泡 + 助手 Markdown）"""
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "")
        if role == "user":
            st.markdown(user_bubble_html(content), unsafe_allow_html=True)
        else:
            st.markdown(assistant_markdown(content) or "抱歉，出错了。")


def render_streaming_placeholder() -> tuple[object, object]:
    """流式输出两件套：进度位、输出位"""
    progress_ph = st.empty()
    output_ph = st.empty()
    return progress_ph, output_ph


def render_streaming_cursor(output_ph, full_text: str) -> None:
    """流式助手正文 + 字符光标"""
    output_ph.markdown(assistant_markdown(full_text, with_cursor=True))
