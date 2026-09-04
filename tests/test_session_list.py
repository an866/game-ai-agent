"""session_list 测试 —— 会话摘要行数据的纯函数部分"""

from src.ui.chat import session_list


class TestSessionSummaries:
    def test_empty(self):
        rows = session_list.build_session_rows({}, active_id=None)
        assert rows == []

    def test_rows_sorted_and_active_marked(self):
        sessions = {
            "a": {"title": "T1", "messages": [{"role": "user"}, {"role": "assistant"}] * 2,
                  "summary": None},
            "b": {"title": "T2", "messages": [{"role": "user"}], "summary": "摘要"},
        }
        rows = session_list.build_session_rows(sessions, active_id="b")
        assert rows[0]["sid"] == "b"
        assert rows[0]["is_active"] is True
        assert rows[0]["rounds"] == 0
        assert rows[0]["has_summary"] is True

    def test_rounds_computed(self):
        sessions = {"a": {"title": "T", "messages": [{"role": "user"}, {"role": "assistant"}] * 3, "summary": None}}
        rows = session_list.build_session_rows(sessions, active_id=None)
        assert rows[0]["rounds"] == 3