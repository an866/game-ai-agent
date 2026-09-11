"""LangGraph 整图编排 —— mock 各节点，验证路由分发与聚合结果"""

from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.agents import graph as graph_mod


@pytest.fixture
def _reset_graph(monkeypatch):
    """deps 中缓存的 graph 需要清掉，确保用 mock 节点重建"""
    import src.deps as deps

    deps.reset_all()
    yield
    deps.reset_all()


def _patch_nodes(monkeypatch, intent: str, final_response: str, called: list[str]):
    async def fake_router(state):
        called.append("router")
        return {"intent": intent, "game_name": state.get("game_name", "测试游戏")}

    def _mk(node_name):
        async def _fn(state):
            called.append(node_name)
            return {"final_response": final_response}

        return _fn

    original_aggregator = graph_mod.aggregator_node

    async def fake_aggregator(state):
        called.append("aggregator")
        return await original_aggregator(state)

    monkeypatch.setattr(graph_mod, "router_node", fake_router)
    for name, node in [
        ("query", "query_node"),
        ("price", "price_node"),
        ("recommend", "recommend_node"),
        ("news", "news_node"),
        ("general_chat", "general_chat_node"),
    ]:
        monkeypatch.setattr(graph_mod, node, _mk(name))
    monkeypatch.setattr(graph_mod, "aggregator_node", fake_aggregator)


async def _run_graph(monkeypatch, intent: str, final_response: str = "OK"):
    called: list[str] = []
    _patch_nodes(monkeypatch, intent, final_response, called)
    compiled = graph_mod.build_graph()
    result = await compiled.ainvoke(
        {"messages": [HumanMessage(content="黑神话多少钱")]}
    )
    return result, called


class TestGraphRouting:
    @pytest.mark.asyncio
    async def test_price_intent_routes_to_price_node(self, monkeypatch, _reset_graph):
        result, called = await _run_graph(monkeypatch, "price_check", "价格150")
        assert "price" in called
        assert "query" not in called
        assert "general_chat" not in called
        assert result["final_response"] == "价格150"
        assert isinstance(result["messages"][-1], AIMessage)
        assert result["messages"][-1].content == "价格150"

    @pytest.mark.asyncio
    async def test_game_query_routes_to_query_node(self, monkeypatch, _reset_graph):
        result, called = await _run_graph(monkeypatch, "game_query", "游戏信息")
        assert "query" in called
        assert "price" not in called

    @pytest.mark.asyncio
    async def test_recommend_routes_to_recommend_node(self, monkeypatch, _reset_graph):
        _, called = await _run_graph(monkeypatch, "recommend", "推荐列表")
        assert "recommend" in called

    @pytest.mark.asyncio
    async def test_news_routes_to_news_node(self, monkeypatch, _reset_graph):
        _, called = await _run_graph(monkeypatch, "news", "新闻摘要")
        assert "news" in called

    @pytest.mark.asyncio
    async def test_unknown_intent_falls_to_general(self, monkeypatch, _reset_graph):
        _, called = await _run_graph(monkeypatch, "totally_unknown", "闲聊")
        assert "general_chat" in called

    @pytest.mark.asyncio
    async def test_empty_final_response_fallback_message(self, monkeypatch, _reset_graph):
        result, _ = await _run_graph(monkeypatch, "general", final_response="")
        assert "抱歉" in result["messages"][-1].content


class TestGraphNodeFailure:
    @pytest.mark.asyncio
    async def test_node_exception_propagates_from_ainvoke(self, monkeypatch, _reset_graph):
        """当前图未对节点异常做捕获 —— 记录行为，防止静默吞错后行为漂移"""
        called: list[str] = []

        async def fake_router(state):
            return {"intent": "price_check"}

        async def fake_price(state):
            raise RuntimeError("工具全挂")

        monkeypatch.setattr(graph_mod, "router_node", fake_router)
        monkeypatch.setattr(graph_mod, "price_node", fake_price)

        compiled = graph_mod.build_graph()
        with pytest.raises(RuntimeError, match="工具全挂"):
            await compiled.ainvoke({"messages": [HumanMessage(content="hi")]})
