"""HoYoLAB 社区工具 —— 原神 / 鸣潮 等游戏的官方资讯"""

from typing import Any
import httpx
from src.tools.base import GameDataTool


class GenshinNewsTool(GameDataTool):
    """获取原神官方新闻"""
    name: str = "genshin_get_news"
    description: str = "获取原神（Genshin Impact）的官方新闻和公告。无参数。"
    cache_ttl: int = 1800

    async def _arun(self, page_size: int = 10) -> Any:
        return await self._cached_call(self._get_news, page_size)

    async def _get_news(self, page_size: int = 10) -> list[dict]:
        url = "https://bbs-api-os.hoyolab.com/community/post/wapi/getNewsList"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                params={"gids": 2, "type": 1, "pageSize": page_size},
                headers={
                    "User-Agent": "GameAI-Agent/1.0",
                    "Referer": "https://www.hoyolab.com/",
                },
                timeout=self.request_timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            posts = data.get("data", {}).get("list", [])
            return [
                {
                    "title": p["post"]["subject"],
                    "url": f"https://www.hoyolab.com/article/{p['post']['post_id']}",
                    "created_at": p["post"]["created_at"],
                    "summary": p["post"]["content"][:300],
                }
                for p in posts
            ]


class GenshinEventsTool(GameDataTool):
    """获取原神活动日历"""
    name: str = "genshin_get_events"
    description: str = "获取原神当前和即将开始的活动信息。无参数。"
    cache_ttl: int = 3600

    async def _arun(self) -> Any:
        return await self._cached_call(self._get_events)

    async def _get_events(self) -> list[dict]:
        url = "https://bbs-api-os.hoyolab.com/community/community_contribution/wapi/event/list"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                params={"game_id": 2},
                headers={
                    "User-Agent": "GameAI-Agent/1.0",
                    "Referer": "https://www.hoyolab.com/",
                },
                timeout=self.request_timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            events = data.get("data", {}).get("list", [])
            return [
                {
                    "title": e.get("title"),
                    "start_date": e.get("start_time"),
                    "end_date": e.get("end_time"),
                    "url": e.get("url", ""),
                }
                for e in events
            ]
