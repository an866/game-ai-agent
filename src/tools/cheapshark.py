"""CheapShark API 工具 —— 游戏折扣查询（免费，无需 API Key）"""

from typing import Any
from src.tools.base import GameDataTool, get_http_client


def _discount_percent(normal_price: float, sale_price: float) -> float:
    """计算折扣百分比（免费游戏 normal=0 时返回 0）"""
    if normal_price <= 0:
        return 0.0
    return round((normal_price - sale_price) / normal_price * 100, 1)


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

        resp = await get_http_client().get(url, params=params)
        resp.raise_for_status()
        deals = resp.json()
        return [
            {
                "deal_id": d["dealID"],
                "title": d["title"],
                "sale_price": float(d["salePrice"]),
                "normal_price": float(d["normalPrice"]),
                # savings 是美元金额；折扣百分比需要自己从原价/现价计算
                "savings": float(d["savings"]),
                "discount_percent": _discount_percent(
                    float(d["normalPrice"]), float(d["salePrice"])
                ),
                "store_name": d.get("storeID", "Unknown"),
                "metacritic_score": d.get("metacriticScore"),
                "steam_rating": d.get("steamRatingText"),
                "thumb": d.get("thumb"),
            }
            for d in deals
        ]