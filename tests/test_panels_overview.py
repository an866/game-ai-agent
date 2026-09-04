"""overview 面板测试 —— 统计字典规整"""

from src.ui.panels import overview


def test_normalize_stats_defaults():
    s = overview.normalize_stats({})
    assert s["watchlist"] == 0 and s["alerts"] == 0 and s["news_count"] == 0
    assert s["best_deal"] == "-"


def test_normalize_stats_keeps_values():
    s = overview.normalize_stats({"watchlist": 5, "best_deal": "-45%"})
    assert s["watchlist"] == 5 and s["best_deal"] == "-45%"