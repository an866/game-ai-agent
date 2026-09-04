"""全局 UI 状态 —— ui = {tab, theme, panel_state}

唯一读写入口：UI 代码不得直接操作 st.session_state["ui"]。
面板切换不丢状态：各面板的状态挂在自己的命名空间。
"""

import streamlit as st

DEFAULT_TAB = "chat"
DEFAULT_THEME = "neon"

TABS = ("chat", "overview", "recommend", "price", "news", "search")
THEMES = ("neon", "night", "light")

# 图标栏顺序（D5 决策）：与 PANEL_TITLE 下标一致
TAB_ICONS = {"chat": "💬", "overview": "🏠", "recommend": "🎯",
             "price": "💰", "news": "📰", "search": "🔍"}


def _ui() -> dict:
    if "ui" not in st.session_state:
        st.session_state["ui"] = {
            "tab": DEFAULT_TAB,
            "theme": DEFAULT_THEME,
            "panel_state": {},
        }
    return st.session_state["ui"]


def init_ui_state() -> None:
    _ui()


def get_tab() -> str:
    return _ui()["tab"]


def set_tab(tab: str) -> None:
    assert tab in TABS, f"未知 tab: {tab}"
    _ui()["tab"] = tab


def get_theme() -> str:
    return _ui()["theme"]


def set_theme(theme: str) -> None:
    assert theme in THEMES, f"未知主题: {theme}"
    _ui()["theme"] = theme


def get_panel_state(panel: str) -> dict:
    return _ui()["panel_state"].get(panel, {})


def set_panel_state(panel: str, state: dict) -> None:
    _ui()["panel_state"][panel] = state


def update_panel_state(panel: str, patch: dict) -> None:
    merged = dict(get_panel_state(panel))
    merged.update(patch)
    _ui()["panel_state"][panel] = merged