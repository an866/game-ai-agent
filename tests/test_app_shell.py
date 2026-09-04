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

    def test_switch_tab_to_overview(self, monkeypatch):
        """overview 分支无头渲染不崩（Task 10 接入后新增）

        数据源打桩：真实 DB/API 在测试环境不可用且带 10s×重试超时，
        直接跑会拖死 AppTest；打桩仅验证分支渲染路径本身不抛异常。
        """
        import src.ui.panels.overview as overview_mod

        monkeypatch.setattr(overview_mod, "_load_stats", lambda: {
            "watchlist": 3, "alerts": 1, "news_count": 120, "best_deal": "-45%",
        })
        monkeypatch.setattr(overview_mod, "_load_hot", lambda: [
            {"name": "Dota 2", "players": "100"},
            {"name": "Counter-Strike 2", "players": "-"},
        ])

        at = _run_app()
        at.button(key="tab_overview").click().run()
        assert not at.exception
        # 顶部返回条 + 统计卡（HTML markdown 内） + 热门在线渲染
        assert any("返回对话" in b.label for b in at.button)
        assert any("活跃监控" in m.value for m in at.markdown)
        assert any("Dota 2" in m.value for m in at.markdown)

    def test_text_input_submit_triggers_reply(self, monkeypatch):
        """输入框键入并回车 → 提交 + 流式回复；last_submitted 哨兵防重复提交"""
        import src.agents.graph as graph_mod

        async def fake_chat_stream(message, history=None, summary=None):
            yield {"type": "progress", "node": "router"}
            yield {"type": "done", "response": "测试回复"}

        monkeypatch.setattr(graph_mod, "chat_stream", fake_chat_stream)

        at = AppTest.from_file("src/ui/app.py", default_timeout=60).run()
        assert not at.exception

        # 键入并回车 → 用户气泡 + 流式回复（画面 markdown 气泡各一份）
        at.text_input(key="chat_input_v2").set_value("测试问题")
        at.run()
        assert not at.exception
        assert any("测试问题" in m.value for m in at.markdown)
        assert any("测试回复" in m.value for m in at.markdown)

        # 再次 run：文本保留在输入框，哨兵阻止重复提交（用户气泡不翻倍）
        at.run()
        assert not at.exception
        assert sum("测试问题" in m.value for m in at.markdown) == 1