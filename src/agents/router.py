"""路由 Agent —— 意图识别与分类"""

from typing import Literal
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from config.loader import get_agents_config

_ROUTER_SCHEMA_HINT = (
    "\n\n【输出契约】只输出一个 JSON 对象，不要 markdown 代码块，字段严格为：\n"
    '{"intent": "game_query|price_check|recommend|news|general", '
    '"game_name": "游戏名或 null", "reasoning": "简短分类理由"}'
)


class RouterDecision(BaseModel):
    """路由决策结构"""
    intent: Literal["game_query", "price_check", "recommend", "news", "general"] = Field(
        description="用户意图分类"
    )
    game_name: str | None = Field(default=None, description="提取的游戏名称")
    reasoning: str = Field(default="", description="分类理由")


def get_router_llm() -> ChatOpenAI:
    """路由 LLM —— 走工厂单例（温度/模型与 ROLE_TEMPERATURES 对齐）"""
    from src.llm import get_llm
    return get_llm("router")


def _parse_router_decision(raw: str) -> RouterDecision:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    return RouterDecision.model_validate_json(text)


def clear_router_cache() -> None:
    """清空路由链缓存（settings / LLM 变更后重建）"""
    global _cached_route
    _cached_route = None


# 路由链单例：system_prompt 与 LLM 进程内不变，避免每轮重建
_cached_route = None


def build_router_chain():
    """构建路由链 —— LLM + JSON 输出（同参缓存）

    DeepSeek 当前不支持 json_schema response_format，且 thinking 模式
    拒绝强制 tool_choice，故不用 with_structured_output 默认路径。
    """
    global _cached_route
    if _cached_route is not None:
        return _cached_route

    prompts = get_agents_config()

    llm = get_router_llm()
    structured_llm = llm.bind(response_format={"type": "json_object"})

    system_prompt = prompts["router"]["system_prompt"] + _ROUTER_SCHEMA_HINT

    async def route(state: dict) -> dict:
        """路由函数 —— 接收 state，返回更新（async：避免阻塞事件循环）"""
        import asyncio

        messages = state.get("messages", [])
        user_msg = messages[-1].content if messages else ""

        try:
            response = await asyncio.wait_for(
                structured_llm.ainvoke([
                    ("system", system_prompt),
                    ("human", user_msg),
                ]),
                timeout=45,
            )
            result = _parse_router_decision(response.content)
            return {
                "intent": result.intent,
                "game_name": result.game_name or state.get("game_name", ""),
                "reasoning": result.reasoning,
            }
        except Exception as exc:
            # 路由失败/超时 → 兜底 general，避免 UI 永远停在「正在理解」
            return {
                "intent": "general",
                "game_name": state.get("game_name", ""),
                "reasoning": f"router 降级: {type(exc).__name__}",
            }

    _cached_route = route
    return route
