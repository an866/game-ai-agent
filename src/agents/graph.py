"""LangGraph 多智能体编排 —— Supervisor 模式"""

from typing import TypedDict, Annotated
import yaml
from pathlib import Path

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from loguru import logger

from config.settings import get_settings

settings = get_settings()

config_path = Path(__file__).parent.parent.parent / "config" / "agents.yaml"
with open(config_path, encoding="utf-8") as f:
    prompts = yaml.safe_load(f)


class GameAgentState(TypedDict):
    """多智能体共享状态"""
    messages: Annotated[list[BaseMessage], add_messages]

    intent: str
    sub_intent: str
    game_name: str
    steam_appid: int

    query_result: dict
    price_result: dict
    recommend_result: list
    news_result: dict

    final_response: str


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=0.3,
    )


# ===== 节点函数 =====

async def router_node(state: GameAgentState) -> dict:
    """路由节点：意图识别"""
    from src.agents.router import build_router_chain

    route_fn = build_router_chain()
    result = route_fn(state)

    logger.info(f"路由: intent={result['intent']}, game={result.get('game_name', 'N/A')}")
    return result


async def query_node(state: GameAgentState) -> dict:
    """游戏查询节点"""
    from src.agents.query import run_query
    return await run_query(state)


async def price_node(state: GameAgentState) -> dict:
    """价格查询节点"""
    from src.agents.price import run_price
    return await run_price(state)


async def recommend_node(state: GameAgentState) -> dict:
    """游戏推荐节点"""
    from src.agents.recommend import run_recommend
    return await run_recommend(state)


async def news_node(state: GameAgentState) -> dict:
    """新闻聚合节点"""
    from src.agents.news import run_news
    return await run_news(state)


async def general_chat_node(state: GameAgentState) -> dict:
    """通用对话节点"""
    llm = get_llm()
    messages = state.get("messages", [])
    user_input = messages[-1].content if messages else "你好"

    system_prompt = prompts["general"]["system_prompt"]
    response = await llm.ainvoke([
        ("system", system_prompt),
        ("human", user_input),
    ])

    return {"final_response": response.content}


async def aggregator_node(state: GameAgentState) -> dict:
    """结果聚合节点"""
    response = state.get("final_response", "")
    if response:
        return {
            "messages": [AIMessage(content=response)],
        }
    return {"messages": [AIMessage(content="抱歉，我暂时无法处理这个请求。")]}


# ===== 路由函数 =====

def route_by_intent(state: GameAgentState) -> str:
    """根据意图分发到对应的专业 Agent"""
    intent = state.get("intent", "general")
    route_map = {
        "game_query": "query",
        "price_check": "price",
        "recommend": "recommend",
        "news": "news",
        "general": "general_chat",
    }
    target = route_map.get(intent, "general_chat")
    logger.info(f"分发: {intent} → {target}")
    return target


# ===== 构建图 =====

def build_graph() -> StateGraph:
    """构建 LangGraph 状态图"""
    workflow = StateGraph(GameAgentState)

    # 添加节点
    workflow.add_node("router", router_node)
    workflow.add_node("query", query_node)
    workflow.add_node("price", price_node)
    workflow.add_node("recommend", recommend_node)
    workflow.add_node("news", news_node)
    workflow.add_node("general_chat", general_chat_node)
    workflow.add_node("aggregator", aggregator_node)

    # 边
    workflow.add_edge(START, "router")

    workflow.add_conditional_edges(
        "router",
        route_by_intent,
        {
            "query": "query",
            "price": "price",
            "recommend": "recommend",
            "news": "news",
            "general_chat": "general_chat",
        },
    )

    workflow.add_edge("query", "aggregator")
    workflow.add_edge("price", "aggregator")
    workflow.add_edge("recommend", "aggregator")
    workflow.add_edge("news", "aggregator")
    workflow.add_edge("general_chat", "aggregator")

    workflow.add_edge("aggregator", END)

    return workflow.compile()


# 全局编译实例
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


async def chat(message: str, history: list[dict] | None = None) -> str:
    """便捷对话接口"""
    graph = get_graph()
    messages = []
    if history:
        for h in history:
            if h["role"] == "user":
                messages.append(HumanMessage(content=h["content"]))
            else:
                messages.append(AIMessage(content=h["content"]))
    messages.append(HumanMessage(content=message))

    result = await graph.ainvoke({"messages": messages})
    response_messages = result.get("messages", [])
    if response_messages:
        return response_messages[-1].content
    return result.get("final_response", "抱歉，出错了。")
