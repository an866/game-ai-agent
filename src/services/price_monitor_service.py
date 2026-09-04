"""价格巡检服务 —— 遍历活跃监控项检查目标价，48h 窗口内去重

决策记录：同一监控项在 ALERT_DEDUP_HOURS 内仅触发一次告警，
避免每 6h 一轮巡检持续低于目标价时重复插入告警行（原行为）。
"""

from typing import Callable

from loguru import logger

from src.data.repository import PriceAlertRepository, WatchlistRepository
from src.deps import get_session_factory
from src.tools.cheapshark import CheapSharkDealsTool

ALERT_DEDUP_HOURS = 48


async def run_price_check(session_factory: Callable | None = None) -> dict:
    """执行一轮价格巡检。

    Returns:
        {"checked": 检查项数, "triggered": 新触发告警数, "skipped": 去重跳过数}
    """
    factory = session_factory or get_session_factory
    cheapshark = CheapSharkDealsTool()
    stats = {"checked": 0, "triggered": 0, "skipped": 0}

    async with factory()() as session:
        watchlist_repo = WatchlistRepository(session)
        alert_repo = PriceAlertRepository(session)
        active_watches = await watchlist_repo.get_all_active()
        if not active_watches:
            logger.info("价格巡检: 无活跃监控项")
            return stats

        for watch in active_watches:
            stats["checked"] += 1
            try:
                # 走工具基类 _arun（Redis 缓存 + 重试 + 超时）
                deals = await cheapshark._arun(watch.game_name, on_sale=True)
                if not deals:
                    continue

                best_deal = min(deals, key=lambda d: d["sale_price"])
                current_price = best_deal["sale_price"]

                if current_price <= float(watch.target_price):
                    if await alert_repo.has_recent_alert(watch.id, ALERT_DEDUP_HOURS):
                        stats["skipped"] += 1
                        continue
                    await alert_repo.create_alert(
                        watchlist_id=watch.id,
                        current_price=current_price,
                        target_price=float(watch.target_price),
                        store_name=best_deal.get("store_name", "Unknown"),
                    )
                    stats["triggered"] += 1
                    logger.info(
                        f"价格告警: {watch.game_name} "
                        f"当前 ¥{current_price} ≤ 目标 ¥{float(watch.target_price)}"
                    )

                await watchlist_repo.update_status(watch.id, "active")
                # 单个监控项一个事务：create_alert + update_status 原子提交
                await session.commit()

            except Exception as e:
                await session.rollback()
                logger.warning(f"价格巡检失败 [{watch.game_name}]: {e}")

        logger.info(f"价格巡检完成: {stats}")
        return stats