"""search 面板测试 —— 平台/类型映射与搜索推导"""

from src.ui.panels import search


def test_filter_params():
    params = search.build_filter_params(platforms=["PC"], genres=["动作", "RPG"])
    assert params["platforms"] == "4"
    assert params["genres"] == "action,role-playing-games-rpg"


def test_filter_params_empty():
    assert search.build_filter_params(platforms=[], genres=[]) == {}


def test_panel_state_query_roundtrip():
    state = {"query": "黑神话", "platforms": ["PC"], "genres": []}
    q = search.build_query_from_state(state)
    assert q == "黑神话"