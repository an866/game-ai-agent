"""价格追踪 Agent —— 跨商店比价与降价提醒"""

from config.loader import get_agents_config
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from src.llm import get_llm
from langchain_core.messages import HumanMessage

from config.settings import get_settings
from src.tools.cheapshark import CheapSharkDealsTool
from src.tools.isthereanydeal import ITADLookupTool, ITADPricesTool, ITADHistoryTool

settings = get_settings()

prompts = get_agents_config()


def get_price_llm() -> ChatOpenAI:
    return get_llm("price")


def build_price_agent():
    """构建价格分析 Agent (ReAct)"""
    llm = get_price_llm()
    tools = [
        CheapSharkDealsTool(),
        ITADLookupTool(),
        ITADPricesTool(),
        ITADHistoryTool(),
    ]
    system_prompt = prompts["price"]["system_prompt"]
    return create_agent(model=llm, tools=tools, system_prompt=system_prompt)


async def run_price(state: dict) -> dict:
    """执行价格查询"""
    agent = build_price_agent()
    messages = state.get("messages", [])
    user_input = messages[-1].content if messages else ""
    game_name = state.get("game_name", "")

    query = f"查询游戏价格: {game_name}. {user_input}"

    agent_messages = list(messages[:-1]) if len(messages) > 1 else []
    agent_messages.append(HumanMessage(content=query))
    result = await agent.ainvoke({"messages": agent_messages})

    response_messages = result.get("messages", [])
    final = response_messages[-1].content if response_messages else ""
    return {
        "price_result": result,
        "final_response": final,
    }