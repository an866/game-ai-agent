"""消息气泡流 + 流式渲染（保留 stream_sync 管线机制，视觉升级）"""

import html as _html

import streamlit as st


def bubble_html(role: str, content: str, safe_suffix: str = "") -> str:
    """聊天气泡 HTML（颜色全走 CSS 变量）

    safe_suffix: 已转义内容之后追加的原始 HTML（如流式光标 span）——
    该参数不为调用方做转义，调用方负责传入安全内容。
    """
    safe = _html.escape(content)
    if role == "user":
        align, bg, grd = "flex-end", "linear-gradient(135deg, var(--accent1), var(--accent2))", "box-shadow: var(--glow);"
    else:
        align, bg, grd = "flex-start", "var(--panel-2)", ""
    return (
        f'<div style="display:flex; justify-content:{align}; margin:6px 0;">'
        f'  <div style="max-width:75%; background:{bg}; {grd} color:var(--text);'
        f'           padding:10px 14px; border-radius:14px; border:1px solid var(--border);'
        f'           white-space:pre-wrap; word-break:break-word; font-size:14px;">{safe}{safe_suffix}</div>'
        f'</div>'
    )


def append_token(full: str, chunk: str) -> str:
    return full + chunk


def render_message_list(messages: list[dict]) -> None:
    """渲染既有消息流（无流式时）"""
    for m in messages:
        st.markdown(bubble_html(m["role"], m["content"]), unsafe_allow_html=True)


def render_streaming_placeholder() -> tuple[object, object]:
    """流式输出两件套：进度位、输出位"""
    progress_ph = st.empty()
    output_ph = st.empty()
    return progress_ph, output_ph


def render_streaming_cursor(output_ph, full_text: str) -> None:
    """打字光标（动画由 theme.py 注入的 blink keyframes 提供）"""
    output_ph.markdown(
        bubble_html("assistant", full_text, safe_suffix='<span style="animation: blink 1s steps(2) infinite;">▌</span>'),
        unsafe_allow_html=True,
    )