"""联网搜索 —— DDG 免费搜索 + Tavily 付费回退

WebSearchTool 与 MCP server (src/mcp/web_search_server.py) 共用 search_web。
"""

import asyncio
from typing import Any

from bs4 import BeautifulSoup
from loguru import logger
from pydantic import BaseModel, Field

from src.tools.base import GameDataTool, get_http_client

DDG_TIMEOUT = 8.0
TAVILY_TIMEOUT = 10.0


def _get_tavily_key() -> str:
    """Tavily key 唯一来源：settings（.env / 环境变量可覆盖）"""
    from config.settings import get_settings
    return get_settings().tavily_api_key or ""


async def search_web(query: str, max_results: int = 5) -> list[dict]:
    """通用联网搜索 —— DDG 优先，失败/超时回退 Tavily，双失败返回降级文案"""
    try:
        return await asyncio.wait_for(
            _search_ddg(query, max_results), timeout=DDG_TIMEOUT
        )
    except Exception as exc:
        logger.warning(f"DDG 搜索失败，回退 Tavily: {exc}")

    try:
        return await asyncio.wait_for(
            _search_tavily(query, max_results), timeout=TAVILY_TIMEOUT
        )
    except Exception as exc:
        logger.warning(f"Tavily 搜索也失败: {exc}")
        return [{"title": "搜索失败", "snippet": "当前无法联网搜索，请稍后重试", "url": ""}]


async def _search_ddg(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo HTML 搜索（免费，无需 API Key）"""
    url = "https://html.duckduckgo.com/html/"
    resp = await get_http_client().get(url, params={"q": query})
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # DDG 可能返回验证页面（202 无结果），检测并触发回退
    results = []
    for item in soup.select(".result")[:max_results]:
        title_el = item.select_one(".result__title a, .result__a")
        snippet_el = item.select_one(".result__snippet, .result__extract__snippet")
        results.append({
            "title": title_el.get_text(strip=True) if title_el else "",
            "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
            "url": title_el.get("href", "") if title_el else "",
        })

    if not results:
        raise RuntimeError("DuckDuckGo 返回空结果或验证页面")

    return results


async def _search_tavily(query: str, max_results: int = 5) -> list[dict]:
    """Tavily 搜索回退（付费，月免 1000 次）"""
    key = _get_tavily_key()
    if not key:
        raise ValueError("TAVILY_API_KEY 未配置")

    from tavily import TavilyClient
    from src.utils.async_utils import run_sync_in_loop

    client = TavilyClient(api_key=key)
    resp = await run_sync_in_loop(
        client.search, query, max_results=max_results, search_depth="basic"
    )
    return [
        {
            "title": r.get("title", ""),
            "snippet": r.get("content", ""),
            "url": r.get("url", ""),
        }
        for r in resp.get("results", [])
    ]


class WebSearchInput(BaseModel):
    query: str = Field(description="搜索关键词")
    max_results: int = Field(default=5, description="最大结果数")


class WebSearchTool(GameDataTool):
    """通用联网搜索 —— DDG 优先，失败/超时回退到 Tavily"""
    name: str = "web_search"
    description: str = (
        "在互联网上搜索游戏相关信息（新闻、评价、攻略、发售日等）。"
        "当 Steam/RAWG 等内置 API 无法回答用户问题时使用。输入为搜索关键词。"
    )
    args_schema: type[BaseModel] = WebSearchInput
    cache_ttl: int = 1800

    async def _arun(self, query: str, max_results: int = 5, **kwargs: Any) -> Any:
        return await self._cached_call(search_web, query, max_results)