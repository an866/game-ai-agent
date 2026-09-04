"""监控列表服务 —— UI 与调度器的统一入口"""

from typing import Callable

from loguru import logger

from src.data.repository import WatchlistRepository, PriceAlertRepository
from src.deps import get_session_factory


async def list_watches(session_factory: Callable | None = None) -> list[dict]:
    """返回活跃监控项列表（dict 形式，可直接进 DataFrame）"""
    factory = session_factory or get_session_factory
    try:
        async with factory()() as session:
            items = await WatchlistRepository(session).get_all_active()
            return [
                {
                    "id": item.id,
                    "game_name": item.game_name,
                    "target_price": float(item.target_price),
                    "status": item.status,
                    "created_at": str(item.created_at)[:10] if item.created_at else "-",
                }
                for item in items
            ]
    except Exception as exc:
        logger.warning(f"监控列表加载失败: {exc}")
        return []


async def add_watch(game_name: str, target_price: float, session_factory: Callable | None = None) -> bool:
    factory = session_factory or get_session_factory
    try:
        async with factory()() as session:
            await WatchlistRepository(session).add(
                game_name=game_name, target_price=target_price
            )
            await session.commit()
        return True
    except Exception as exc:
        logger.warning(f"添加监控失败 ({game_name}): {exc}")
        return False


async def delete_watch(watchlist_id: int, session_factory: Callable | None = None) -> bool:
    factory = session_factory or get_session_factory
    try:
        async with factory()() as session:
            await WatchlistRepository(session).delete(watchlist_id)
            await session.commit()
        return True
    except Exception as exc:
        logger.warning(f"删除监控失败 (id={watchlist_id}): {exc}")
        return False


async def list_unread_alerts(limit: int = 20, session_factory: Callable | None = None) -> list[dict]:
    factory = session_factory or get_session_factory
    try:
        async with factory()() as session:
            items = await PriceAlertRepository(session).get_unread(limit)
            return [
                {
                    "current_price": float(a.current_price),
                    "target_price": float(a.target_price),
                    "store_name": a.store_name,
                    "triggered_at": str(a.triggered_at)[:19] if a.triggered_at else "-",
                }
                for a in items
            ]
    except Exception as exc:
        logger.warning(f"告警列表加载失败: {exc}")
        return []


async def mark_all_alerts_read(session_factory: Callable | None = None) -> int:
    factory = session_factory or get_session_factory
    try:
        async with factory()() as session:
            count = await PriceAlertRepository(session).mark_all_read()
            await session.commit()
            return count
    except Exception as exc:
        logger.warning(f"批量已读失败: {exc}")
        return 0