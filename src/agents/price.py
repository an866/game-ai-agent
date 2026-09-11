"""价格追踪 Agent —— 跨商店比价与降价提醒"""

from config.loader import get_agents_config
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from config.settings import get_settings
from src.deps import get_price_agent as deps_get_price_agent
from src.llm import get_llm
from src.tools.base import soft_wrap_tools
from src.tools.cheapshark import CheapSharkDealsTool
from src.tools.isthereanydeal import ITADLookupTool, ITADPricesTool, ITADHistoryTool

settings = get_settings()

prompts = get_agents_config()


def get_price_llm() -> ChatOpenAI:
    return get_llm("price")


def _create_price_agent():
    """构建价格分析 Agent (ReAct) —— 实例由 deps 缓存

    ITAD 需要 API Key；未配置时只挂 CheapShark，避免空 key 触发 404 打断整条链路。
    """
    llm = get_price_llm()
    tools: list = [CheapSharkDealsTool()]
    if get_settings().itad_api_key:
        tools.extend([
            ITADLookupTool(),
            ITADPricesTool(),
            ITADHistoryTool(),
        ])
    tools = soft_wrap_tools(tools)
    system_prompt = prompts["price"]["system_prompt"]
    return create_agent(model=llm, tools=tools, system_prompt=system_prompt)


def build_price_agent():
    """价格分析 Agent —— 单例由 deps 持有"""
    return deps_get_price_agent()


async def run_price(state: dict) -> dict:
    """执行价格查询"""
    agent = build_price_agent()
    messages = state.get("messages", [])
    user_input = messages[-1].content if messages else ""
    game_name = state.get("game_name", "")

    query = f"查询游戏价格: {game_name}. {user_input}"

    agent_messages = list(messages[:-1]) if len(messages) > 1 else []
    agent_messages.append(HumanMessage(content=query))
    try:
        result = await agent.ainvoke({"messages": agent_messages})
    except Exception as exc:
        from loguru import logger
        logger.exception("价格 agent 失败")
        return {
            "price_result": {},
            "final_response": (
                f"价格服务暂时不可用（{type(exc).__name__}），请稍后再试。"
            ),
        }

    response_messages = result.get("messages", [])
    final = response_messages[-1].content if response_messages else ""
    return {
        "price_result": result,
        "final_response": final,
    }
