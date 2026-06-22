"""联网搜索 MCP Server

通过 stdio 传输向 Claude Code 暴露 web_search 工具。
DDG 优先（免费），失败/超时自动回退到 Tavily。

使用 mcp 包 (v1.27.2) 的 FastMCP 构建。
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("web-search")


def _get_tavily_key() -> str:
    import os
    return os.getenv("TAVILY_API_KEY", "")


@mcp.tool(name="web_search", description="在互联网上搜索信息。DDG 免费搜索优先，失败时自动回退到 Tavily。返回标题、摘要和URL。")
async def web_search(query: str, max_results: int = 5) -> list[dict]:
    """联网搜索 —— DDG 优先 (8s 超时), Tavily 回退 (10s 超时)"""
    # 第1次: DuckDuckGo
    try:
        return await asyncio.wait_for(
            _search_ddg(query, max_results), timeout=8.0
        )
    except Exception:
        pass

    # 第2次: Tavily 回退
    try:
        return await asyncio.wait_for(
            _search_tavily(query, max_results), timeout=10.0
        )
    except Exception:
        return [{"title": "搜索失败", "snippet": "当前无法联网搜索，请稍后重试", "url": ""}]


async def _search_ddg(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo HTML 搜索（免费）"""
    url = "https://html.duckduckgo.com/html/"
    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(url, params={"q": query}, timeout=8.0)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for item in soup.select(".result")[:max_results]:
        title_el = item.select_one(".result__title a, .result__a")
        snippet_el = item.select_one(".result__snippet")
        results.append({
            "title": title_el.get_text(strip=True) if title_el else "",
            "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
            "url": title_el.get("href", "") if title_el else "",
        })

    if not results:
        raise RuntimeError("DuckDuckGo 无结果")
    return results


async def _search_tavily(query: str, max_results: int = 5) -> list[dict]:
    """Tavily API 回退"""
    key = _get_tavily_key()
    if not key:
        raise ValueError("TAVILY_API_KEY not set")

    from tavily import TavilyClient
    client = TavilyClient(api_key=key)
    resp = client.search(query, max_results=max_results, search_depth="basic")
    return [
        {"title": r.get("title", ""), "snippet": r.get("content", ""), "url": r.get("url", "")}
        for r in resp.get("results", [])
    ]


if __name__ == "__main__":
    mcp.run()
