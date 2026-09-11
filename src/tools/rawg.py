"""RAWG API 工具 —— 游戏元数据、截图、推荐"""

from typing import Any
from pydantic import BaseModel, Field
from config.settings import get_settings
from src.tools.base import GameDataTool, get_http_client

settings = get_settings()


async def _rawg_get(path: str, params: dict | None = None) -> Any:
    """RAWG API 统一请求：共享客户端 + API key 注入"""
    key = (settings.rawg_api_key or "").strip()
    if not key:
        # 无 key 时立刻失败，避免 401×3 重试把面板拖到不可用
        raise RuntimeError("RAWG_API_KEY 未配置（.env），RAWG 数据源不可用")
    url = f"https://api.rawg.io/api/{path}"
    merged = {"key": key, **(params or {})}
    resp = await get_http_client().get(url, params=merged)
    resp.raise_for_status()
    return resp.json()


class RAWGSearchInput(BaseModel):
    query: str = Field(description="游戏名称")
    page: int = Field(default=1, description="页码")
    platforms: str | None = Field(default=None, description="平台过滤，多个用逗号分隔")
    genres: str | None = Field(default=None, description="类型过滤，多个用逗号分隔")


class RAWGGameSearchTool(GameDataTool):
    """搜索 RAWG 游戏数据库"""
    name: str = "rawg_search_game"
    description: str = "在 RAWG 游戏数据库中搜索游戏，返回游戏 ID、名称、评分、类型等。输入为游戏名称。"
    args_schema: type[BaseModel] = RAWGSearchInput
    cache_ttl: int = 600
    max_retries: int = 1  # 无 key / 鉴权失败重试无意义

    async def _arun(self, query: str, page: int = 1, platforms: str | None = None,
                    genres: str | None = None, **kwargs: Any) -> Any:
        return await self._cached_call(self._search, query, page, platforms, genres)

    async def _search(self, query: str, page: int = 1,
                      platforms: str | None = None, genres: str | None = None) -> list[dict]:
        params: dict = {"search": query, "page": page, "page_size": 10}
        if platforms:
            params["platforms"] = platforms
        if genres:
            params["genres"] = genres
        data = await _rawg_get("games", params)
        return [
            {
                "id": game["id"],
                "name": game["name"],
                "slug": game["slug"],
                "rating": game.get("rating"),
                "released": game.get("released"),
                "genres": [g["name"] for g in game.get("genres", [])],
                "platforms": [p["platform"]["name"] for p in game.get("platforms", [])],
                "background_image": game.get("background_image"),
                "metacritic": game.get("metacritic"),
            }
            for game in data.get("results", [])
        ]


class RAWGDetailInput(BaseModel):
    game_id: int = Field(description="RAWG 游戏 ID")


class RAWGGameDetailTool(GameDataTool):
    """获取 RAWG 游戏详细信息"""
    name: str = "rawg_get_details"
    description: str = "通过 RAWG 游戏 ID 获取详细游戏信息。输入为 RAWG 游戏 ID（整数）。"
    args_schema: type[BaseModel] = RAWGDetailInput
    cache_ttl: int = 1800

    async def _arun(self, game_id: int, **kwargs: Any) -> Any:
        return await self._cached_call(self._get_details, game_id)

    async def _get_details(self, game_id: int) -> dict:
        game = await _rawg_get(f"games/{game_id}")
        return {
            "id": game["id"],
            "name": game["name"],
            "slug": game["slug"],
            "description": game.get("description_raw", "")[:1000],
            "rating": game.get("rating"),
            "rating_count": game.get("ratings_count"),
            "released": game.get("released"),
            "genres": [g["name"] for g in game.get("genres", [])],
            "platforms": [p["platform"]["name"] for p in game.get("platforms", [])],
            "developers": [d["name"] for d in game.get("developers", [])],
            "publishers": [p["name"] for p in game.get("publishers", [])],
            "tags": [t["name"] for t in game.get("tags", [])[:15]],
            "background_image": game.get("background_image"),
            "website": game.get("website"),
            "metacritic": game.get("metacritic"),
            "metacritic_url": game.get("metacritic_url"),
        }


class RAWGScreenshotsInput(BaseModel):
    game_id: int = Field(description="RAWG 游戏 ID")


class RAWGGameScreenshotsTool(GameDataTool):
    """获取 RAWG 游戏截图"""
    name: str = "rawg_get_screenshots"
    description: str = "获取游戏的截图列表。输入为 RAWG 游戏 ID（整数）。"
    args_schema: type[BaseModel] = RAWGScreenshotsInput
    cache_ttl: int = 3600

    async def _arun(self, game_id: int, **kwargs: Any) -> Any:
        return await self._cached_call(self._get_screenshots, game_id)

    async def _get_screenshots(self, game_id: int) -> list[dict]:
        data = await _rawg_get(f"games/{game_id}/screenshots")
        return [
            {"id": s["id"], "image": s["image"]}
            for s in data.get("results", [])[:10]
        ]


class RAWGRecommendInput(BaseModel):
    game_id: int = Field(description="RAWG 游戏 ID")


class RAWGGameRecommendationsTool(GameDataTool):
    """获取 RAWG 相似游戏推荐"""
    name: str = "rawg_get_recommendations"
    description: str = "根据 RAWG 游戏 ID 获取相似游戏推荐。输入为 RAWG 游戏 ID（整数）。"
    args_schema: type[BaseModel] = RAWGRecommendInput
    cache_ttl: int = 3600
    max_retries: int = 1

    async def _arun(self, game_id: int, **kwargs: Any) -> Any:
        return await self._cached_call(self._get_suggested, game_id)

    async def _get_suggested(self, game_id: int) -> list[dict]:
        data = await _rawg_get(f"games/{game_id}/suggested")
        return [
            {
                "id": game["id"],
                "name": game["name"],
                "rating": game.get("rating"),
                "released": game.get("released"),
                "genres": [g["name"] for g in game.get("genres", [])],
                "background_image": game.get("background_image"),
                "suggested_count": game.get("suggestions_count"),
            }
            for game in data.get("results", [])[:5]
        ]