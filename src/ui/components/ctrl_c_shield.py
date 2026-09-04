"""Ctrl+C 拦截盾 —— Streamlit 清缓存快捷键与复制的冲突修复

背景：Streamlit 用 ReactHotkeys 绑定裸键 `c`（清缓存快捷键）。焦点不在
输入框时按 Ctrl+C（复制选中文本）也会命中该绑定，弹出 "Clear caches"
确认框，导致页面文本无法复制。官方无配置开关。

方案：无框架自定义组件（iframe 内脚本）在 parent document 的 capture
阶段截停「带修饰键的 c」，浏览器原生复制不受影响；裸 C 仍保留清缓存。

若跨域（iframe 无法访问 parent.document），拦截静默降级不影响渲染。
"""

from pathlib import Path

import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).parent / "static" / "ctrl_c_shield"
_ctrl_c_shield = components.declare_component(
    "ctrl_c_shield", path=str(_COMPONENT_DIR)
)


def render_ctrl_c_shield() -> None:
    """渲染拦截盾（app 主壳调用一次；0 高、无输入、无返回）"""
    _ctrl_c_shield(height=0)