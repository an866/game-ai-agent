"""游戏查询 Agent —— 获取游戏详细信息"""

import yaml
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate

from config.settings import get_settings
from src.tools.steam_api import SteamSearchTool, SteamDetailTool, SteamCurrentPlayersTool
from src.tools.rawg import RAWGGameSearchTool, RAWGGameDetailTool, RAWGGameScreenshotsTool

settings = get_settings()

config_path = Path(__file__).parent.parent.parent / "config" / "agents.yaml"
with open(config_path, encoding="utf-8") as f:
    prompts = yaml.safe_load(f)

REACT_PROMPT = PromptTemplate.from_template("""You are a game information query expert.

TOOLS:
{tools}

TOOL NAMES: {tool_names}

Use the following format:
Question: the user's question
Thought: think about what to do
Action: the tool to use
Action Input: the input to the tool
Observation: the tool result
... (repeat Thought/Action/Action Input/Observation as needed)
Thought: I now know the final answer
Final Answer: the final answer in Chinese

System: {system_prompt}

Question: {input}
Thought: {agent_scratchpad}
""")


def get_query_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=0.3,
    )


def build_query_agent() -> AgentExecutor:
    """构建游戏查询 Agent (ReAct)"""
    llm = get_query_llm()
    tools = [
        SteamSearchTool(),
        SteamDetailTool(),
        SteamCurrentPlayersTool(),
        RAWGGameSearchTool(),
        RAWGGameDetailTool(),
        RAWGGameScreenshotsTool(),
    ]

    agent = create_react_agent(llm=llm, tools=tools, prompt=REACT_PROMPT)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=10,
        return_intermediate_steps=False,
    )
    return executor


async def run_query(state: dict, query: str | None = None) -> dict:
    """执行游戏查询"""
    executor = build_query_agent()
    messages = state.get("messages", [])
    user_input = query or (messages[-1].content if messages else "")

    system_prompt = prompts["query"]["system_prompt"]
    result = await executor.ainvoke({
        "input": user_input,
        "system_prompt": system_prompt,
    })

    return {
        "query_result": result,
        "final_response": result.get("output", ""),
    }
