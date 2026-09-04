"""theme 单元测试 —— 变量表完整性、键一致性、裸 HEX 扫描"""

import io
import re
import tokenize

import pytest
from src.ui import theme


def _strip_comments(src: str) -> str:
    """仅剥离 Python 注释（保留字符串字面量内容，让裸 HEX 可以被扫出）"""
    try:
        tokens = tokenize.generate_tokens(io.StringIO(src).readline)
        return "".join(tok.string for tok in tokens if tok.type != tokenize.COMMENT)
    except tokenize.TokenError:
        return src


class TestThemeVariables:
    def test_three_themes_default_neon(self):
        assert set(theme.THEME_VARS.keys()) == {"neon", "night", "light"}
        assert theme.DEFAULT_THEME == "neon"

    def test_all_themes_have_same_keys(self):
        keys = [frozenset(v) for v in theme.THEME_VARS.values()]
        assert len(set(keys)) == 1, "三套主题变量键必须完全一致"

    def test_required_keys_present(self):
        required = {"--bg", "--panel", "--panel-2", "--accent1", "--accent2",
                    "--ok", "--warn", "--danger", "--text", "--text-dim",
                    "--border", "--glow", "--radius"}
        for name, vars_ in theme.THEME_VARS.items():
            missing = required - set(vars_)
            assert not missing, f"主题 {name} 缺变量: {missing}"

    def test_hex_values_are_valid(self):
        hex_re = re.compile(r"^#[0-9a-fA-F]{6}$")
        for name, vars_ in theme.THEME_VARS.items():
            for key, val in vars_.items():
                if key in ("--glow", "--radius"):  # 非颜色变量（阴影/圆角）
                    continue
                assert hex_re.match(val), f"{name}/{key} 非法颜色: {val}"

    def test_get_theme_css_injects_all_variables(self):
        css = theme.get_theme_css("neon")
        for key in theme.THEME_VARS["neon"]:
            assert key in css
        assert ":root" in css


class TestNoBareHexInUI:
    """硬性约定：UI 代码禁止裸 HEX（theme.py 本身除外）"""

    UI_DIRS = [
        "src/ui/components", "src/ui/panels", "src/ui/chat",
        "src/ui/_pages", "src/ui/app.py",
    ]

    @pytest.mark.parametrize("path", [
        p for d in UI_DIRS
        for p in [__import__("pathlib").Path(d)]
        if p.exists()
        for p in ([p] if p.is_file() else p.rglob("*.py"))
    ])
    def test_no_bare_hex(self, path):
        src = path.read_text(encoding="utf-8")
        # 剥离 Python 注释；字符串字面量/CSS 内的 HEX 仍会被扫出
        code = _strip_comments(src)
        hits = re.findall(r'#[0-9a-fA-F]{6}', code)
        assert not hits, f"{path} 含裸 HEX: {hits}"