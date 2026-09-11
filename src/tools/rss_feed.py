"""RSS 订阅工具 —— 拉取和解析游戏新闻 RSS"""

import asyncio
from typing import Any
import feedparser
from bs4 import BeautifulSoup
from langchain_core.documents import Document
from loguru import logger
from config.loader import get_rss_sources
from src.tools.base import GameDataTool, get_http_client


class RSSFetchTool(GameDataTool):
    """拉取 RSS 订阅源"""
    name: str = "rss_fetch_feed"
    description: str = "拉取单个 RSS 订阅源的文章。输入为 RSS URL。"
    cache_ttl: int = 1800

    async def _arun(self, url: str, limit: int = 10) -> Any:
        return await self._cached_call(self._fetch, url, limit)

    async def _fetch(self, url: str, limit: int = 10) -> list[dict]:
        from src.utils.async_utils import run_sync_in_loop
        feed = await run_sync_in_loop(feedparser.parse, url)
        entries = feed.entries[:limit]
        return [
            {
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "summary": (entry.get("summary", "") or entry.get("description", ""))[:500],
                "published": entry.get("published", "") or entry.get("updated", ""),
                "source": feed.feed.get("title", url),
            }
            for entry in entries
        ]


class RSSFetchAllTool(GameDataTool):
    """拉取所有配置的 RSS 源"""
    name: str = "rss_fetch_all"
    description: str = "拉取所有已配置的游戏新闻 RSS 源。无参数。"
    cache_ttl: int = 1800

    async def _arun(self) -> Any:
        return await self._cached_call(self._fetch_all)

    async def _fetch_all(self) -> list[dict]:
        sources = get_rss_sources()
        fetch_tool = RSSFetchTool()

        async def _one(source: dict) -> list[dict]:
            try:
                articles = await fetch_tool._fetch(source["url"])
                for a in articles:
                    a["source_name"] = source["name"]
                    a["language"] = source["language"]
                logger.info(f"RSS: {source['name']} → {len(articles)} 篇")
                return articles
            except Exception as e:
                logger.warning(f"RSS 拉取失败 [{source['name']}]: {e}")
                return []

        batches = await asyncio.gather(*[_one(s) for s in sources])
        return [a for batch in batches for a in batch]


async def fetch_all_rss_as_documents() -> list[Document]:
    """拉取所有 RSS 并转为 LangChain Document 列表"""
    tool = RSSFetchAllTool()
    articles = await tool._fetch_all()
    docs = []
    for a in articles:
        # 尝试抓取全文
        content = a.get("summary", "")
        try:
            resp = await get_http_client().get(a["link"], timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                content = soup.get_text(separator="\n", strip=True)[:3000]
        except Exception:
            pass

        docs.append(Document(
            page_content=content,
            metadata={
                "title": a["title"],
                "source_url": a["link"],
                "source_name": a.get("source_name", a.get("source", "")),
                "published_date": a.get("published", ""),
                "language": a.get("language", "unknown"),
            },
        ))
    return docs
