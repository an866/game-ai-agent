"""message_list 测试 —— 气泡 HTML 构造与流式辅助"""

from src.ui.chat import message_list


class TestBubbleHtml:
    def test_user_bubble(self):
        html = message_list.bubble_html("user", "你好")
        assert "var(--accent1)" in html  # 渐变由 CSS 变量引用
        assert "你好" in html
        assert "flex-end" in html

    def test_assistant_bubble(self):
        html = message_list.bubble_html("assistant", "回复")
        assert "var(--panel-2)" in html
        assert "flex-start" in html

    def test_escape_content(self):
        html = message_list.bubble_html("user", "<script>alert(1)</script>")
        assert "<script>" not in html

    def test_cursor_suffix_not_escaped(self):
        html = message_list.bubble_html("assistant", "正文", safe_suffix="<b>▌</b>")
        assert "<b>▌</b>" in html
        assert "正文" in html


class TestStreaming:
    def test_append_token(self):
        assert message_list.append_token("黑", "神话") == "黑神话"

    def test_truncate_long_content(self):
        long = "x" * 500
        assert len(message_list.append_token(long, "y")) == 501