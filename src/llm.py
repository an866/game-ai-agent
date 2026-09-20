"""LLM 工厂 —— 按角色惰性单例，温度和 streaming 集中管理

历史：6 个 agent 文件 + memory 各写一份 ChatOpenAI 构造，温度散落硬编码。
此处以角色注册表为唯一真源；带参覆盖时以显式参数为准。
"""

from typing import Any

from langchain_openai import ChatOpenAI

from config.settings import Settings, get_settings

# 角色 → 温度（唯一真源；agents.yaml 中原 temperature 字段已删除，勿再添加）
ROLE_TEMPERATURES: dict[str, float] = {
    "router": 0.1,
    "query": 0.3,
    "price": 0.3,
    "recommend": 0.7,
    "news": 0.3,
    "general": 0.5,
    "compress": 0.3,
    "profile_extract": 0.0,
}

# 角色 → streaming 是否开启（面向用户的回复角色全开，降低首字等待体感）
ROLE_STREAMING: dict[str, bool] = {
    "general": True,
    "recommend": True,
    "query": True,
    "price": True,
    "news": True,
}

_cache: dict[tuple, ChatOpenAI] = {}


def _build(role: str, temperature: float, streaming: bool,
           max_tokens: int | None, settings: Settings) -> ChatOpenAI:
    kwargs: dict[str, Any] = {
        "model": settings.llm_model,
        "api_key": settings.openai_api_key,
        "base_url": settings.openai_base_url,
        "temperature": temperature,
        "streaming": streaming,
        # 必须设超时：无 timeout 时 OpenAI 兼容端点挂起会让 UI 永远「正在理解」
        "timeout": settings.llm_request_timeout,
        "max_retries": settings.llm_max_retries,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if settings.llm_reasoning_effort:
        # 推理模型显式参数（langchain-openai 支持；注意启用后其会把
        # temperature 置 None —— 推理模型语义，温度表仍保留作 fallback）
        kwargs["reasoning_effort"] = settings.llm_reasoning_effort
    return ChatOpenAI(**kwargs)


def get_llm(
    role: str,
    *,
    temperature: float | None = None,
    streaming: bool | None = None,
    max_tokens: int | None = None,
    settings: Settings | None = None,
) -> ChatOpenAI:
    """按角色获取 LLM 实例（同参惰性单例）。

    未显式给出的参数取 ROLE_TEMPERATURES / ROLE_STREAMING 默认；
    with_structured_output 等包装在调用方叠加，不进入工厂。
    """
    _settings = settings or get_settings()
    temp = temperature if temperature is not None else ROLE_TEMPERATURES.get(role, 0.3)
    stream = streaming if streaming is not None else ROLE_STREAMING.get(role, False)
    key = (role, temp, stream, max_tokens, _settings.llm_model,
           _settings.openai_base_url, _settings.openai_api_key)
    if key not in _cache:
        _cache[key] = _build(role, temp, stream, max_tokens, _settings)
    return _cache[key]


def clear_llm_cache() -> None:
    """清空单例缓存（测试 / settings 重建后使用）"""
    _cache.clear()
    # 路由链持有 bind 后的 LLM 引用，需一并失效
    try:
        from src.agents.router import clear_router_cache
        clear_router_cache()
    except Exception:
        pass