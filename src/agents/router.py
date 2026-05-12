"""路由 Agent —— 意图识别与分类"""

from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from config.settings import get_settings

settings = get_settings()


class RouterDecision(BaseModel):
    """路由决策结构"""
    intent: Literal["game_query", "price_check", "recommend", "news", "general"] = Field(
        description="用户意图分类"
    )
    game_name: str | None = Field(default=None, description="提取的游戏名称")
    reasoning: str = Field(default="", description="分类理由")


def get_router_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=0.1,
    )


def build_router_chain():
    """构建路由链 —— LLM + 结构化输出"""
    import yaml
    from pathlib import Path

    config_path = Path(__file__).parent.parent.parent / "config" / "agents.yaml"
    with open(config_path, encoding="utf-8") as f:
        prompts = yaml.safe_load(f)

    llm = get_router_llm()
    structured_llm = llm.with_structured_output(RouterDecision)

    system_prompt = prompts["router"]["system_prompt"]

    def route(state: dict) -> dict:
        """路由函数 —— 接收 state，返回更新"""
        messages = state.get("messages", [])
        user_msg = messages[-1].content if messages else ""

        result: RouterDecision = structured_llm.invoke([
            ("system", system_prompt),
            ("human", user_msg),
        ])

        return {
            "intent": result.intent,
            "game_name": result.game_name or state.get("game_name", ""),
        }

    return route
