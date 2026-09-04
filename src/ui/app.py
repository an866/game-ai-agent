"""UI V2 主壳 —— 图标栏 + 模式分发 + 主题注入

单页面板架构（spec D4）：sidebar 为图标栏，主区按 ui["tab"] 渲染
聊天三列或工具面板。面板填充顺序见实施计划 Task 10-14。
"""

import streamlit as st

from src.ui import ui_state, theme
from src.ui.session_state import init_chat_sessions

st.set_page_config(page_title="游戏 AI 助手", page_icon="🎮",
                   layout="wide", initial_sidebar_state="expanded")

ui_state.init_ui_state()
init_chat_sessions()

theme.inject_theme(ui_state.get_theme())

# Streamlit 裸键 'c' 清缓存快捷键会劫持 Ctrl+C 复制 —— 组件拦截（见 ctrl_c_shield）
from src.ui.components.ctrl_c_shield import render_ctrl_c_shield
render_ctrl_c_shield()

# ── 侧栏：图标栏 ──
with st.sidebar:
    st.markdown("### 🎮")
    current = ui_state.get_tab()
    for tab in ui_state.TABS:
        active = tab == current
        label = f"{ui_state.TAB_ICONS[tab]} {ui_state.TAB_NAMES_CN[tab]}"
        if st.button(label, key=f"tab_{tab}", help=tab,
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
elif tab == "price":
    from src.ui.panels.price_watch import render_price_panel
    render_price_panel()
elif tab == "recommend":
    from src.ui.panels.recommend import render_recommend_panel
    render_recommend_panel()