"""IsThereAnyDeal API 工具 —— 跨商店比价与历史价格"""

from typing import Any
from config.settings import get_settings
from src.tools.base import GameDataTool, get_http_client

settings = get_settings()

ITAD_BASE = "https://api.isthereanydeal.com"


async def _itad_price_data(game_plain: str, history: bool = False) -> dict:
    """ITAD 价格查询统一实现（prices 与 history 仅差一个参数）"""
    params = {
        "key": settings.itad_api_key,
        "plains": game_plain,
        "region": "CN",
        "country": "CN",
    }
    if history:
        params["history"] = "1"
    resp = await get_http_client().get(f"{ITAD_BASE}/v01/game/prices/", params=params)
    resp.raise_for_status()
    return resp.json().get("data", {}).get(game_plain, {})


class ITADLookupTool(GameDataTool):
    """通过标题查找 ITAD 游戏 ID"""
    name: str = "itad_lookup_game"
    description: str = "在 IsThereAnyDeal 中查找游戏。输入为游戏名称。"
    cache_ttl: int = 3600

    async def _arun(self, title: str) -> Any:
        return await self._cached_call(self._lookup, title)

    async def _lookup(self, title: str) -> list[dict]:
        resp = await get_http_client().get(
            f"{ITAD_BASE}/v02/game/plain/",
            params={"key": settings.itad_api_key, "title": title, "limit": 5},
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
        game_data = await _itad_price_data(game_plain)
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
                for deal in game_data.get("list", [])
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
        game_data = await _itad_price_data(game_plain, history=True)
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
                for deal in game_data.get("list", [])
            ],
        }