"""统一加载指示组件"""

import streamlit as st
from contextlib import contextmanager


@contextmanager
def show_loading(message: str = "加载中..."):
    """统一加载指示（spinner 样式由主题变量驱动）"""
    with st.spinner(message):
        yield