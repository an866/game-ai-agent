"""数据访问层 —— 封装 MySQL 操作"""

from datetime import datetime
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from src.data.models import Watchlist, PriceAlert, UserPreference, ChatHistory


class WatchlistRepository:
    """价格监控数据访问"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_active(self) -> list[Watchlist]:
        result = await self.session.execute(
            select(Watchlist).where(Watchlist.status == "active")
        )
        return list(result.scalars().all())

    async def get_by_id(self, watchlist_id: int) -> Watchlist | None:
        result = await self.session.execute(
            select(Watchlist).where(Watchlist.id == watchlist_id)
        )
        return result.scalar_one_or_none()

    async def add(self, game_name: str, target_price: float, steam_appid: int | None = None) -> Watchlist:
        item = Watchlist(
            game_name=game_name,
            steam_appid=steam_appid,
            target_price=target_price,
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def update_status(self, watchlist_id: int, status: str):
        await self.session.execute(
            update(Watchlist)
            .where(Watchlist.id == watchlist_id)
            .values(status=status, last_checked_at=datetime.now())
        )
        await self.session.commit()

    async def update_price(self, watchlist_id: int, target_price: float):
        await self.session.execute(
            update(Watchlist)
            .where(Watchlist.id == watchlist_id)
            .values(target_price=target_price)
        )
        await self.session.commit()

    async def delete(self, watchlist_id: int):
        await self.session.execute(
            delete(Watchlist).where(Watchlist.id == watchlist_id)
        )
        await self.session.commit()

    async def get_count(self) -> int:
        result = await self.session.execute(
            select(Watchlist).where(Watchlist.status == "active")
        )
        return len(list(result.scalars().all()))


class PriceAlertRepository:
    """价格告警数据访问"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_alert(
        self, watchlist_id: int, current_price: float,
        target_price: float, store_name: str = "Unknown"
    ) -> PriceAlert:
        alert = PriceAlert(
            watchlist_id=watchlist_id,
            current_price=current_price,
            target_price=target_price,
            store_name=store_name,
        )
        self.session.add(alert)
        await self.session.commit()
        await self.session.refresh(alert)
        return alert

    async def get_unread(self, limit: int = 20) -> list[PriceAlert]:
        result = await self.session.execute(
            select(PriceAlert)
            .where(PriceAlert.is_read == False)
            .order_by(PriceAlert.triggered_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_read(self, alert_id: int):
        await self.session.execute(
            update(PriceAlert)
            .where(PriceAlert.id == alert_id)
            .values(is_read=True)
        )
        await self.session.commit()

    async def get_count_unread(self) -> int:
        result = await self.session.execute(
            select(PriceAlert).where(PriceAlert.is_read == False)
        )
        return len(list(result.scalars().all()))


class ChatHistoryRepository:
    """对话历史数据访问"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, role: str, content: str, intent: str | None = None):
        record = ChatHistory(role=role, content=content, intent=intent)
        self.session.add(record)
        await self.session.commit()

    async def get_recent(self, limit: int = 50) -> list[ChatHistory]:
        result = await self.session.execute(
            select(ChatHistory)
            .order_by(ChatHistory.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
