"""统一错误展示组件"""

import streamlit as st
from contextlib import contextmanager
from loguru import logger


@contextmanager
def show_error(fallback_message: str = "操作失败，请稍后重试"):
    """统一错误处理上下文管理器"""
    try:
        yield
    except Exception as e:
        logger.exception(f"{fallback_message}: {e}")
        st.error(f"{fallback_message}: {e}")