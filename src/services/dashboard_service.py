"""仪表盘服务 —— 首页统计与热门游戏（并行 + 超时，避免卡住概览切换）"""

import asyncio
from typing import Callable

from loguru import logger

from src.data.repository import PriceAlertRepository, WatchlistRepository
from src.deps import get_session_factory
from src.rag.store import get_doc_count

# 单源超时（秒）——任何一路拖死都不应挡住整页渲染
DB_TIMEOUT = 8.0
DEALS_TIMEOUT = 10.0
PLAYERS_TIMEOUT = 12.0


async def _db_counts(session_factory: Callable | None = None) -> tuple[int, int]:
    factory = session_factory or get_session_factory
    async with factory()() as session:
        w = await WatchlistRepository(session).get_count()
        a = await PriceAlertRepository(session).get_count_unread()
        return int(w), int(a)


async def _best_deal() -> str:
    from src.tools.cheapshark import CheapSharkDealsTool
    deals = await CheapSharkDealsTool()._arun("", on_sale=True)
    if deals:
        best = deals[0]
        return f"{best['discount_percent']:.0f}% ({best['title'][:20]})"
    return "-"


async def get_dashboard_stats(session_factory: Callable | None = None) -> dict:
    """首页统计：监控数 / 未读告警 / 新闻库 / 今日最佳折扣（并行）"""
    stats = {"watchlist": 0, "alerts": 0, "news_count": 0, "best_deal": "-"}

    async def _safe(coro, default):
        try:
            return await asyncio.wait_for(coro, timeout=DB_TIMEOUT)
        except Exception as exc:
            logger.warning(f"仪表盘子任务失败: {exc}")
            return default

    db_task = _safe(_db_counts(session_factory), (0, 0))
    # get_doc_count 已改为不加载 embedding，但仍给超时保险
    news_task = asyncio.to_thread(get_doc_count)
    deal_task = _safe(_best_deal(), "-")

    (w, a), news_count, deal = await asyncio.gather(db_task, news_task, deal_task)
    stats["watchlist"] = w
    stats["alerts"] = a
    stats["news_count"] = int(news_count or 0)
    stats["best_deal"] = deal
    return stats


HOT_GAMES = [
    {"name": "Counter-Strike 2", "appid": 730},
    {"name": "Dota 2", "appid": 570},
    {"name": "PUBG: BATTLEGROUNDS", "appid": 578080},
    {"name": "Apex Legends", "appid": 1172470},
    {"name": "Genshin Impact", "appid": None},
]


async def get_hot_players(session_factory: Callable | None = None) -> list[dict]:
    """热门游戏实时在线人数（并行查询，单游戏失败显示 '-'）"""
    from src.tools.steam_api import SteamCurrentPlayersTool

    tool = SteamCurrentPlayersTool()

    async def _one(game: dict):
        if game["appid"] is None:
            return game["name"], None
        try:
            data = await asyncio.wait_for(
                tool._arun(game["appid"]), timeout=PLAYERS_TIMEOUT
            )
            return game["name"], data.get("current_players", 0)
        except Exception as exc:
            logger.warning(f"在线人数获取失败 [{game['name']}]: {exc}")
            return game["name"], None

    try:
        pairs = await asyncio.gather(*[_one(g) for g in HOT_GAMES])
        results = dict(pairs)
    except Exception as exc:
        logger.warning(f"热门游戏加载失败: {exc}")
        results = {g["name"]: None for g in HOT_GAMES}

    return [
        {"name": g["name"], "players": f"{results[g['name']]:,}"}
        if results.get(g["name"]) is not None
        else {"name": g["name"], "players": "-"}
        for g in HOT_GAMES
    ]
