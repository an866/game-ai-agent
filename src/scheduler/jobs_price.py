"""价格巡检定时任务"""

from loguru import logger
from src.data.database import async_session_factory
from src.data.repository import WatchlistRepository, PriceAlertRepository
from src.tools.cheapshark import CheapSharkDealsTool


async def check_watchlist_prices():
    """遍历所有活跃监控项，检查是否到达目标价"""
    cheapshark = CheapSharkDealsTool()

    async with async_session_factory() as session:
        watchlist_repo = WatchlistRepository(session)
        alert_repo = PriceAlertRepository(session)

        active_watches = await watchlist_repo.get_all_active()
        if not active_watches:
            logger.info("价格巡检: 无活跃监控项")
            return

        alerts_triggered = 0
        for watch in active_watches:
            try:
                deals = await cheapshark._search_deals(watch.game_name, on_sale=True)

                if not deals:
                    continue

                best_deal = min(deals, key=lambda d: d["sale_price"])
                current_price = best_deal["sale_price"]

                if current_price <= float(watch.target_price):
                    await alert_repo.create_alert(
                        watchlist_id=watch.id,
                        current_price=current_price,
                        target_price=float(watch.target_price),
                        store_name=best_deal.get("store_name", "Unknown"),
                    )
                    alerts_triggered += 1
                    logger.info(
                        f"价格告警: {watch.game_name} "
                        f"当前 ¥{current_price} ≤ 目标 ¥{float(watch.target_price)}"
                    )

                await watchlist_repo.update_status(watch.id, "active")

            except Exception as e:
                logger.warning(f"价格巡检失败 [{watch.game_name}]: {e}")

        logger.info(f"价格巡检完成: 检查 {len(active_watches)} 项, 触发 {alerts_triggered} 个告警")
