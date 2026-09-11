"""集成测试 —— 真实 MySQL / Redis。默认被 pytest.ini 排除。

跑法：
    py -3.14 -m pytest -m integration -q
    SMOKE_DB=1 py -3.14 scripts/smoke_check.py

注意：pytest-asyncio 默认 function 级事件循环，SQLAlchemy 连接池不可跨循环复用。
每个用例开头 reset_all()，确保在本用例的 loop 上新建 engine/session。
"""

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _fresh_deps():
    from src.deps import reset_all

    reset_all()
    yield
    # 不 dispose：由下一次 reset_all 丢弃引用，避免跨 loop 关闭连接
    reset_all()


@pytest.mark.asyncio
async def test_mysql_engine_connect_and_select_1():
    from sqlalchemy import text

    from src.deps import get_engine

    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_mysql_tables_exist_or_init():
    """表应已存在（init-db 后）；否则说明环境未初始化"""
    from sqlalchemy import text

    from src.deps import get_engine

    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text("SHOW TABLES"))
        tables = {row[0] for row in result}

    expected = {"watchlist", "price_alerts", "user_preferences", "chat_history"}
    missing = expected - tables
    assert not missing, f"缺少表（先跑 init-db）: {missing}"


@pytest.mark.asyncio
async def test_chat_history_roundtrip():
    """真实 DB 写读回"""
    import uuid

    from src.services.chat_service import ChatService

    svc = ChatService()
    sid = f"itest_{uuid.uuid4().hex[:12]}"
    ok = await svc.save_message(sid, "user", "集成测试消息", intent="general")
    assert ok is True

    msgs = await svc.load_recent(sid, limit=5)
    assert any(m["content"] == "集成测试消息" for m in msgs)


@pytest.mark.asyncio
async def test_redis_ping_and_cache_roundtrip():
    import json

    from src.data.redis_client import get_redis
    from src.tools.base import GameDataTool

    class _T(GameDataTool):
        name: str = "itest_tool"
        description: str = "itest"

        async def _arun(self, *args, **kwargs):
            return await self._cached_call(self._api, *args, **kwargs)

        async def _api(self, *args, **kwargs):
            return {"hello": "redis"}

    redis = await get_redis()
    assert await redis.ping() is True

    tool = _T()
    r1 = await tool._arun("itest")
    r2 = await tool._arun("itest")
    assert r1 == r2 == {"hello": "redis"}

    key = tool._cache_key("itest")
    raw = await redis.get(key)
    assert raw is not None
    assert json.loads(raw)["hello"] == "redis"
    await redis.delete(key)


@pytest.mark.asyncio
async def test_watchlist_service_against_real_db():
    import uuid

    from src.services import watchlist_service as ws

    name = f"集成临时游戏_{uuid.uuid4().hex[:8]}"
    added = await ws.add_watch(name, 123.0)
    assert added is True

    items = await ws.list_watches()
    match = [i for i in items if i["game_name"] == name]
    assert match, "刚添加的监控项应出现在列表中"

    wid = match[0]["id"]
    assert await ws.delete_watch(wid) is True
    items2 = await ws.list_watches()
    assert all(i["id"] != wid for i in items2)
