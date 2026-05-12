"""价格追踪 Agent —— 跨商店比价与降价提醒"""

import yaml
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate

from config.settings import get_settings
from src.tools.cheapshark import CheapSharkDealsTool
from src.tools.isthereanydeal import ITADLookupTool, ITADPricesTool, ITADHistoryTool

settings = get_settings()

config_path = Path(__file__).parent.parent.parent / "config" / "agents.yaml"
with open(config_path, encoding="utf-8") as f:
    prompts = yaml.safe_load(f)

REACT_PROMPT = PromptTemplate.from_template("""You are a game price analysis expert.

TOOLS:
{tools}

TOOL NAMES: {tool_names}

Steps:
1. Search for the game price on CheapShark for the best deals
2. Optionally look up the game on ITAD for cross-store comparison
3. Check price history if available
4. Advise whether now is a good time to buy

Use the following format:
Question: the user's question
Thought: think about what to do
Action: the tool to use
Action Input: the input to the tool
Observation: the tool result
... (repeat as needed)
Thought: I now know the final answer
Final Answer: Answer in Chinese with price analysis

System: {system_prompt}

Question: {input}
Thought: {agent_scratchpad}
""")


def get_price_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=0.3,
    )


def build_price_agent() -> AgentExecutor:
    llm = get_price_llm()
    tools = [
        CheapSharkDealsTool(),
        ITADLookupTool(),
        ITADPricesTool(),
        ITADHistoryTool(),
    ]

    agent = create_react_agent(llm=llm, tools=tools, prompt=REACT_PROMPT)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=10,
        return_intermediate_steps=False,
    )


async def run_price(state: dict) -> dict:
    executor = build_price_agent()
    messages = state.get("messages", [])
    user_input = messages[-1].content if messages else ""
    game_name = state.get("game_name", "")

    query = f"查询游戏价格: {game_name}. {user_input}"

    system_prompt = prompts["price"]["system_prompt"]
    result = await executor.ainvoke({
        "input": query,
        "system_prompt": system_prompt,
    })

    return {
        "price_result": result,
        "final_response": result.get("output", ""),
    }
