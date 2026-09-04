"""联网搜索 MCP Server —— 实现委托给 src.tools.web_search.search_web

通过 stdio 传输向 Claude Code 暴露 web_search 工具。
DDG 优先（免费），失败/超时自动回退到 Tavily。
Tavily key 从 settings 读取（.env 或环境变量 TAVILY_API_KEY）。

使用 mcp 包 (v1.27.2) 的 FastMCP 构建。
"""

from mcp.server.fastmcp import FastMCP
from src.tools.web_search import search_web

mcp = FastMCP("web-search")


@mcp.tool(name="web_search", description="在互联网上搜索信息。DDG 免费搜索优先，失败时自动回退到 Tavily。返回标题、摘要和URL。")
async def web_search(query: str, max_results: int = 5) -> list[dict]:
    """联网搜索 —— DDG 优先 (8s 超时), Tavily 回退 (10s 超时)"""
    return await search_web(query, max_results)


if __name__ == "__main__":
    mcp.run()