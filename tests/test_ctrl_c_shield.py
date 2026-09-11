"""ctrl_c_shield 测试 —— 一次注入 + IME 友好 + 主题 CSS 兜底"""

from pathlib import Path

from src.ui import theme
from src.ui.components import ctrl_c_shield


def test_shield_script_blocks_modifiers():
    src = ctrl_c_shield._SHIELD_JS
    assert "stopImmediatePropagation" in src
    assert "ctrlKey" in src or "metaKey" in src
    assert '"c"' in src and '"x"' in src
    # IME 组字中不拦截
    assert "isComposing" in src
    assert "preventDefault()" not in src


def test_no_mutation_observer_ime_safe():
    """禁止全页 MutationObserver —— 打字时 DOM 抖动会导致输入法候选框闪烁"""
    src = ctrl_c_shield._SHIELD_JS
    assert "MutationObserver" not in src
    assert "setInterval" in src


def test_render_injects_once():
    """每会话只注入一次，避免每轮 st.html 重插脚本"""
    src = Path(ctrl_c_shield.__file__).read_text(encoding="utf-8")
    assert "_ctrl_c_shield_injected" in src
    assert "st.html" in src


def test_theme_hides_clear_cache_dialog_css():
    css = theme.get_theme_css("neon")
    assert "stClearCacheDialog" in css
    assert "display: none" in css


def test_theme_inject_once_per_name():
    src = Path(theme.__file__).read_text(encoding="utf-8")
    assert "_injected_theme" in src


def test_shield_loaded_in_app_shell():
    app_src = Path("src/ui/app.py").read_text(encoding="utf-8")
    assert "render_ctrl_c_shield()" in app_src
