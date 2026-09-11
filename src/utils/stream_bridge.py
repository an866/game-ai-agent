"""异步生成器 → 同步生成器的桥接

Streamlit 运行在同步上下文（Tornado），而 LangGraph 的
astream_events 是异步生成器。此模块把异步流投递到**共享事件循环**
（见 async_utils），通过 Queue 将事件同步传回主线程。

用法：
    for event in stream_sync(lambda: chat_stream(prompt, history)):
        if event["type"] == "token":
            ...
"""

import asyncio
import queue
from typing import Callable, AsyncGenerator, Generator, TypeVar

from src.utils.async_utils import get_loop

T = TypeVar("T")


def stream_sync(
    factory: Callable[[], AsyncGenerator[T, None]],
    timeout: float = 120,
) -> Generator[T, None, None]:
    """在共享事件循环上运行异步生成器，通过 Queue 同步消费。

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

    # 投递到共享 loop，避免每条消息 new_event_loop 导致共享客户端绑死旧 loop
    asyncio.run_coroutine_threadsafe(_runner(), get_loop())

    while True:
        try:
            kind, value = q.get(timeout=timeout)
        except queue.Empty:
            # 超时必须显式失败——静默 break 会让 UI 永远停在「正在检索…」
            raise RuntimeError(f"流式超时：{timeout}s 内无新事件") from None

        if kind == "done":
            break
        elif kind == "error":
            raise RuntimeError(f"流式处理异常: {value}") from value
        else:
            yield value
