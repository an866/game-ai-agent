"""统计数字卡 —— 概览面板用（颜色全走主题变量）"""

import streamlit as st


def render_metric_card(label: str, value: str, icon: str = "", help: str | None = None) -> None:
    """霓虹渐变数字卡"""
    st.markdown(
        f"""
        <div style="background: var(--panel); border: 1px solid var(--border);
                    border-radius: var(--radius); padding: 14px 16px;
                    border-top: 3px solid var(--accent1);">
          <div style="color: var(--text-dim); font-size: 13px;">{icon} {label}</div>
          <div style="color: var(--text); font-size: 26px; font-weight: 700;
                      margin-top: 4px;">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if help:
        st.caption(help)