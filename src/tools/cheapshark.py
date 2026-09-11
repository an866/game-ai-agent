"""CheapShark API 工具 —— 游戏折扣查询（免费，无需 API Key）"""

from typing import Any

from pydantic import BaseModel, Field, model_validator

from src.tools.base import GameDataTool, get_http_client


def _discount_percent(normal_price: float, sale_price: float) -> float:
    """计算折扣百分比（免费游戏 normal=0 时返回 0）"""
    if normal_price <= 0:
        return 0.0
    return round((normal_price - sale_price) / normal_price * 100, 1)


class CheapSharkSearchInput(BaseModel):
    title: str = Field(default="", description="游戏名称")
    on_sale: bool = Field(default=True, description="是否仅折扣中")
    upper_price: float | None = Field(default=None, description="价格上限（美元）")
    args: Any = Field(default=None, description="兼容模型误用的位置参数列表")

    @model_validator(mode="before")
    @classmethod
    def _coerce_args_to_title(cls, data: Any) -> Any:
        """部分模型会输出 {"args": ["游戏名"]} 而非 {"title": "游戏名"}"""
        if isinstance(data, dict) and not data.get("title"):
            args = data.get("args")
            if isinstance(args, (list, tuple)) and args:
                data = {**data, "title": str(args[0])}
            elif isinstance(args, str) and args:
                data = {**data, "title": args}
        return data


class CheapSharkDealsTool(GameDataTool):
    """搜索 CheapShark 优惠"""
    name: str = "cheapshark_search_deals"
    description: str = "在 CheapShark 搜索游戏折扣信息。参数 title 为游戏名称字符串。"
    args_schema: type[BaseModel] = CheapSharkSearchInput
    cache_ttl: int = 900

    async def _arun(self, title: str = "", on_sale: bool = True,
                    upper_price: float | None = None, **kwargs: Any) -> Any:
        if not title:
            args = kwargs.get("args")
            if isinstance(args, (list, tuple)) and args:
                title = str(args[0])
            elif isinstance(args, str):
                title = args
        if not title:
            raise ValueError("缺少参数 title（游戏名称）")
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