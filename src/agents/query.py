"""游戏查询 Agent —— 获取游戏详细信息（多游戏对比 + 工具软失败）"""

from loguru import logger

from config.loader import get_agents_config
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from config.settings import get_settings
from src.deps import get_query_agent as deps_get_query_agent
from src.llm import get_llm
from src.tools.base import soft_wrap_tools
from src.tools.steam_api import SteamSearchTool, SteamDetailTool, SteamCurrentPlayersTool
from src.tools.rawg import RAWGGameSearchTool, RAWGGameDetailTool, RAWGGameScreenshotsTool
from src.tools.web_search import WebSearchTool

settings = get_settings()

prompts = get_agents_config()


def get_query_llm() -> ChatOpenAI:
    return get_llm("query")


def _create_query_agent():
    """构建游戏查询 Agent (ReAct) —— 实例由 deps 缓存

    - 工具软失败：HTTPStatusError 不再打断整轮（对比多游戏时尤其关键）
    - 含 WebSearch：prompt 已引用，此前漏挂导致模型无法兜底
    """
    llm = get_query_llm()
    tools = soft_wrap_tools([
        SteamSearchTool(),
        SteamDetailTool(),
        SteamCurrentPlayersTool(),
        RAWGGameSearchTool(),
        RAWGGameDetailTool(),
        RAWGGameScreenshotsTool(),
        WebSearchTool(),
    ])
    system_prompt = prompts["query"]["system_prompt"]
    return create_agent(model=llm, tools=tools, system_prompt=system_prompt)


def build_query_agent():
    """游戏查询 Agent —— 单例由 deps 持有"""
    return deps_get_query_agent()


async def _web_fallback(user_input: str) -> str:
    """agent 整轮失败时的联网降级回复"""
    try:
        from src.tools.web_search import search_web
        hits = await search_web(user_input, max_results=5)
        lines = []
        for h in hits[:5]:
            title = h.get("title") or ""
            snippet = (h.get("snippet") or "")[:160]
            if title:
                lines.append(f"- **{title}**：{snippet}")
        if lines:
            return (
                "内置游戏库暂时不可用，以下是联网检索到的相关信息（请以官方为准）：\n\n"
                + "\n".join(lines)
            )
    except Exception as exc:
        logger.warning(f"联网兜底也失败: {exc}")
    return "游戏信息服务暂时不可用，请稍后再试。"


async def run_query(state: dict, query: str | None = None) -> dict:
    """执行游戏查询"""
    agent = build_query_agent()
    messages = state.get("messages", [])
    user_input = query or (messages[-1].content if messages else "")

    agent_messages = list(messages[:-1]) if len(messages) > 1 else []
    agent_messages.append(HumanMessage(content=user_input))
    try:
        result = await agent.ainvoke({"messages": agent_messages})
    except Exception as exc:
        logger.exception("查询 agent 失败，走联网兜底")
        return {
            "query_result": {},
            "final_response": await _web_fallback(user_input),
        }

    response_messages = result.get("messages", [])
    final = response_messages[-1].content if response_messages else ""
    if not final or not str(final).strip():
        final = await _web_fallback(user_input)
    return {
        "query_result": result,
        "final_response": final,
    }
