"""recommend 面板测试 —— 画像提示与搜索词构建"""

from src.ui.panels import recommend
from src.services.chat_service import build_profile_text


def test_profile_label_text():
    assert recommend.profile_label({"favorite_genres": "RPG", "favorite_games": "黑神话"}) is not None
    assert recommend.profile_label({}) is None


def test_search_query_with_profile():
    profile = {"favorite_genres": "动作"}
    q = recommend.build_search_query("黑神话", profile, genre_pref=["动作"])
    assert q.startswith("用户画像:")