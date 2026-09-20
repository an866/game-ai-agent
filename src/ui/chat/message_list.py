"""消息流 —— DeepSeek 网页版形态

- 用户：右侧淡蓝气泡（columns 右栏 + 内联样式，避免 Streamlit 包裹层吃掉 class CSS）
- 助手：左侧无重气泡，正文走 Streamlit Markdown（表格/列表可渲染）
- 流式光标用字符 ▌，避免 unsafe_allow_html 注入正文
"""

import html as _html

import streamlit as st

CURSOR = "▌"

# 用户气泡：内联样式保证在 Streamlit 1.5x 的 emotion 包裹层下仍生效
_USER_BUBBLE_CSS = (
    "background:rgba(59,130,246,0.16);"
    "border:1px solid rgba(59,130,246,0.35);"
    "padding:10px 16px;"
    "border-radius:16px 16px 4px 16px;"
    "white-space:pre-wrap;"
    "word-break:break-word;"
    "font-size:14px;"
    "line-height:1.55;"
    "margin-left:auto;"
    "display:inline-block;"
    "max-width:100%;"
    "text-align:left;"
)


def user_bubble_html(content: str) -> str:
    """用户消息气泡 HTML（带内联样式，可直接 unsafe_allow_html）"""
    safe = _html.escape(content)
    return (
        f'<div style="display:flex;justify-content:flex-end;width:100%;margin:12px 0;">'
        f'<div class="ds-bubble-user" style="{_USER_BUBBLE_CSS}">{safe}</div>'
        f"</div>"
    )


def render_user_message(content: str) -> None:
    """用户消息：右栏 + flex 右对齐淡蓝气泡"""
    safe = _html.escape(content)
    left, right = st.columns([1, 11], gap="small")
    with right:
        st.markdown(
            f'<div style="display:flex;justify-content:flex-end;width:100%;margin:8px 0;">'
            f'<div class="ds-bubble-user" style="{_USER_BUBBLE_CSS}">{safe}</div>'
            f"</div>",
            unsafe_allow_html=True,
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
            render_user_message(content)
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
