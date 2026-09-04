"""ui_state 单元测试 —— 分区读写与面板切换不丢状态"""

import streamlit as st
import pytest
from src.ui import ui_state


class TestUiState:
    def test_defaults(self):
        ui_state.init_ui_state()
        assert ui_state.get_tab() == "chat"
        assert ui_state.get_theme() == "neon"

    def test_set_tab_roundtrip(self):
        ui_state.init_ui_state()
        ui_state.set_tab("search")
        assert ui_state.get_tab() == "search"

    def test_panel_state_isolated_by_panel(self):
        ui_state.init_ui_state()
        ui_state.set_panel_state("search", {"query": "黑神话"})
        ui_state.set_panel_state("news", {"days": 7})
        assert ui_state.get_panel_state("search") == {"query": "黑神话"}
        assert ui_state.get_panel_state("news") == {"days": 7}
        # 切换 tab 不丢面板状态
        ui_state.set_tab("chat")
        ui_state.set_tab("search")
        assert ui_state.get_panel_state("search") == {"query": "黑神话"}

    def test_panel_state_missing_returns_default(self):
        ui_state.init_ui_state()
        assert ui_state.get_panel_state("nope") == {}

    def test_panel_state_merge(self):
        ui_state.init_ui_state()
        ui_state.set_panel_state("price", {"watchlist": [1]})
        ui_state.update_panel_state("price", {"alerts": [2]})
        s = ui_state.get_panel_state("price")
        assert s == {"watchlist": [1], "alerts": [2]}

    def test_theme_roundtrip(self):
        ui_state.init_ui_state()
        ui_state.set_theme("light")
        assert ui_state.get_theme() == "light"