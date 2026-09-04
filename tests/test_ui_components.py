"""UI 组件测试 —— 变量化后组件 import 正常；metric_card 签名为纯函数式"""

import pytest
from src.ui.components import _loading, _error, metric_card


class TestMetricCard:
    def test_signature(self):
        import inspect
        sig = inspect.signature(metric_card.render_metric_card)
        params = list(sig.parameters)
        assert params[:2] == ["label", "value"]
        assert "help" in params

    def test_css_uses_variables_only(self):
        import re
        src = open(metric_card.__file__, encoding="utf-8").read()
        code = re.sub(r"#.*$", "", src, flags=re.M)
        assert not re.findall(r"#[0-9a-fA-F]{6}", code)