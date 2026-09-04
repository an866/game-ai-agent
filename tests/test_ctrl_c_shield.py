"""ctrl_c_shield 测试 —— 组件壳与静态资源完整性"""

from pathlib import Path

from src.ui.components import ctrl_c_shield


def test_component_assets_exist():
    """无框架组件依赖 index.html 存在（iframe 加载入口）"""
    index = Path(ctrl_c_shield._COMPONENT_DIR) / "index.html"
    assert index.exists()
    src = index.read_text(encoding="utf-8")
    assert "keydown" in src and "stopPropagation" in src


def test_render_function_signature():
    """渲染函数无参数、无返回值（0 高隐身盾）"""
    import inspect
    sig = inspect.signature(ctrl_c_shield.render_ctrl_c_shield)
    assert sig.parameters == {}


def test_shield_loaded_in_app_shell():
    """主壳必须渲染拦截盾（防集成丢失回归）"""
    app_src = Path("src/ui/app.py").read_text(encoding="utf-8")
    assert "render_ctrl_c_shield()" in app_src