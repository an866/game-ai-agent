"""游戏推荐 Agent —— 根据用户偏好推荐类似游戏"""

import yaml
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate

from config.settings import get_settings
from src.tools.rawg import RAWGGameSearchTool, RAWGGameRecommendationsTool, RAWGGameDetailTool

settings = get_settings()

config_path = Path(__file__).parent.parent.parent / "config" / "agents.yaml"
with open(config_path, encoding="utf-8") as f:
    prompts = yaml.safe_load(f)

REACT_PROMPT = PromptTemplate.from_template("""You are a game recommendation expert.

TOOLS:
{tools}

TOOL NAMES: {tool_names}

Steps:
1. First search for the game the user mentioned to get its RAWG ID
2. Then use that ID to get similar game recommendations
3. If needed, get more details on the recommended games

Use the following format:
Question: the user's question
Thought: think about what to do
Action: the tool to use
Action Input: the input to the tool
Observation: the tool result
... (repeat as needed)
Thought: I now know the final answer
Final Answer: Recommend 3-5 similar games in Chinese, with reasons for each

System: {system_prompt}

Question: {input}
Thought: {agent_scratchpad}
""")


def get_recommend_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model_complex,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=0.7,
    )


def build_recommend_agent() -> AgentExecutor:
    llm = get_recommend_llm()
    tools = [
        RAWGGameSearchTool(),
        RAWGGameRecommendationsTool(),
        RAWGGameDetailTool(),
    ]

    agent = create_react_agent(llm=llm, tools=tools, prompt=REACT_PROMPT)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=8,
        return_intermediate_steps=False,
    )


async def run_recommend(state: dict) -> dict:
    executor = build_recommend_agent()
    messages = state.get("messages", [])
    user_input = messages[-1].content if messages else ""
    game_name = state.get("game_name", "")

    query = f"用户喜欢: {game_name}. {user_input}"

    system_prompt = prompts["recommend"]["system_prompt"]
    result = await executor.ainvoke({
        "input": query,
        "system_prompt": system_prompt,
    })

    return {
        "recommend_result": result,
        "final_response": result.get("output", ""),
    }
