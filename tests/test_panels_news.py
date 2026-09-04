"""news 面板测试 —— 筛选参数归一"""

from src.ui.panels import news


def test_filters_normalized():
    f = news.normalize_filters(game="全部", source="游民星空", days="最近 7 天")
    assert f == {"game": None, "source": "游民星空", "days": 7}


def test_filters_all_none():
    assert news.normalize_filters(game="全部", source="全部", days="全部") == {
        "game": None, "source": None, "days": None}