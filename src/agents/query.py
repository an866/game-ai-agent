"""游戏查询 Agent —— 获取游戏详细信息"""

from config.loader import get_agents_config
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from src.llm import get_llm
from langchain_core.messages import HumanMessage

from config.settings import get_settings
from src.tools.steam_api import SteamSearchTool, SteamDetailTool, SteamCurrentPlayersTool
from src.tools.rawg import RAWGGameSearchTool, RAWGGameDetailTool, RAWGGameScreenshotsTool

settings = get_settings()

prompts = get_agents_config()


def get_query_llm() -> ChatOpenAI:
    return get_llm("query")


def build_query_agent():
    """构建游戏查询 Agent (ReAct)

    langchain 1.x 使用 create_agent（内部即 ReAct 循环，
    工具列表自动注入，不再需要手写 {tools} 模板）。
    """
    llm = get_query_llm()
    tools = [
        SteamSearchTool(),
        SteamDetailTool(),
        SteamCurrentPlayersTool(),
        RAWGGameSearchTool(),
        RAWGGameDetailTool(),
        RAWGGameScreenshotsTool(),
    ]
    system_prompt = prompts["query"]["system_prompt"]
    return create_agent(model=llm, tools=tools, system_prompt=system_prompt)


async def run_query(state: dict, query: str | None = None) -> dict:
    """执行游戏查询"""
    agent = build_query_agent()
    messages = state.get("messages", [])
    user_input = query or (messages[-1].content if messages else "")

    agent_messages = list(messages[:-1]) if len(messages) > 1 else []
    agent_messages.append(HumanMessage(content=user_input))
    result = await agent.ainvoke({"messages": agent_messages})

    response_messages = result.get("messages", [])
    final = response_messages[-1].content if response_messages else ""
    return {
        "query_result": result,
        "final_response": final,
    }