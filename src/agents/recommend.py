"""游戏推荐 Agent —— 根据用户偏好推荐类似游戏"""

import yaml
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from config.settings import get_settings
from src.tools.rawg import RAWGGameSearchTool, RAWGGameRecommendationsTool, RAWGGameDetailTool
from src.tools.web_search import WebSearchTool

settings = get_settings()

config_path = Path(__file__).parent.parent.parent / "config" / "agents.yaml"
with open(config_path, encoding="utf-8") as f:
    prompts = yaml.safe_load(f)


def get_recommend_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=0.7,
        streaming=True,
    )


_recommend_agent = None


def build_recommend_agent():
    """构建游戏推荐 Agent (ReAct) —— 单例缓存"""
    global _recommend_agent
    if _recommend_agent is not None:
        return _recommend_agent

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
    _recommend_agent = agent
    return agent


async def run_recommend(state: dict, profile: dict | None = None) -> dict:
    agent = build_recommend_agent()
    messages = state.get("messages", [])
    user_input = messages[-1].content if messages else ""
    game_name = state.get("game_name", "")

    # ── 注入用户画像 ──
    if profile:
        parts = []
        if profile.get("favorite_genres"): parts.append(f"偏好类型: {profile['favorite_genres']}")
        if profile.get("favorite_games"): parts.append(f"喜欢的游戏: {profile['favorite_games']}")
        if profile.get("platforms"): parts.append(f"平台: {profile['platforms']}")
        if profile.get("budget_range"): parts.append(f"预算: {profile['budget_range']}")
        if parts:
            profile_text = "用户画像: " + "；".join(parts) + "。"
            query = f"{profile_text}\n用户喜欢: {game_name}. {user_input}"
        else:
            query = f"用户喜欢: {game_name}. {user_input}"
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
