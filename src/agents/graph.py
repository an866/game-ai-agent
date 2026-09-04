"""LangGraph 多智能体编排 —— Supervisor 模式"""

from typing import TypedDict, Annotated, AsyncGenerator
from config.loader import get_agents_config

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from loguru import logger

from src.tools.web_search import WebSearchTool
from src.deps import get_graph as deps_get_graph, get_general_agent as deps_get_general_agent

from config.settings import get_settings

settings = get_settings()

prompts = get_agents_config()


class GameAgentState(TypedDict):
    """多智能体共享状态"""
    messages: Annotated[list[BaseMessage], add_messages]

    intent: str
    sub_intent: str
    game_name: str
    reasoning: str
    steam_appid: int

    query_result: dict
    price_result: dict
    recommend_result: list
    news_result: dict

    final_response: str



# ===== 节点函数 =====

async def router_node(state: GameAgentState) -> dict:
    """路由节点：意图识别"""
    from src.agents.router import build_router_chain

    route_fn = build_router_chain()
    result = route_fn(state)

    logger.info(f"路由: intent={result['intent']}, game={result.get('game_name', 'N/A')}, reason={result.get('reasoning', 'N/A')}")
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


def _create_general_agent():
    """构建通用对话 Agent (ReAct + WebSearch) —— 实例由 deps 缓存"""
    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=0.5,
        streaming=True,
    )
    tools = [WebSearchTool()]
    system_prompt = prompts["general"]["system_prompt"]
    agent = create_react_agent(model=llm, tools=tools, prompt=system_prompt)
    agent.max_iterations = 3
    return agent


def build_general_agent():
    """通用对话 Agent —— 单例由 deps 持有"""
    return deps_get_general_agent()


async def general_chat_node(state: GameAgentState) -> dict:
    """通用对话节点 —— 具备联网搜索能力"""
    agent = build_general_agent()
    messages = state.get("messages", [])
    user_input = messages[-1].content if messages else "你好"

    agent_messages = list(messages[:-1]) if len(messages) > 1 else []
    agent_messages.append(HumanMessage(content=user_input))
    result = await agent.ainvoke({"messages": agent_messages})
    response_messages = result.get("messages", [])
    final = response_messages[-1].content if response_messages else ""

    return {"final_response": final}


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


def get_graph():
    """编译后的 LangGraph —— 单例由 deps 持有"""
    return deps_get_graph()


def _build_messages(
    message: str,
    history: list[dict] | None,
    summary: str | None = None,
) -> list:
    """将对话历史 + 可选摘要转换为 LangChain 消息列表"""
    messages = []
    if summary:
        messages.append(SystemMessage(content=summary))
    if history:
        for h in history:
            role = h.get("role", "")
            if role == "user":
                messages.append(HumanMessage(content=h["content"]))
            elif role == "system":
                messages.append(SystemMessage(content=h["content"]))
            else:
                messages.append(AIMessage(content=h["content"]))
    messages.append(HumanMessage(content=message))
    return messages


# 节点标签 —— 用于流式进度展示
NODE_LABELS = {
    "router": "🔍 正在理解你的问题...",
    "query": "🎮 正在搜索游戏信息...",
    "price": "💰 正在查询价格...",
    "recommend": "🎯 正在生成推荐...",
    "news": "📰 正在检索新闻...",
    "general_chat": "💬 正在思考...",
    "aggregator": "📝 正在整理回复...",
}


async def chat_stream(
    message: str,
    history: list[dict] | None = None,
    summary: str | None = None,
) -> AsyncGenerator[dict, None]:
    """流式对话接口 —— 逐 token 产出事件字典。

    事件类型：
        {"type": "progress", "node": "query"}     — 进入新阶段
        {"type": "clear"}                         — 清空当前输出（Agent 内新一轮 LLM 调用开始）
        {"type": "token", "content": "..."}       — 文本 token
        {"type": "done", "response": "..."}       — 流结束，附带完整响应文本
        {"type": "error", "message": "..."}       — 错误

    Yields:
        事件字典，最终事件为 {"type": "done"} 或 {"type": "error"}
    """
    graph = get_graph()
    messages = _build_messages(message, history, summary=summary)
    full_response: str = ""

    try:
        async for event in graph.astream_events(
            {"messages": messages}, version="v2"
        ):
            kind = event["event"]
            name = event.get("name", "")
            metadata = event.get("metadata", {})

            # ── 进度事件：进入新的 graph 节点 ──
            if kind == "on_chain_start":
                node = metadata.get("langgraph_node", "")
                if node in NODE_LABELS:
                    yield {"type": "progress", "node": node}

            # ── 新 LLM 调用开始 → UI 清空上一段输出 ──
            if kind == "on_chat_model_start":
                # 仅在 agent 节点内部（非 Router）发出 clear
                parent_node = metadata.get("langgraph_node", "")
                if parent_node and parent_node != "router":
                    full_response = ""
                    yield {"type": "clear"}

            # ── 流式 token ──
            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                content = getattr(chunk, "content", "")
                if content:
                    full_response += content
                    yield {"type": "token", "content": content}

        yield {"type": "done", "response": full_response}

    except Exception as exc:
        logger.exception("流式对话异常")
        yield {"type": "error", "message": str(exc)}


async def chat(
    message: str,
    history: list[dict] | None = None,
    summary: str | None = None,
) -> str:
    """便捷对话接口（非流式，保持向后兼容）"""
    graph = get_graph()
    messages = _build_messages(message, history, summary=summary)

    result = await graph.ainvoke({"messages": messages})
    response_messages = result.get("messages", [])
    if response_messages:
        return response_messages[-1].content
    return result.get("final_response", "抱歉，出错了。")
