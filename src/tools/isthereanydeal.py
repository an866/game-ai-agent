"""IsThereAnyDeal API 工具 —— 跨商店比价与历史价格

API 说明（2026）：
- 旧版 /v01|/v02/game/plain 已下线
- 搜索：GET  /games/search/v1?key=&title=
- 概览：POST /games/overview/v2?key=&country=&currency=  body=["<game_id>", ...]
- 比价：POST /games/prices/v2?key=&country=&currency=    body=["<game_id>", ...]
"""

from typing import Any

from pydantic import BaseModel, Field, model_validator

from config.settings import get_settings
from src.tools.base import GameDataTool, coerce_arg, get_http_client

ITAD_BASE = "https://api.isthereanydeal.com"

# ITAD 中国区常无报价，默认按美区美元取价（可在响应里看到 historyLow）
_DEFAULT_COUNTRY = "US"
_DEFAULT_CURRENCY = "USD"


def _require_key() -> str:
    key = get_settings().itad_api_key
    if not key:
        raise ValueError(
            "ITAD_API_KEY 未配置，无法查询 IsThereAnyDeal 价格；请先配置或改用 CheapShark"
        )
    return key


class ITADLookupInput(BaseModel):
    title: str = Field(default="", description="游戏名称")
    args: Any = Field(default=None, description="兼容模型误用的位置参数列表")

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        if isinstance(data, dict) and not data.get("title"):
            args = data.get("args")
            if isinstance(args, (list, tuple)) and args:
                data = {**data, "title": str(args[0])}
            elif isinstance(args, str) and args:
                data = {**data, "title": args}
        return data


class ITADPlainInput(BaseModel):
    game_plain: str = Field(default="", description="ITAD 游戏 ID 或 slug")
    args: Any = Field(default=None, description="兼容模型误用的位置参数列表")

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any) -> Any:
        if isinstance(data, dict) and not data.get("game_plain"):
            args = data.get("args")
            if isinstance(args, (list, tuple)) and args:
                data = {**data, "game_plain": str(args[0])}
            elif isinstance(args, str) and args:
                data = {**data, "game_plain": args}
        return data


async def _itad_post_ids(path: str, ids: list[str], history: bool = False) -> Any:
    key = _require_key()
    params = {
        "key": key,
        "country": _DEFAULT_COUNTRY,
        "currency": _DEFAULT_CURRENCY,
    }
    if history:
        params["history"] = "1"
    resp = await get_http_client().post(
        f"{ITAD_BASE}{path}",
        params=params,
        json=ids,
        headers={"Content-Type": "application/json"},
    )
    resp.raise_for_status()
    return resp.json()


class ITADLookupTool(GameDataTool):
    """通过标题查找 ITAD 游戏 ID"""
    name: str = "itad_lookup_game"
    description: str = "在 IsThereAnyDeal 中查找游戏。参数 title 为游戏名称字符串。返回 id/slug/title。"
    args_schema: type[BaseModel] = ITADLookupInput
    cache_ttl: int = 3600

    async def _arun(self, title: str = "", **kwargs: Any) -> Any:
        title = coerce_arg(title, kwargs.get("args"))
        if not title:
            raise ValueError("缺少参数 title（游戏名称）")
        if not get_settings().itad_api_key:
            return {"error": "ITAD_API_KEY 未配置，跳过 IsThereAnyDeal 查询"}
        return await self._cached_call(self._lookup, title)

    async def _lookup(self, title: str) -> list[dict]:
        key = _require_key()
        resp = await get_http_client().get(
            f"{ITAD_BASE}/games/search/v1",
            params={"key": key, "title": title},
        )
        resp.raise_for_status()
        games = resp.json() or []
        return [
            {
                # plain 保留为兼容字段（旧 agent/提示词仍可能引用）
                "id": game.get("id"),
                "plain": game.get("id"),
                "slug": game.get("slug"),
                "title": game.get("title"),
                "type": game.get("type"),
            }
            for game in games[:5]
        ]


class ITADPricesTool(GameDataTool):
    """获取各商店当前价格"""
    name: str = "itad_get_prices"
    description: str = (
        "获取游戏在各数字商店的当前价格与史低。参数 game_plain 为 itad_lookup_game 返回的 id。"
    )
    args_schema: type[BaseModel] = ITADPlainInput
    cache_ttl: int = 900

    async def _arun(self, game_plain: str = "", **kwargs: Any) -> Any:
        game_plain = coerce_arg(game_plain, kwargs.get("args"))
        if not game_plain:
            raise ValueError("缺少参数 game_plain")
        return await self._cached_call(self._get_prices, game_plain)

    async def _get_prices(self, game_plain: str) -> dict:
        data = await _itad_post_ids("/games/prices/v2", [game_plain])
        rows = data if isinstance(data, list) else data.get("prices", [])
        deals: list[dict] = []
        for row in rows:
            for deal in row.get("deals", []):
                price = deal.get("price") or {}
                regular = deal.get("regular") or {}
                deals.append({
                    "shop": (deal.get("shop") or {}).get("name"),
                    "price_new": price.get("amount"),
                    "price_old": regular.get("amount"),
                    "price_cut": deal.get("cut"),
                    "currency": price.get("currency"),
                    "history_low": (deal.get("historyLow") or {}).get("amount"),
                    "store_low": (deal.get("storeLow") or {}).get("amount"),
                    "url": deal.get("url"),
                })
        return {"game": game_plain, "prices": deals}


class ITADHistoryTool(GameDataTool):
    """获取历史价格走势 / 史低"""
    name: str = "itad_get_history"
    description: str = (
        "获取游戏的历史最低价与当前各店报价。参数 game_plain 为 itad_lookup_game 返回的 id。"
    )
    args_schema: type[BaseModel] = ITADPlainInput
    cache_ttl: int = 1800

    async def _arun(self, game_plain: str = "", **kwargs: Any) -> Any:
        game_plain = coerce_arg(game_plain, kwargs.get("args"))
        if not game_plain:
            raise ValueError("缺少参数 game_plain")
        return await self._cached_call(self._get_history, game_plain)

    async def _get_history(self, game_plain: str) -> dict:
        data = await _itad_post_ids("/games/overview/v2", [game_plain])
        payload = data.get("prices", []) if isinstance(data, dict) else (data or [])
        if not payload:
            return {"game": game_plain, "current_lowest": None, "history": []}
        item = payload[0]
        current = item.get("current") or {}
        lowest = item.get("lowest") or {}
        current_price = current.get("price") or {}
        lowest_price = lowest.get("price") or {}
        return {
            "game": game_plain,
            "current_lowest": {
                "shop": (current.get("shop") or {}).get("name"),
                "price_new": current_price.get("amount"),
                "price_old": (current.get("regular") or {}).get("amount"),
                "price_cut": current.get("cut"),
                "currency": current_price.get("currency"),
            },
            "history_lowest": {
                "shop": (lowest.get("shop") or {}).get("name"),
                "price_new": lowest_price.get("amount"),
                "currency": lowest_price.get("currency"),
                "timestamp": lowest.get("timestamp"),
            },
            "history": [],
        }
