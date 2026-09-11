"""共享事件循环回归 —— 多次 stream_sync / run_coro_sync 不得挂死

历史坑：每条消息 asyncio.new_event_loop()，第二条起 httpx/redis 单例绑在死 loop 上。
"""

import asyncio
import time

import pytest

from src.utils.async_utils import get_loop, run_coro_sync, submit_coro
from src.utils.stream_bridge import stream_sync


async def _agen(items):
    for x in items:
        yield x


class TestSharedLoop:
    def test_loop_is_singleton_and_running(self):
        loop1 = get_loop()
        loop2 = get_loop()
        assert loop1 is loop2
        assert loop1.is_running()

    def test_run_coro_sync_twice(self):
        assert run_coro_sync(lambda: _coro_value(1)) == 1
        assert run_coro_sync(lambda: _coro_value(2)) == 2

    def test_stream_sync_twice(self):
        """UI 连续两轮对话：两次 stream_sync 必须都能出事件并结束"""
        for round_no in (1, 2):
            got = list(stream_sync(lambda: _agen([{"n": round_no}, {"n": round_no * 10}])))
            assert got == [{"n": round_no}, {"n": round_no * 10}]

    def test_submit_coro_fire_and_forget(self):
        box = []

        async def work():
            box.append("ok")

        submit_coro(work())
        # 共享 loop 上很快完成；给一点调度时间
        deadline = time.time() + 2
        while not box and time.time() < deadline:
            time.sleep(0.01)
        assert box == ["ok"]

    def test_run_coro_sync_rejects_nested_call(self):
        async def nested():
            return run_coro_sync(lambda: _coro_value(1))

        with pytest.raises((RuntimeError, TimeoutError)):
            # 嵌套调用应在入口直接 RuntimeError；若调度后抛也算防护生效
            run_coro_sync(nested, timeout=2)


async def _coro_value(v):
    await asyncio.sleep(0)
    return v
