"""异步生成器 → 同步生成器的线程桥接

Streamlit 运行在同步上下文（Tornado），而 LangGraph 的
astream_events 是异步生成器。此模块提供一个线程安全的桥接，
让 Streamlit 可以逐事件消费异步流。

用法：
    for event in stream_sync(lambda: chat_stream(prompt, history)):
        if event["type"] == "token":
            ...
"""

import asyncio
import queue
import threading
from typing import Callable, AsyncGenerator, Generator, TypeVar

T = TypeVar("T")


def stream_sync(
    factory: Callable[[], AsyncGenerator[T, None]],
    timeout: float = 120,
) -> Generator[T, None, None]:
    """在独立线程中运行异步生成器，通过 Queue 将事件同步传递给主线程。

    Args:
        factory: 返回异步生成器的可调用对象（lambda 或函数引用）
        timeout: 等待流中下一个事件的最大秒数，超时后终止

    Yields:
        异步生成器产出的每一项

    Raises:
        RuntimeError: 流中发生任何未捕获异常时抛出
    """
    q: queue.Queue = queue.Queue()

    async def _runner() -> None:
        try:
            async for item in factory():
                q.put(("item", item))
            q.put(("done", None))
        except Exception as exc:
            q.put(("error", exc))

    def _thread_target() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_runner())
        # 注意：故意不调用 loop.close()。
        # 线程内会执行 chat_stream → SQLAlchemy 异步引擎。
        # close loop 后引擎析构时清理连接池会触发
        # "Event loop is closed" 崩溃（见 6aa30a7 的修复与教训）。
        # loop 由 GC/进程退出时回收。

    thread = threading.Thread(target=_thread_target, daemon=True)
    thread.start()

    while True:
        try:
            kind, value = q.get(timeout=timeout)
        except queue.Empty:
            break

        if kind == "done":
            break
        elif kind == "error":
            raise RuntimeError(f"流式处理异常: {value}") from value
        else:
            yield value