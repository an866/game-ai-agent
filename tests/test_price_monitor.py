"""价格巡检服务测试 —— 触发 / 48h 去重 / 超窗重发 / 降级"""

import pytest

from src.services.price_monitor_service import run_price_check


class _DummySession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _DummySessionFactory:
    def __call__(self):
        return lambda: _DummySession()


class FakeWatch:
    def __init__(self, id, game_name, target_price):
        self.id = id
        self.game_name = game_name
        self.target_price = target_price
        self.status = "active"


class FakeWatchRepo:
    def __init__(self, watches):
        self.watches = watches
        self.updated = []

    async def get_all_active(self):
        return [w for w in self.watches if w.status == "active"]

    async def update_status(self, watch_id, status):
        self.updated.append((watch_id, status))


class FakeAlertRepo:
    def __init__(self, recent_ids=None):
        self.recent_ids = set(recent_ids or [])  # 窗口内已有告警的 watchlist_id
        self.created = []
        self._now_recent = set(recent_ids or [])

    async def has_recent_alert(self, watchlist_id, window_hours=48):
        return watchlist_id in self.recent_ids

    async def create_alert(self, watchlist_id, current_price, target_price, store_name="Unknown"):
        self.created.append({
            "watchlist_id": watchlist_id,
            "current_price": current_price,
            "target_price": target_price,
            "store_name": store_name,
        })
        self.recent_ids.add(watchlist_id)


class FakeCheapSharkTool:
    """可注入的 cheapshark —— deals_by_title: {title: [deals]}"""

    def __init__(self, deals_by_title):
        self.deals_by_title = deals_by_title

    async def _arun(self, title, on_sale=True):
        return self.deals_by_title.get(title, [])


@pytest.mark.asyncio
async def test_triggers_alert_below_target(monkeypatch):
    monkeypatch.setattr(
        "src.services.price_monitor_service.CheapSharkDealsTool",
        lambda: FakeCheapSharkTool({"黑神话": [{"sale_price": 150.0, "store_name": "Steam"}]}),
    )
    watch_repo = FakeWatchRepo([FakeWatch(1, "黑神话", 200.0)])
    alert_repo = FakeAlertRepo()

    monkeypatch.setattr("src.services.price_monitor_service.WatchlistRepository", lambda s: watch_repo)
    monkeypatch.setattr("src.services.price_monitor_service.PriceAlertRepository", lambda s: alert_repo)

    stats = await run_price_check(session_factory=_DummySessionFactory())
    assert stats == {"checked": 1, "triggered": 1, "skipped": 0}
    assert alert_repo.created[0]["current_price"] == 150.0
    assert alert_repo.created[0]["store_name"] == "Steam"
    assert watch_repo.updated == [(1, "active")]


@pytest.mark.asyncio
async def test_dedup_within_window(monkeypatch):
    """48h 窗口内已有告警 → 跳过"""
    monkeypatch.setattr(
        "src.services.price_monitor_service.CheapSharkDealsTool",
        lambda: FakeCheapSharkTool({"黑神话": [{"sale_price": 100.0, "store_name": "Steam"}]}),
    )
    watch_repo = FakeWatchRepo([FakeWatch(1, "黑神话", 200.0)])
    alert_repo = FakeAlertRepo(recent_ids={1})

    monkeypatch.setattr("src.services.price_monitor_service.WatchlistRepository", lambda s: watch_repo)
    monkeypatch.setattr("src.services.price_monitor_service.PriceAlertRepository", lambda s: alert_repo)

    stats = await run_price_check(session_factory=_DummySessionFactory())
    assert stats == {"checked": 1, "triggered": 0, "skipped": 1}
    assert alert_repo.created == []


@pytest.mark.asyncio
async def test_retrigger_after_window(monkeypatch):
    """其他监控项不在窗口内 → 正常触发"""
    monkeypatch.setattr(
        "src.services.price_monitor_service.CheapSharkDealsTool",
        lambda: FakeCheapSharkTool({"A": [{"sale_price": 10.0, "store_name": "S"}]}),
    )
    watch_repo = FakeWatchRepo([FakeWatch(1, "A", 50.0), FakeWatch(2, "B", 50.0)])
    alert_repo = FakeAlertRepo(recent_ids={1})  # 只有 1 在窗口内

    monkeypatch.setattr("src.services.price_monitor_service.WatchlistRepository", lambda s: watch_repo)
    monkeypatch.setattr("src.services.price_monitor_service.PriceAlertRepository", lambda s: alert_repo)

    stats = await run_price_check(session_factory=_DummySessionFactory())
    assert stats == {"checked": 2, "triggered": 0, "skipped": 1}  # B 价格高于目标
    assert alert_repo.created == []


@pytest.mark.asyncio
async def test_no_alert_above_target(monkeypatch):
    monkeypatch.setattr(
        "src.services.price_monitor_service.CheapSharkDealsTool",
        lambda: FakeCheapSharkTool({"黑神话": [{"sale_price": 300.0, "store_name": "Steam"}]}),
    )
    watch_repo = FakeWatchRepo([FakeWatch(1, "黑神话", 200.0)])
    alert_repo = FakeAlertRepo()

    monkeypatch.setattr("src.services.price_monitor_service.WatchlistRepository", lambda s: watch_repo)
    monkeypatch.setattr("src.services.price_monitor_service.PriceAlertRepository", lambda s: alert_repo)

    stats = await run_price_check(session_factory=_DummySessionFactory())
    assert stats == {"checked": 1, "triggered": 0, "skipped": 0}
    assert alert_repo.created == []


@pytest.mark.asyncio
async def test_no_active_watches(monkeypatch):
    watch_repo = FakeWatchRepo([])
    alert_repo = FakeAlertRepo()
    monkeypatch.setattr("src.services.price_monitor_service.WatchlistRepository", lambda s: watch_repo)
    monkeypatch.setattr("src.services.price_monitor_service.PriceAlertRepository", lambda s: alert_repo)

    stats = await run_price_check(session_factory=_DummySessionFactory())
    assert stats == {"checked": 0, "triggered": 0, "skipped": 0}


@pytest.mark.asyncio
async def test_api_failure_does_not_abort_round(monkeypatch):
    """单个监控项失败不中断整轮巡检"""
    class FlakyTool:
        async def _arun(self, title, on_sale=True):
            if title == "坏游戏":
                raise RuntimeError("api down")
            return [{"sale_price": 5.0, "store_name": "S"}]

    monkeypatch.setattr(
        "src.services.price_monitor_service.CheapSharkDealsTool", lambda: FlakyTool()
    )
    watch_repo = FakeWatchRepo([FakeWatch(1, "坏游戏", 50.0), FakeWatch(2, "好游戏", 50.0)])
    alert_repo = FakeAlertRepo()

    monkeypatch.setattr("src.services.price_monitor_service.WatchlistRepository", lambda s: watch_repo)
    monkeypatch.setattr("src.services.price_monitor_service.PriceAlertRepository", lambda s: alert_repo)

    stats = await run_price_check(session_factory=_DummySessionFactory())
    assert stats == {"checked": 2, "triggered": 1, "skipped": 0}