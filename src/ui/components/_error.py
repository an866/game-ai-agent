"""统一错误展示组件"""

import streamlit as st
from contextlib import contextmanager


@contextmanager
def show_error(fallback_message: str = "操作失败，请稍后重试"):
    """统一错误处理上下文管理器

    用法:
        with show_error("搜索失败"):
            results = fragile_operation()
    """
    try:
        yield
    except Exception as e:
        st.error(f"{fallback_message}: {e}")
