"""快捷指令 —— 输入框上方的行为胶囊（点击即发送对应指令，模板空位由 LLM 补全）"""

import streamlit as st

# label（含图标前缀）→ 对应文本指令模板（{} 为游戏名占位）
QUICK_COMMANDS = [
    {"label": "💰 查价格", "template": "/price {name}"},
    {"label": "🎯 找推荐", "template": "/recommend {name}"},
    {"label": "📰 看新闻", "template": "/news {name}"},
    {"label": "🔍 搜游戏", "template": "/search {name}"},
]


def _bare(label: str) -> str:
    """去掉图标前缀：'💰 查价格' → '查价格'"""
    return label.split(" ", 1)[-1].strip()


def build_prompt(label: str, game_name: str = "") -> str:
    """指令 label（带或不带图标前缀均可）+ 游戏名 → 文本指令"""
    bare = _bare(label)
    for c in QUICK_COMMANDS:
        if bare == _bare(c["label"]):
            return c["template"].format(name=game_name.strip()).strip()
    return ""


def render_quick_commands() -> None:
    """渲染快捷指令胶囊行；点击写入 draft，chat_panel 下一 run 即点即发"""
    from src.ui import ui_state

    cols = st.columns(len(QUICK_COMMANDS))
    for col, cmd in zip(cols, QUICK_COMMANDS):
        with col:
            if st.button(cmd["label"], key=f"qc_{cmd['label']}", use_container_width=True):
                ui_state.update_panel_state("chat", {"draft": build_prompt(cmd["label"])})
                st.rerun()