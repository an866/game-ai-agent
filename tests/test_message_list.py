"""message_list 测试 —— DeepSeek 形态：用户气泡 + 助手 Markdown"""

from src.ui.chat import message_list


class TestUserBubble:
    def test_user_bubble_right_and_accent(self):
        html = message_list.user_bubble_html("你好")
        assert "ds-chat-row-user" in html
        assert "ds-bubble-user" in html
        # 配色在 theme CSS 的 .ds-bubble-user（var(--accent1)），HTML 只给结构类
        from src.ui import theme
        css = theme.get_theme_css("neon")
        assert ".ds-bubble-user" in css
        assert "var(--accent1)" in css
        assert "你好" in html

    def test_escape_content(self):
        html = message_list.user_bubble_html("<script>alert(1)</script>")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_bubble_html_user_compat(self):
        html = message_list.bubble_html("user", "hi")
        assert "ds-bubble-user" in html


class TestAssistantMarkdown:
    def test_no_bubble_shell(self):
        text = message_list.assistant_markdown("回复内容")
        assert text == "回复内容"
        assert "ds-bubble" not in text
        assert "<div" not in text

    def test_cursor_appended(self):
        text = message_list.assistant_markdown("正文", with_cursor=True)
        assert text.endswith(message_list.CURSOR)
        assert text.startswith("正文")

    def test_bubble_html_assistant_compat_returns_markdown(self):
        text = message_list.bubble_html("assistant", "**bold**")
        assert text == "**bold**"

    def test_safe_suffix_passthrough(self):
        text = message_list.bubble_html("assistant", "正文", safe_suffix="▌")
        assert text.endswith("▌")


class TestStreaming:
    def test_append_token(self):
        assert message_list.append_token("黑", "神话") == "黑神话"
