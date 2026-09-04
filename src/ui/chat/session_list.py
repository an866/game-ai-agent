"""会话列组件 —— 新建/搜索/选择/删除 会话（X 三列式的中间列）"""

import streamlit as st

from src.ui.session_state import init_chat_sessions, create_chat_session, switch_session


def build_session_rows(sessions: dict, active_id: str | None) -> list[dict]:
    """会话 → 展示行（活跃会话排最前，按标题排序）"""
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


def render_session_list(max_items: int = 50) -> None:
    """渲染会话列；交互（新建/切换/删除）直接操作 session_state"""
    init_chat_sessions()
    sessions = st.session_state["chat_sessions"]
    active = st.session_state.get("active_session_id")

    if st.button("➕ 新对话", key="new_session", use_container_width=True):
        create_chat_session()
        st.rerun()

    filter_q = st.text_input("搜索会话", key="session_filter", label_visibility="collapsed",
                             placeholder="搜索会话…")

    rows = build_session_rows(sessions, active)
    if filter_q:
        rows = [r for r in rows if filter_q.lower() in r["title"].lower()]

    for row in rows[:max_items]:
        title = row["title"]
        marker = " 📋" if row["has_summary"] else ""
        prefix = "▸ " if row["is_active"] else ""
        btn_label = f"{prefix}{title} ({row['rounds']}轮){marker}"
        if st.button(btn_label, key=f"sess_{row['sid']}", use_container_width=True,
                     type="primary" if row["is_active"] else "secondary"):
            switch_session(row["sid"])
            st.rerun()
        if not row["is_active"]:
            if st.button("🗑", key=f"del_{row['sid']}", help="删除此对话"):
                del st.session_state["chat_sessions"][row["sid"]]
                st.rerun()