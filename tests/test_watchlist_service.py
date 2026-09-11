"""watchlist 服务 —— 列表/增删/未读告警/批量已读（fake repo）"""

from types import SimpleNamespace

import pytest

from src.services import watchlist_service as ws


class _DummySession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def commit(self):
        return None

    async def rollback(self):
        return None


class _DummySessionFactory:
    def __call__(self):
        return lambda: _DummySession()


class FakeWatchRepo:
    def __init__(self):
        self.items = []
        self.deleted = []

    async def get_all_active(self):
        return [i for i in self.items if i.status == "active"]

    async def add(self, game_name, target_price, steam_appid=None):
        item = SimpleNamespace(
            id=len(self.items) + 1,
            game_name=game_name,
            target_price=target_price,
            status="active",
            created_at="2026-09-09",
        )
        self.items.append(item)
        return item

    async def delete(self, watchlist_id):
        self.deleted.append(watchlist_id)
        self.items = [i for i in self.items if i.id != watchlist_id]


class FakeAlertRepo:
    def __init__(self):
        self.unread = []
        self.read_count = 0

    async def get_unread(self, limit=20):
        return self.unread[:limit]

    async def mark_all_read(self):
        n = len(self.unread)
        self.unread.clear()
        self.read_count += n
        return n


@pytest.fixture
def fakes(monkeypatch):
    watch = FakeWatchRepo()
    alert = FakeAlertRepo()
    monkeypatch.setattr(ws, "WatchlistRepository", lambda s: watch)
    monkeypatch.setattr(ws, "PriceAlertRepository", lambda s: alert)
    return watch, alert


@pytest.mark.asyncio
async def test_list_watches_empty(fakes):
    watch, _ = fakes
    assert await ws.list_watches(session_factory=_DummySessionFactory()) == []


@pytest.mark.asyncio
async def test_add_and_list_roundtrip(fakes):
    watch, _ = fakes
    factory = _DummySessionFactory()
    assert await ws.add_watch("黑神话", 200.0, session_factory=factory) is True
    items = await ws.list_watches(session_factory=factory)
    assert len(items) == 1
    assert items[0]["game_name"] == "黑神话"
    assert items[0]["target_price"] == 200.0
    assert items[0]["status"] == "active"


@pytest.mark.asyncio
async def test_delete_watch(fakes):
    watch, _ = fakes
    factory = _DummySessionFactory()
    await ws.add_watch("原神", 0.0, session_factory=factory)
    wid = watch.items[0].id
    assert await ws.delete_watch(wid, session_factory=factory) is True
    assert await ws.list_watches(session_factory=factory) == []


@pytest.mark.asyncio
async def test_unread_alerts_and_mark_all(fakes):
    _, alert = fakes
    factory = _DummySessionFactory()
    alert.unread = [
        SimpleNamespace(
            current_price=99.0,
            target_price=150.0,
            store_name="Steam",
            triggered_at="2026-09-09 12:00:00",
        )
    ]
    unread = await ws.list_unread_alerts(session_factory=factory)
    assert len(unread) == 1
    assert unread[0]["current_price"] == 99.0

    n = await ws.mark_all_alerts_read(session_factory=factory)
    assert n == 1
    assert await ws.list_unread_alerts(session_factory=factory) == []


@pytest.mark.asyncio
async def test_db_failure_returns_empty_or_false(monkeypatch):
    class BoomFactory:
        def __call__(self):
            raise ConnectionError("db down")

    monkeypatch.setattr(ws, "WatchlistRepository", lambda s: (_ for _ in ()).throw(RuntimeError()))
    assert await ws.list_watches(session_factory=BoomFactory()) == []
    assert await ws.add_watch("x", 1.0, session_factory=BoomFactory()) is False
    assert await ws.delete_watch(1, session_factory=BoomFactory()) is False
    assert await ws.list_unread_alerts(session_factory=BoomFactory()) == []
    assert await ws.mark_all_alerts_read(session_factory=BoomFactory()) == 0
