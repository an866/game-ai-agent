"""异步工具 —— 同步↔异步桥接与事件循环方针的唯一实现处

方针（6aa30a7 + 本轮多消息卡死修复）：
SQLAlchemy / httpx / redis 异步客户端是进程级单例，只能绑在**一个**
存活的事件循环上。若每条消息 `asyncio.new_event_loop()`，第二条起
共享客户端会绑在已死 loop 上 → 挂死或 "Event loop is closed"。

因此本仓库约定：
1. 进程级**单一**后台事件循环（daemon 线程 `run_forever`），**永不 close**；
2. 所有异步工作（run_coro_sync / stream_sync / fire-and-forget）都投递到该 loop；
3. **禁止**在共享 loop 内再调用 `run_coro_sync`（会自等待死锁）——
   loop 内一律 `await`；同步侧才走本模块桥接。
"""

import asyncio
import threading
from typing import Awaitable, Callable, Coroutine, TypeVar

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: threading.Thread | None = None
_loop_lock = threading.Lock()


def get_loop() -> asyncio.AbstractEventLoop:
    """获取进程级共享事件循环（惰性启动，永不 close）"""
    global _loop, _loop_thread
    if _loop is not None and _loop.is_running():
        return _loop
    with _loop_lock:
        if _loop is not None and _loop.is_running():
            return _loop

        loop = asyncio.new_event_loop()

        def _run() -> None:
            asyncio.set_event_loop(loop)
            loop.run_forever()

        thread = threading.Thread(target=_run, daemon=True, name="agent-event-loop")
        thread.start()
        _loop = loop
        _loop_thread = thread
        return loop


def _on_shared_loop() -> bool:
    try:
        return asyncio.get_running_loop() is _loop
    except RuntimeError:
        return False


def run_coro_sync(coro_factory: Callable[[], Awaitable[T]], timeout: float = 120) -> T:
    """在共享事件循环上运行协程，同步等待结果。

    Args:
        coro_factory: 返回协程的可调用对象（协程只能被 await 一次，
            因此传入 factory 而非协程本身）
        timeout: 等待总超时

    Raises:
        RuntimeError: 已在共享 loop 内调用（会死锁）——调用方应直接 await
    """
    if _on_shared_loop():
        raise RuntimeError(
            "run_coro_sync 不能在共享事件循环内调用（会死锁）；请直接 await"
        )
    loop = get_loop()
    return asyncio.run_coroutine_threadsafe(coro_factory(), loop).result(timeout=timeout)


def submit_coro(coro: Coroutine) -> "asyncio.Future":
    """把协程投递到共享 loop，不等待结果（fire-and-forget）。

    返回 concurrent.futures.Future，可 `.result()` 阻塞取值；忽略即可后台执行。
    """
    return asyncio.run_coroutine_threadsafe(coro, get_loop())


async def run_sync_in_loop(fn: Callable[..., T], *args, **kwargs) -> T:
    """在事件循环内执行同步阻塞函数（feedparser/tavily 等），避免卡住循环"""
    return await asyncio.to_thread(fn, *args, **kwargs)
