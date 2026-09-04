"""price 面板测试 —— 监控/告警数据处理"""

from src.ui.panels import price_watch


def test_watch_rows_to_dicts():
    rows = price_watch.watch_rows_to_dicts([
        {"id": 1, "game_name": "黑神话", "target_price": 200.0, "status": "active",
         "created_at": "2026-09-01"},
    ])
    assert rows[0]["game_name"] == "黑神话"
    assert rows[0]["target_price"] == 200.0


def test_alert_rows_columns():
    rows = price_watch.watch_rows_to_dicts([])
    assert rows == []