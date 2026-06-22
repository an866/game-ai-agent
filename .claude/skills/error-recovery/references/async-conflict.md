# Async Event Loop Conflict

## 错误签名
```
'NoneType' object has no attribute 'send'
```
Streamlit 刷新时报 asyncio 错误。

## 根因
`asyncio.run()` 与 Streamlit 的 Tornado 事件循环冲突。

## 已验证解法
用 `run_async_safe()` 替代所有 `asyncio.run()`：
```python
from src.ui.session_state import run_async_safe

@st.cache_data(ttl=5, show_spinner=False)
def load_data(_cache_buster: int = 0):
    async def _run():
        ...
    return run_async_safe(_run())
```
返回 dict 而非 ORM 对象。
