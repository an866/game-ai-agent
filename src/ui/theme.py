"""主题系统 —— 三套 CSS 变量 + 运行时注入

设计决策（spec D7/D2）：CSS 变量 + :root 注入，不依赖 Streamlit 内置主题；
三套皮肤由同一份覆盖样式驱动，颜色全部走变量。
UI 代码（components/panels/chat/app）禁止裸 HEX —— tests/test_theme.py 扫描。
"""

import streamlit as st

DEFAULT_THEME = "neon"

THEME_VARS: dict[str, dict[str, str]] = {
    "neon": {   # 霓虹电竞（默认）
        "--bg": "#0a0a12", "--panel": "#12121e", "--panel-2": "#181834",
        "--accent1": "#ff3d81", "--accent2": "#a855f7",
        "--ok": "#22d3ee", "--warn": "#f0a03a", "--danger": "#ff5d5d",
        "--text": "#e8e8ff", "--text-dim": "#8a8ab8", "--border": "#2a2a55",
        "--glow": "0 0 12px rgba(255, 61, 129, .35)", "--radius": "12px",
    },
    "night": {  # 暗夜游戏风
        "--bg": "#0f1420", "--panel": "#171f31", "--panel-2": "#1e2942",
        "--accent1": "#2b4a9e", "--accent2": "#3b6ad8",
        "--ok": "#4ade80", "--warn": "#f0a03a", "--danger": "#ef4444",
        "--text": "#c8d3ea", "--text-dim": "#8a97b8", "--border": "#2c3c61",
        "--glow": "none", "--radius": "12px",
    },
    "light": {  # 明亮现代
        "--bg": "#f3f5fa", "--panel": "#ffffff", "--panel-2": "#f8fafc",
        "--accent1": "#3a6ff0", "--accent2": "#3a6ff0",
        "--ok": "#16a34a", "--warn": "#d97706", "--danger": "#dc2626",
        "--text": "#33415c", "--text-dim": "#5a6b8a", "--border": "#e0e5f0",
        "--glow": "0 2px 8px rgba(0, 0, 0, .06)", "--radius": "12px",
    },
}

# 覆盖 Streamlit 原生控件的核心样式（全部引用变量）
_BASE_OVERRIDES = """
.stApp { background: var(--bg); color: var(--text); }
[data-testid="stSidebar"] { background: var(--panel); border-right: 1px solid var(--border); }
h1, h2, h3, h4 { color: var(--text); }
.stButton > button, .stFormSubmitButton > button {
  background: linear-gradient(135deg, var(--accent1), var(--accent2));
  color: #fff; border: none; border-radius: var(--radius);
}
.stTextInput input, .stTextArea textarea, [data-baseweb="select"] > div {
  background: var(--panel-2); color: var(--text); border: 1px solid var(--border); border-radius: var(--radius);
}
.stTextInput input::placeholder { color: var(--text-dim); }
[data-testid="stDataFrame"] { background: var(--panel); }
hr { border-color: var(--border); }
"""


def get_theme_css(theme: str) -> str:
    """主题名 → 完整 CSS 字符串（:root 变量 + 覆盖样式）"""
    vars_ = THEME_VARS.get(theme, THEME_VARS[DEFAULT_THEME])
    var_block = ":root {\n" + "\n".join(f"  {k}: {v};" for k, v in vars_.items()) + "\n}"
    return var_block + "\n" + _BASE_OVERRIDES + "\n"


def inject_theme(theme: str) -> None:
    """向页面注入主题 CSS（非法主题名回退默认霓虹）"""
    css = get_theme_css(theme if theme in THEME_VARS else DEFAULT_THEME)
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)