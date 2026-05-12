"""Steam API 工具 —— 游戏搜索、详情、新闻、在线人数"""

from typing import Any
import httpx
from config.settings import get_settings
from src.tools.base import GameDataTool

settings = get_settings()


class SteamSearchTool(GameDataTool):
    """搜索 Steam 商店游戏"""
    name: str = "steam_search_game"
    description: str = "在 Steam 商店搜索游戏，返回匹配的游戏列表。输入为游戏名称字符串。"
    cache_ttl: int = 600

    async def _arun(self, query: str) -> Any:
        return await self._cached_call(self._search, query)

    async def _search(self, query: str) -> list[dict]:
        url = "https://store.steampowered.com/api/storesearch/"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                params={"term": query, "l": "zh", "cc": "CN"},
                headers={"User-Agent": "GameAI-Agent/1.0"},
                timeout=self.request_timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])[:10]
            return [
                {
                    "appid": item["id"],
                    "name": item["name"],
                    "type": "steam",
                }
                for item in items
            ]


class SteamDetailTool(GameDataTool):
    """获取 Steam 游戏详情"""
    name: str = "steam_get_details"
    description: str = "获取 Steam 游戏的详细信息（简介、发行日期、开发商、价格等）。输入为 Steam App ID（整数）。"
    cache_ttl: int = 1800

    async def _arun(self, appid: int) -> Any:
        return await self._cached_call(self._get_details, appid)

    async def _get_details(self, appid: int) -> dict:
        url = "https://store.steampowered.com/api/appdetails/"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                params={"appids": appid, "l": "zh", "cc": "CN"},
                headers={"User-Agent": "GameAI-Agent/1.0"},
                timeout=self.request_timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            game_data = data.get(str(appid), {})
            if not game_data.get("success"):
                return {"error": "获取游戏详情失败"}

            info = game_data["data"]
            return {
                "name": info.get("name"),
                "steam_appid": info.get("steam_appid"),
                "short_description": info.get("short_description"),
                "developers": info.get("developers", []),
                "publishers": info.get("publishers", []),
                "release_date": info.get("release_date", {}).get("date"),
                "genres": [g["description"] for g in info.get("genres", [])],
                "categories": [c["description"] for c in info.get("categories", [])],
                "is_free": info.get("is_free", False),
                "price_overview": info.get("price_overview", {}),
                "metacritic": info.get("metacritic", {}),
                "recommendations": info.get("recommendations", {}).get("total"),
                "header_image": info.get("header_image"),
                "platforms": {k: v for k, v in info.get("platforms", {}).items() if v},
                "supported_languages": info.get("supported_languages"),
            }


class SteamNewsTool(GameDataTool):
    """获取 Steam 游戏新闻"""
    name: str = "steam_get_news"
    description: str = "获取指定 Steam 游戏的官方新闻。输入为 Steam App ID（整数）。"
    cache_ttl: int = 900

    async def _arun(self, appid: int, count: int = 5) -> Any:
        return await self._cached_call(self._get_news, appid, count)

    async def _get_news(self, appid: int, count: int = 5) -> list[dict]:
        url = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                params={"appid": appid, "count": count, "feeds": "steam_community_announcements"},
                timeout=self.request_timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("appnews", {}).get("newsitems", [])
            return [
                {
                    "title": item["title"],
                    "url": item["url"],
                    "author": item.get("author"),
                    "date": item.get("date"),
                }
                for item in items
            ]


class SteamCurrentPlayersTool(GameDataTool):
    """获取 Steam 游戏当前在线人数"""
    name: str = "steam_current_players"
    description: str = "获取 Steam 游戏的当前在线玩家数。输入为 Steam App ID（整数）。"
    cache_ttl: int = 300

    async def _arun(self, appid: int) -> Any:
        return await self._cached_call(self._get_players, appid)

    async def _get_players(self, appid: int) -> dict:
        url = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                params={"appid": appid},
                timeout=self.request_timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "appid": appid,
                "current_players": data.get("response", {}).get("player_count", 0),
            }
