"""CheapShark API 工具 —— 游戏折扣查询（免费，无需 API Key）"""

from typing import Any
import httpx
from src.tools.base import GameDataTool


class CheapSharkDealsTool(GameDataTool):
    """搜索 CheapShark 优惠"""
    name: str = "cheapshark_search_deals"
    description: str = "在 CheapShark 搜索游戏折扣信息。输入为游戏名称。"
    cache_ttl: int = 900

    async def _arun(self, title: str, on_sale: bool = True, upper_price: float | None = None) -> Any:
        return await self._cached_call(
            self._search_deals, title, on_sale, upper_price
        )

    async def _search_deals(
        self, title: str, on_sale: bool = True, upper_price: float | None = None
    ) -> list[dict]:
        url = "https://www.cheapshark.com/api/1.0/deals"
        params: dict = {
            "title": title,
            "pageSize": 10,
            "onSale": "1" if on_sale else "0",
        }
        if upper_price is not None:
            params["upperPrice"] = str(upper_price)

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=self.request_timeout)
            resp.raise_for_status()
            deals = resp.json()
            return [
                {
                    "deal_id": d["dealID"],
                    "title": d["title"],
                    "sale_price": float(d["salePrice"]),
                    "normal_price": float(d["normalPrice"]),
                    "savings": float(d["savings"]),
                    "discount_percent": round(float(d["savings"])),
                    "store_name": d.get("storeID", "Unknown"),
                    "metacritic_score": d.get("metacriticScore"),
                    "steam_rating": d.get("steamRatingText"),
                    "thumb": d.get("thumb"),
                }
                for d in deals
            ]


class CheapSharkStoresTool(GameDataTool):
    """获取 CheapShark 商店列表"""
    name: str = "cheapshark_get_stores"
    description: str = "获取 CheapShark 支持的所有商店列表。无参数。"
    cache_ttl: int = 86400

    async def _arun(self) -> Any:
        return await self._cached_call(self._get_stores)

    async def _get_stores(self) -> list[dict]:
        url = "https://www.cheapshark.com/api/1.0/stores"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=self.request_timeout)
            resp.raise_for_status()
            return resp.json()
