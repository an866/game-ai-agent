"""UI V2 主壳 —— 图标栏 + 模式分发 + 主题注入

单页面板架构（spec D4）：sidebar 为图标栏，主区按 ui["tab"] 渲染
聊天三列或工具面板。面板填充顺序见实施计划 Task 10-14。
"""

import streamlit as st

from src.ui import ui_state, theme
from src.ui.session_state import init_session_state, init_chat_sessions

st.set_page_config(page_title="游戏 AI 助手", page_icon="🎮",
                   layout="wide", initial_sidebar_state="expanded")

ui_state.init_ui_state()
init_session_state()
init_chat_sessions()

theme.inject_theme(ui_state.get_theme())

# ── 侧栏：图标栏 ──
with st.sidebar:
    st.markdown("### 🎮")
    current = ui_state.get_tab()
    for tab in ui_state.TABS:
        icon = ui_state.TAB_ICONS[tab]
        active = tab == current
        if st.button(icon, key=f"tab_{tab}", help=tab,
                     type="primary" if active else "secondary",
                     use_container_width=True):
            ui_state.set_tab(tab)
            st.rerun()
    st.divider()
    st.caption("主题")
    for t in ui_state.THEMES:
        if st.button(t, key=f"theme_{t}", use_container_width=True):
            ui_state.set_theme(t)
            st.rerun()

# ── 主区：模式分发 ──
tab = ui_state.get_tab()

if tab == "chat":
    from src.ui.chat.chat_panel import render_chat_panel
    render_chat_panel()
elif tab == "overview":
    from src.ui.panels.overview import render_overview_panel
    render_overview_panel()
elif tab == "search":
    from src.ui.panels.search import render_search_panel
    render_search_panel()
elif tab == "news":
    from src.ui.panels.news import render_news_panel
    render_news_panel()
else:
    # 工具面板路由（后续任务逐个接入真实渲染）
    route = {
        "recommend": None, "price": None,
    }
    render = route[tab]
    if render is None:
        st.title(tab)
        st.info(f"面板 {tab}（Task 12-14 填充）")
    else:
        render()