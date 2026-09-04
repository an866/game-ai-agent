"""全模块 import 断链回归测试

项目历史上多次发生"文件缺失导致 import 崩溃"未被发现（web_search.py、
stream_bridge.py、base.py 的 get_headers 曾因无测试而漏检）。
此测试枚举 src 与 scripts 下全部模块，逐个 import；
任何一个模块断链都会在此红。CLAUDE.md 将该测试列为 CI 级门槛。
"""

import importlib
import pkgutil
import sys
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).parent.parent / "src"


def _iter_modules(root: Path, package: str):
    """递归枚举包内所有 Python 模块名"""
    for mod_info in pkgutil.walk_packages([str(root)], prefix=f"{package}."):
        yield mod_info.name


def _module_list() -> list[str]:
    modules = ["src.main", "scripts.init_db"]
    for root, package in ((SRC_ROOT / "agents", "src.agents"),
                          (SRC_ROOT / "data", "src.data"),
                          (SRC_ROOT / "mcp", "src.mcp"),
                          (SRC_ROOT / "rag", "src.rag"),
                          (SRC_ROOT / "scheduler", "src.scheduler"),
                          (SRC_ROOT / "tools", "src.tools"),
                          (SRC_ROOT / "utils", "src.utils"),
                          (SRC_ROOT / "ui", "src.ui")):
        modules.extend(_iter_modules(root, package))
    return sorted(set(modules))


ALL_MODULES = _module_list()


@pytest.mark.parametrize("module_name", ALL_MODULES)
def test_module_imports(module_name: str):
    """每个模块都应能独立 import，不允许任何断链"""
    importlib.import_module(module_name)


def test_no_missing_modules():
    """模块枚举不应为空（防测试本身静默失效）"""
    assert len(ALL_MODULES) >= 30


def test_expected_symbols_present():
    """关键共享符号必须存在（历史断链点）"""
    from src.tools.base import GameDataTool, get_headers, get_http_client  # noqa: F401
    from src.tools.web_search import WebSearchTool  # noqa: F401
    from src.utils.stream_bridge import stream_sync  # noqa: F401