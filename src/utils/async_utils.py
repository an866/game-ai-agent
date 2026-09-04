"""异步工具 —— 同步↔异步桥接与事件循环方针的唯一实现处

方针（6aa30a7 验证过的教训）：SQLAlchemy 异步引擎析构时会清理连接池，
如果其创建时所在的事件循环已被 close，会抛 "Event loop is closed" 崩溃。
因此本仓库约定：
1. 线程内每次任务创建新的事件循环，**不调用 loop.close()**，交由 GC 回收；
2. 线程池为进程级单例（避免 Streamlit 高频 rerun 时反复创建线程池）。
"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")

_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        with _executor_lock:
            if _executor is None:
                # Streamlit 单线程 rerun 天然串行；如需并行 rerun 再调大
                _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent-bridge")
    return _executor


def run_coro_sync(coro_factory: Callable[[], Awaitable[T]], timeout: float = 120) -> T:
    """在独立线程的新事件循环中运行协程，同步等待结果。

    Args:
        coro_factory: 返回协程的可调用对象（协程只能被 await 一次，
            因此传入 factory 而非协程本身，供 _get_executor 重试场景复用）
        timeout: 等待总超时
    """
    def _run() -> T:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # 注意：故意不 loop.close() —— SQLAlchemy 异步引擎析构需要
        # 存活的事件循环（见模块 docstring），loop 由 GC/进程退出回收。
        return loop.run_until_complete(coro_factory())

    return _get_executor().submit(_run).result(timeout=timeout)


async def run_sync_in_loop(fn: Callable[..., T], *args, **kwargs) -> T:
    """在事件循环内执行同步阻塞函数（feedparser/tavily 等），避免卡住循环"""
    return await asyncio.to_thread(fn, *args, **kwargs)