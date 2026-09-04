"""仪表盘服务 —— 首页统计与热门游戏"""

from typing import Callable

from loguru import logger

from src.data.repository import PriceAlertRepository, WatchlistRepository
from src.deps import get_session_factory
from src.rag.store import get_doc_count


async def get_dashboard_stats(session_factory: Callable | None = None) -> dict:
    """首页统计：监控数 / 未读告警 / 新闻库 / 今日最佳折扣"""
    factory = session_factory or get_session_factory
    stats = {"watchlist": 0, "alerts": 0, "news_count": 0, "best_deal": "-"}
    try:
        async with factory()() as session:
            stats["watchlist"] = await WatchlistRepository(session).get_count()
            stats["alerts"] = await PriceAlertRepository(session).get_count_unread()
    except Exception as exc:
        logger.warning(f"仪表盘 DB 统计失败: {exc}")

    try:
        stats["news_count"] = get_doc_count()
    except Exception as exc:
        logger.warning(f"仪表盘新闻数获取失败: {exc}")

    try:
        from src.tools.cheapshark import CheapSharkDealsTool

        deals = await CheapSharkDealsTool()._arun("", on_sale=True)
        if deals:
            best = deals[0]
            stats["best_deal"] = f"{best['discount_percent']:.0f}% ({best['title'][:20]})"
    except Exception as exc:
        logger.warning(f"仪表盘折扣获取失败: {exc}")
    return stats


async def get_hot_players(session_factory: Callable | None = None) -> list[dict]:
    """热门游戏实时在线人数（查询失败的游戏显示 '-'）"""
    hot_games = [
        {"name": "Counter-Strike 2", "appid": 730},
        {"name": "Dota 2", "appid": 570},
        {"name": "PUBG: BATTLEGROUNDS", "appid": 578080},
        {"name": "Apex Legends", "appid": 1172470},
        {"name": "Genshin Impact", "appid": None},
    ]

    try:
        from src.tools.steam_api import SteamCurrentPlayersTool

        tool = SteamCurrentPlayersTool()
        results = {}
        for game in hot_games:
            if game["appid"] is None:
                results[game["name"]] = None
                continue
            try:
                data = await tool._arun(game["appid"])
                results[game["name"]] = data.get("current_players", 0)
            except Exception as exc:
                logger.warning(f"在线人数获取失败 [{game['name']}]: {exc}")
                results[game["name"]] = None

        return [
            {"name": game["name"], "players": f"{results[game['name']]:,}"}
            if results.get(game["name"]) is not None
            else {"name": game["name"], "players": "-"}
            for game in hot_games
        ]
    except Exception as exc:
        logger.warning(f"热门游戏加载失败: {exc}")
        return [{"name": g["name"], "players": "-"} for g in hot_games]