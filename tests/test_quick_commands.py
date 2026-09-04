"""quick_commands 测试 —— 指令定义与填充逻辑"""

import streamlit as st
from src.ui.chat import quick_commands


class TestQuickCommands:
    def test_commands_defined(self):
        cmds = quick_commands.QUICK_COMMANDS
        assert isinstance(cmds, list) and len(cmds) >= 4
        labels = {c["label"] for c in cmds}
        assert {"💰 查价格", "🎯 找推荐", "📰 看新闻", "🔍 搜游戏"}.issubset(labels)

    def test_build_prompt(self):
        assert quick_commands.build_prompt("查价格", "黑神话") == "/price 黑神话"
        assert quick_commands.build_prompt("找推荐", "魂系") == "/recommend 魂系"
        assert quick_commands.build_prompt("看新闻", "") == "/news"