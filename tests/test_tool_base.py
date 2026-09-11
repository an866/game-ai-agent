"""GameDataTool 基类 —— 缓存命中 / 重试 / 超时 / 缓存读写失败降级"""

import pytest
from pydantic import PrivateAttr

from src.tools.base import GameDataTool


class FakeRedis:
    def __init__(self, store: dict | None = None, fail_get=False, fail_set=False):
        self.store = store if store is not None else {}
        self.fail_get = fail_get
        self.fail_set = fail_set
        self.get_calls = 0
        self.setex_calls = 0

    async def get(self, key):
        self.get_calls += 1
        if self.fail_get:
            raise ConnectionError("redis down")
        return self.store.get(key)

    async def setex(self, key, ttl, value):
        self.setex_calls += 1
        if self.fail_set:
            raise ConnectionError("redis write down")
        self.store[key] = value


class CountingTool(GameDataTool):
    name: str = "counting_tool"
    description: str = "test tool"
    cache_ttl: int = 300
    max_retries: int = 3
    request_timeout: int = 5

    # pydantic 模型不允许随意设实例属性 → 用 PrivateAttr
    _call_count: int = PrivateAttr(default=0)
    _fail_times: int = PrivateAttr(default=0)
    _result: dict = PrivateAttr(default_factory=lambda: {"ok": True, "n": 1})

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def fail_times(self) -> int:
        return self._fail_times

    @fail_times.setter
    def fail_times(self, v: int) -> None:
        self._fail_times = v

    async def _fake_api(self, *args, **kwargs):
        self._call_count += 1
        if self._call_count <= self._fail_times:
            raise RuntimeError(f"api fail #{self._call_count}")
        return self._result

    async def _slow_api(self, *args, **kwargs):
        import asyncio

        self._call_count += 1
        await asyncio.sleep(10)
        return {"ok": True}

    async def _arun(self, *args, **kwargs):
        return await self._cached_call(self._fake_api, *args, **kwargs)


@pytest.fixture
def fake_redis(monkeypatch):
    store: dict = {}
    client = FakeRedis(store)

    async def _get_redis():
        return client

    monkeypatch.setattr("src.tools.base.get_redis", _get_redis)
    return client


class TestCache:
    @pytest.mark.asyncio
    async def test_cache_miss_then_hit(self, fake_redis):
        tool = CountingTool()
        r1 = await tool._arun("黑神话")
        r2 = await tool._arun("黑神话")
        assert r1 == r2 == {"ok": True, "n": 1}
        assert tool.call_count == 1  # 第二次走缓存
        assert fake_redis.setex_calls == 1
        assert fake_redis.get_calls == 2

    @pytest.mark.asyncio
    async def test_different_args_use_different_keys(self, fake_redis):
        tool = CountingTool()
        await tool._arun("黑神话")
        await tool._arun("原神")
        assert tool.call_count == 2
        assert len(fake_redis.store) == 2

    @pytest.mark.asyncio
    async def test_cache_key_stable_for_same_args(self):
        tool = CountingTool()
        k1 = tool._cache_key("黑神话", on_sale=True)
        k2 = tool._cache_key("黑神话", on_sale=True)
        assert k1 == k2
        assert k1.startswith("tool_cache:")

    @pytest.mark.asyncio
    async def test_cache_read_failure_still_calls_api(self, fake_redis):
        fake_redis.fail_get = True
        tool = CountingTool()
        result = await tool._arun("黑神话")
        assert result == {"ok": True, "n": 1}
        assert tool.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_write_failure_still_returns_result(self, fake_redis):
        fake_redis.fail_set = True
        tool = CountingTool()
        result = await tool._arun("黑神话")
        assert result == {"ok": True, "n": 1}
        assert tool.call_count == 1


class TestRetry:
    @pytest.mark.asyncio
    async def test_retry_until_success(self, fake_redis, monkeypatch):
        async def _no_sleep(_):
            return None

        monkeypatch.setattr("src.tools.base.asyncio.sleep", _no_sleep)

        tool = CountingTool(max_retries=3)
        tool.fail_times = 2
        result = await tool._arun("x")
        assert result == {"ok": True, "n": 1}
        assert tool.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises(self, fake_redis, monkeypatch):
        async def _no_sleep(_):
            return None

        monkeypatch.setattr("src.tools.base.asyncio.sleep", _no_sleep)

        tool = CountingTool(max_retries=2)
        tool.fail_times = 99
        with pytest.raises(RuntimeError, match="api fail"):
            await tool._arun("x")
        assert tool.call_count == 2

    @pytest.mark.asyncio
    async def test_timeout_raises_timeouterror(self, fake_redis, monkeypatch):
        # request_timeout 是 int；用 mock wait_for 避免真实等待
        import asyncio

        async def _fake_wait_for(coro, timeout=None):
            coro.close()
            raise asyncio.TimeoutError()

        monkeypatch.setattr("src.tools.base.asyncio.wait_for", _fake_wait_for)

        tool = CountingTool(max_retries=1, request_timeout=1)

        async def _api(*args, **kwargs):
            return {"ok": True}

        with pytest.raises(TimeoutError, match="请求超时"):
            await tool._cached_call(_api, "x")


class TestSoftWrap:
    @pytest.mark.asyncio
    async def test_soft_wrap_returns_error_dict_not_raise(self, fake_redis, monkeypatch):
        """HTTPStatusError 等不应打断 ReAct —— 包装后返回 ok=false 字典"""
        from src.tools.base import soft_wrap_tool

        async def _no_sleep(_):
            return None

        monkeypatch.setattr("src.tools.base.asyncio.sleep", _no_sleep)

        tool = CountingTool(max_retries=1)
        tool.fail_times = 99
        wrapped = soft_wrap_tool(tool)
        result = await wrapped._arun("x")
        assert isinstance(result, dict)
        assert result["ok"] is False
        assert result["tool"] == "counting_tool"
        assert "error" in result

    def test_soft_wrap_idempotent(self, fake_redis):
        from src.tools.base import soft_wrap_tool

        tool = CountingTool()
        once = soft_wrap_tool(tool)
        twice = soft_wrap_tool(once)
        assert once is twice
        assert getattr(twice, "_soft_wrapped", False) is True
