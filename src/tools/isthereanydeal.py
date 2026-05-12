"""IsThereAnyDeal API 工具 —— 跨商店比价与历史价格"""

from typing import Any
import httpx
from config.settings import get_settings
from src.tools.base import GameDataTool

settings = get_settings()

ITAD_BASE = "https://api.isthereanydeal.com"


class ITADLookupTool(GameDataTool):
    """通过标题查找 ITAD 游戏 ID"""
    name: str = "itad_lookup_game"
    description: str = "在 IsThereAnyDeal 中查找游戏。输入为游戏名称。"
    cache_ttl: int = 3600

    async def _arun(self, title: str) -> Any:
        return await self._cached_call(self._lookup, title)

    async def _lookup(self, title: str) -> list[dict]:
        url = f"{ITAD_BASE}/v02/game/plain/"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                params={"key": settings.itad_api_key, "title": title, "limit": 5},
                timeout=self.request_timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "plain": game["plain"],
                    "title": game["title"],
                    "type": game.get("type"),
                    "released": game.get("released"),
                }
                for game in data.get("data", {}).get("list", [])
            ]


class ITADPricesTool(GameDataTool):
    """获取各商店当前价格"""
    name: str = "itad_get_prices"
    description: str = "获取游戏在各数字商店的当前价格。输入为 ITAD 游戏 plain ID（字符串）。"
    cache_ttl: int = 900

    async def _arun(self, game_plain: str) -> Any:
        return await self._cached_call(self._get_prices, game_plain)

    async def _get_prices(self, game_plain: str) -> dict:
        url = f"{ITAD_BASE}/v01/game/prices/"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                params={
                    "key": settings.itad_api_key,
                    "plains": game_plain,
                    "region": "CN",
                    "country": "CN",
                },
                timeout=self.request_timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            game_data = data.get("data", {}).get(game_plain, {})
            deals = game_data.get("list", [])
            return {
                "game": game_plain,
                "prices": [
                    {
                        "shop": deal.get("shop", {}).get("name"),
                        "price_new": deal.get("price_new"),
                        "price_old": deal.get("price_old"),
                        "price_cut": deal.get("price_cut"),
                        "url": deal.get("url"),
                    }
                    for deal in deals
                ],
            }


class ITADHistoryTool(GameDataTool):
    """获取历史价格走势"""
    name: str = "itad_get_history"
    description: str = "获取游戏的历史价格走势。输入为 ITAD 游戏 plain ID（字符串）。"
    cache_ttl: int = 1800

    async def _arun(self, game_plain: str) -> Any:
        return await self._cached_call(self._get_history, game_plain)

    async def _get_history(self, game_plain: str) -> dict:
        url = f"{ITAD_BASE}/v01/game/prices/"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                params={
                    "key": settings.itad_api_key,
                    "plains": game_plain,
                    "region": "CN",
                    "country": "CN",
                    "history": "1",
                },
                timeout=self.request_timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            game_data = data.get("data", {}).get(game_plain, {})
            deals = game_data.get("list", [])
            return {
                "game": game_plain,
                "current_lowest": game_data.get("price"),
                "history": [
                    {
                        "shop": deal.get("shop", {}).get("name"),
                        "price_new": deal.get("price_new"),
                        "price_old": deal.get("price_old"),
                        "price_cut": deal.get("price_cut"),
                    }
                    for deal in deals
                ],
            }
