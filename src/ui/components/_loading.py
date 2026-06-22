"""统一 Loading 状态组件"""

import streamlit as st
from contextlib import contextmanager


@contextmanager
def show_loading(message: str = "加载中..."):
    """统一加载状态上下文管理器

    用法:
        with show_loading("搜索中..."):
            results = run_async_safe(search())
    """
    with st.spinner(message):
        yield
