"""app 主壳冒烟 —— 图标栏渲染、tab 分发、主题注入不崩"""

import streamlit as st
from streamlit.testing.v1 import AppTest


def _run_app():
    return AppTest.from_file("src/ui/app.py", default_timeout=30).run()


class TestAppShell:
    def test_app_runs(self):
        at = _run_app()
        assert not at.exception

    def test_icon_buttons_present(self):
        at = _run_app()
        labels = [b.label for b in at.button]
        assert "💬" in labels and "💰" in labels and "🎯" in labels

    def test_theme_buttons_present(self):
        at = _run_app()
        # 主题按钮以主题名（neon/night/light）作为 label；
        # 侧栏仍有 st.caption("主题") 辅助文字（计划原断言"主题"在按钮 label 上，已按实际渲染调整）
        assert any(b.label in ("neon", "night", "light") for b in at.button)

    def test_default_tab_is_chat(self):
        at = _run_app()
        # 默认 tab=chat：主区渲染 chat_panel（会话列 + 聊天区）
        # （原断言 st.title("💬 AI 对话") 在 Task 9 面板化后移除，改用会话列"➕ 新对话"按钮）
        assert "➕ 新对话" in [b.label for b in at.button]

    def test_switch_tab_to_price(self):
        at = _run_app()
        # AppTest 的 at.button(...) 按 widget key 查找而非 label —— 用图标栏按钮的固定 key
        # （计划原写法 at.button("💰") 会抛 KeyError，已调整）
        at.button(key="tab_price").click().run()
        assert not at.exception