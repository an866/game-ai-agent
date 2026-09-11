"""会话列组件 —— DeepSeek 历史列表 + 右键菜单

标题左键切换；右键弹出菜单（重命名/置顶/分享/多选/删除）。
另提供 ⋯ popover，右键脚本失效时仍可删除。
"""

import streamlit as st

from src.ui.chat.session_context import (
    render_ctx_menu_runtime,
    _hidden_action_buttons,
    session_row_attrs,
)
from src.ui.session_state import init_chat_sessions, create_chat_session, switch_session


def _truncate(title: str, n: int = 28) -> str:
    t = (title or "未命名对话").replace("\n", " ").strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def build_session_rows(sessions: dict, active_id: str | None) -> list[dict]:
    rows = []
    for sid, s in sessions.items():
        rounds = len(s.get("messages", [])) // 2
        rows.append({
            "sid": sid,
            "title": s.get("title", "未命名对话"),
            "rounds": rounds,
            "has_summary": bool(s.get("summary")),
            "is_active": sid == active_id,
        })
    rows.sort(key=lambda r: (not r["is_active"], r["title"]))
    return rows


def _popover_menu(sid: str, title: str) -> None:
    """⋯ 菜单（不依赖 JS 的可靠入口）"""
    with st.popover("⋯", help="更多操作"):
        st.caption(title[:40])
        if st.button("重命名", key=f"pop_rename_{sid}", use_container_width=True):
            st.toast("重命名即将上线", icon="✏️")
        if st.button("置顶", key=f"pop_pin_{sid}", use_container_width=True):
            st.toast("置顶即将上线", icon="📌")
        if st.button("分享", key=f"pop_share_{sid}", use_container_width=True):
            st.toast("分享即将上线", icon="↗")
        if st.button("多选", key=f"pop_multi_{sid}", use_container_width=True):
            st.toast("多选即将上线", icon="☑")
        if st.button("删除", key=f"pop_del_{sid}", use_container_width=True, type="primary"):
            sessions = st.session_state.get("chat_sessions") or {}
            if sid in sessions:
                del sessions[sid]
                if st.session_state.get("active_session_id") == sid:
                    st.session_state["active_session_id"] = None
            st.rerun()


def render_session_list(max_items: int = 50) -> None:
    init_chat_sessions()
    render_ctx_menu_runtime()

    sessions = st.session_state["chat_sessions"]
    active = st.session_state.get("active_session_id")

    if st.button("＋ 新对话", key="new_session", use_container_width=True):
        create_chat_session()
        st.rerun()

    filter_q = st.text_input(
        "搜索会话", key="session_filter",
        label_visibility="collapsed", placeholder="搜索会话…",
    )

    rows = build_session_rows(sessions, active)
    if filter_q:
        rows = [r for r in rows if filter_q.lower() in r["title"].lower()]

    if not rows:
        st.caption("暂无对话")
        return

    st.caption("右键标题或点 ⋯：重命名 / 置顶 / 分享 / 多选 / 删除")
    # 注意：不要在每行后闭合 ds-sess-col —— Streamlit 会把 widget 渲染成兄弟节点，
    # 提前闭合会导致后续行不在列内、右键拦截失效。
    st.markdown('<div class="ds-sess-col">', unsafe_allow_html=True)
    for row in rows[:max_items]:
        sid = row["sid"]
        title = row["title"]
        display = _truncate(title)

        st.markdown(session_row_attrs(sid), unsafe_allow_html=True)
        c1, c2 = st.columns([5, 1], gap="small")
        with c1:
            if st.button(
                display, key=f"sess_{sid}", use_container_width=True,
                type="primary" if row["is_active"] else "secondary",
                help=f"{title}（右键打开菜单）",
            ):
                if not row["is_active"]:
                    switch_session(sid)
                    st.rerun()
        with c2:
            _popover_menu(sid, title)
        _hidden_action_buttons(sid, title)
    st.markdown("</div>", unsafe_allow_html=True)
