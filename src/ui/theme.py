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
        "--text": "#e8e8ff", "--text-dim": "#a6a6d4", "--border": "#3d3d70",
        "--glow": "0 0 12px rgba(255, 61, 129, .35)", "--radius": "12px",
    },
    "night": {  # 暗夜游戏风
        "--bg": "#0f1420", "--panel": "#171f31", "--panel-2": "#1e2942",
        "--accent1": "#2b4a9e", "--accent2": "#3b6ad8",
        "--ok": "#4ade80", "--warn": "#f0a03a", "--danger": "#ef4444",
        "--text": "#c8d3ea", "--text-dim": "#a0b2d6", "--border": "#3a4d7a",
        "--glow": "none", "--radius": "12px",
    },
    "light": {  # 明亮现代
        "--bg": "#f3f5fa", "--panel": "#ffffff", "--panel-2": "#f8fafc",
        "--accent1": "#3a6ff0", "--accent2": "#3a6ff0",
        "--ok": "#16a34a", "--warn": "#d97706", "--danger": "#dc2626",
        "--text": "#33415c", "--text-dim": "#46587a", "--border": "#ccd6ea",
        "--glow": "0 2px 8px rgba(0, 0, 0, .06)", "--radius": "12px",
    },
}

# 覆盖 Streamlit 原生控件的核心样式（全部引用变量）
_BASE_OVERRIDES = """
.stApp { background: var(--bg); color: var(--text); }
[data-testid="stSidebar"] { background: var(--panel); border-right: 1px solid var(--border); }
h1, h2, h3, h4 { color: var(--text); }
/* 默认按钮安静；仅 primary 用 accent 渐变（DeepSeek 式层级） */
.stButton > button, .stFormSubmitButton > button {
  background: var(--panel-2);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-weight: 500;
}
.stButton > button[kind="primary"],
.stFormSubmitButton > button[kind="primary"] {
  background: linear-gradient(135deg, var(--accent1), var(--accent2));
  color: #fff;
  border: none;
}
.stTextInput input, .stTextArea textarea, [data-baseweb="select"] > div {
  background: var(--panel-2); color: var(--text); border: 1px solid var(--border); border-radius: var(--radius);
}
.stTextInput input::placeholder { color: var(--text-dim); }
[data-testid="stDataFrame"] { background: var(--panel); }
hr { border-color: var(--border); }
[data-testid="stCaptionContainer"] { color: var(--text-dim); }
[data-testid="stDialog"] { color: var(--text); }
.stTextInput input::placeholder, .stTextArea textarea::placeholder { color: var(--text-dim); }
/* 复制误触清缓存弹窗：CSS 常驻隐藏（JS 拦截之外的兜底） */
[data-testid="stClearCacheDialog"] { display: none !important; }
/* 侧栏 Tab / 主题按钮：默认安静；当前 tab 用 primary 淡强调 */
[data-testid="stSidebar"] .stButton > button {
  text-align: left;
  justify-content: flex-start;
  margin: 2px 0;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
  border: 1px solid var(--accent1);
  color: var(--text);
  background: var(--panel-2);
}
"""

# 流式输出光标动画 + DeepSeek 风格聊天布局（颜色全走变量，UI 目录禁裸 HEX）
_EXTRA_ANIMATIONS = """
@keyframes blink {
  0% { opacity: 1; }
  50% { opacity: .2; }
  100% { opacity: 1; }
}

/* ── DeepSeek 风格对话区 ── */
.ds-chat-row-user {
  display: flex;
  justify-content: flex-end;
  margin: 10px 0;
}
.ds-bubble-user {
  max-width: 72%;
  background: linear-gradient(135deg, var(--accent1), var(--accent2));
  color: #fff;
  padding: 10px 16px;
  border-radius: 16px 16px 4px 16px;
  box-shadow: var(--glow);
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  line-height: 1.55;
}
.ds-welcome {
  text-align: center;
  padding: 48px 16px 24px;
}
.ds-welcome h1 {
  font-size: 1.85rem;
  font-weight: 600;
  margin: 0 0 8px;
  color: var(--text);
}
.ds-welcome .ds-sub {
  color: var(--text-dim);
  font-size: 0.95rem;
  margin-bottom: 28px;
}
.ds-progress {
  color: var(--text-dim);
  font-size: 12px;
  margin: 4px 0 2px 8px;
  opacity: 0.85;
}
/* 助手正文：加大行距，接近 DeepSeek 阅读感 */
[data-testid="stChatMessage"],
.element-container .stMarkdown {
  line-height: 1.65;
}
.ds-session-title {
  color: var(--text);
  font-size: 13px;
}
/* 会话列表：紧凑、左对齐、弱边框 —— DeepSeek 历史栏 */
.ds-sess-col .stButton > button {
  text-align: left;
  justify-content: flex-start;
  padding: 8px 12px;
  min-height: 2.2rem;
  font-size: 13px;
  border-radius: 10px;
  margin: 2px 0;
}
.ds-sess-col .stButton > button[kind="primary"] {
  /* 当前会话：淡底强调，不用大面积渐变 */
  background: var(--panel-2);
  border: 1px solid var(--accent1);
  color: var(--text);
}
.ds-sess-del .stButton > button {
  padding: 8px 0;
  min-width: 2.4rem;
  opacity: 0.75;
}
.ds-sess-del .stButton > button:hover {
  opacity: 1;
}
"""


def get_theme_css(theme: str) -> str:
    """主题名 → 完整 CSS 字符串（:root 变量 + 覆盖样式 + 动画）"""
    vars_ = THEME_VARS.get(theme, THEME_VARS[DEFAULT_THEME])
    var_block = ":root {\n" + "\n".join(f"  {k}: {v};" for k, v in vars_.items()) + "\n}"
    return var_block + "\n" + _BASE_OVERRIDES + "\n" + _EXTRA_ANIMATIONS


def inject_theme(theme: str) -> None:
    """向页面注入主题 CSS（同一主题只注入一次，避免每轮重插 style 引发 IME 闪烁）"""
    name = theme if theme in THEME_VARS else DEFAULT_THEME
    if st.session_state.get("_injected_theme") == name:
        return
    css = get_theme_css(name)
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    st.session_state["_injected_theme"] = name