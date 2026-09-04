"""游戏推荐 Agent —— 根据用户偏好推荐类似游戏"""

from config.loader import get_agents_config
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from config.settings import get_settings
from src.agents.memory import build_profile_text
from src.tools.rawg import RAWGGameSearchTool, RAWGGameRecommendationsTool, RAWGGameDetailTool
from src.deps import get_recommend_agent as deps_get_recommend_agent
from src.tools.web_search import WebSearchTool

settings = get_settings()

prompts = get_agents_config()


def get_recommend_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=0.7,
        streaming=True,
    )


def _create_recommend_agent():
    """构建游戏推荐 Agent (ReAct) —— 实例由 deps 缓存"""
    llm = get_recommend_llm()
    tools = [
        WebSearchTool(),
        RAWGGameSearchTool(),
        RAWGGameRecommendationsTool(),
        RAWGGameDetailTool(),
    ]
    system_prompt = prompts["recommend"]["system_prompt"]
    agent = create_react_agent(model=llm, tools=tools, prompt=system_prompt)
    agent.max_iterations = 5
    return agent


def build_recommend_agent():
    """游戏推荐 Agent —— 单例由 deps 持有"""
    return deps_get_recommend_agent()


async def run_recommend(state: dict, profile: dict | None = None) -> dict:
    agent = build_recommend_agent()
    messages = state.get("messages", [])
    user_input = messages[-1].content if messages else ""
    game_name = state.get("game_name", "")

    # ── 注入用户画像 ──
    profile_text = build_profile_text(profile or {})
    if profile_text:
        query = f"{profile_text}\n用户喜欢: {game_name}. {user_input}"
    else:
        query = f"用户喜欢: {game_name}. {user_input}"

    agent_messages = [HumanMessage(content=query)]
    result = await agent.ainvoke({"messages": agent_messages})
    response_messages = result.get("messages", [])
    final = response_messages[-1].content if response_messages else ""

    return {
        "recommend_result": result,
        "final_response": final,
    }
