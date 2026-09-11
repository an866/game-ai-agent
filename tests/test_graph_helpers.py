"""LangGraph helper —— _build_messages / aggregator_node / 节点标签完备性"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.graph import (
    INTENT_ROUTE,
    NODE_LABELS,
    _build_messages,
    aggregator_node,
    route_by_intent,
)


class TestBuildMessages:
    def test_message_only(self):
        msgs = _build_messages("黑神话多少钱", None)
        assert len(msgs) == 1
        assert isinstance(msgs[0], HumanMessage)
        assert msgs[0].content == "黑神话多少钱"

    def test_history_roles_mapped(self):
        history = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "system", "content": "ctx"},
        ]
        msgs = _build_messages("继续", history)
        assert len(msgs) == 4
        assert isinstance(msgs[0], HumanMessage)
        assert isinstance(msgs[1], AIMessage)
        assert isinstance(msgs[2], SystemMessage)
        assert isinstance(msgs[3], HumanMessage)
        assert msgs[-1].content == "继续"

    def test_history_trimmed_to_keep(self):
        """长历史只保留最近 keep 条，降低每轮 prompt 体积"""
        history = [{"role": "user", "content": f"m{i}"} for i in range(20)]
        msgs = _build_messages("最新", history, history_keep=3)
        # 3 条历史 + 1 条新消息
        assert len(msgs) == 4
        assert msgs[0].content == "m17"
        assert msgs[-1].content == "最新"

    def test_summary_prepended_as_system(self):
        msgs = _build_messages("你好", None, summary="用户喜欢RPG")
        assert isinstance(msgs[0], SystemMessage)
        assert msgs[0].content == "用户喜欢RPG"
        assert isinstance(msgs[1], HumanMessage)

    def test_unknown_role_defaults_to_ai(self):
        msgs = _build_messages("x", [{"role": "tool", "content": "data"}])
        assert isinstance(msgs[0], AIMessage)


class TestAggregator:
    @pytest.mark.asyncio
    async def test_uses_final_response(self):
        result = await aggregator_node({"final_response": "推荐黑神话"})
        assert result["messages"][0].content == "推荐黑神话"
        assert isinstance(result["messages"][0], AIMessage)

    @pytest.mark.asyncio
    async def test_empty_final_response_fallback(self):
        result = await aggregator_node({})
        assert "抱歉" in result["messages"][0].content

    @pytest.mark.asyncio
    async def test_empty_string_fallback(self):
        result = await aggregator_node({"final_response": ""})
        assert "抱歉" in result["messages"][0].content


class TestRouteCoverage:
    def test_every_route_target_has_label(self):
        for target in INTENT_ROUTE.values():
            assert target in NODE_LABELS, f"节点 {target} 缺少进度标签"

    def test_intent_none_falls_back(self):
        assert route_by_intent({"intent": None}) == "general_chat"
