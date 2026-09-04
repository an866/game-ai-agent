"""数据访问层 —— 封装 MySQL 操作

事务约定（C12）：Repository 方法不做 commit/flush 之外的事——
增改删只作用于当前 session，由调用方（service 层）负责 commit/rollback。
单次操作需补 id 的用 flush 即可（expire_on_commit=False 下已设置的属性保留）。
"""

from datetime import datetime, timedelta
from sqlalchemy import select, update, delete, func
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
        await self.session.flush()
        return item

    async def update_status(self, watchlist_id: int, status: str):
        await self.session.execute(
            update(Watchlist)
            .where(Watchlist.id == watchlist_id)
            .values(status=status, last_checked_at=datetime.now())
        )

    async def update_price(self, watchlist_id: int, target_price: float):
        await self.session.execute(
            update(Watchlist)
            .where(Watchlist.id == watchlist_id)
            .values(target_price=target_price)
        )

    async def delete(self, watchlist_id: int):
        await self.session.execute(
            delete(Watchlist).where(Watchlist.id == watchlist_id)
        )

    async def get_count(self) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(Watchlist)
            .where(Watchlist.status == "active")
        )
        return result.scalar() or 0


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
        await self.session.flush()
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

    async def get_count_unread(self) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(PriceAlert)
            .where(PriceAlert.is_read == False)
        )
        return result.scalar() or 0

    async def has_recent_alert(self, watchlist_id: int, window_hours: int = 48) -> bool:
        """指定时间窗口内是否已为该监控项触发过告警（防重复）"""
        cutoff = datetime.now() - timedelta(hours=window_hours)
        result = await self.session.execute(
            select(func.count())
            .select_from(PriceAlert)
            .where(
                PriceAlert.watchlist_id == watchlist_id,
                PriceAlert.triggered_at >= cutoff,
            )
        )
        return (result.scalar() or 0) > 0

    async def mark_all_read(self) -> int:
        """批量标记全部未读告警为已读，返回受影响行数"""
        result = await self.session.execute(
            update(PriceAlert)
            .where(PriceAlert.is_read == False)
            .values(is_read=True)
        )
        return result.rowcount or 0


class ChatHistoryRepository:
    """对话历史数据访问"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, session_id: str, role: str, content: str, intent: str | None = None):
        record = ChatHistory(session_id=session_id, role=role, content=content, intent=intent)
        self.session.add(record)

    async def get_recent(self, session_id: str, limit: int = 50) -> list[ChatHistory]:
        """按时间倒序取指定会话最近 N 条"""
        result = await self.session.execute(
            select(ChatHistory)
            .where(ChatHistory.session_id == session_id)
            .order_by(ChatHistory.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class UserPreferenceRepository:
    """用户画像数据访问"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_profile(self, session_id: str, profile: dict):
        """写入或更新用户画像（全字段覆盖）"""
        values = {
            "favorite_genres": profile.get("favorite_genres", ""),
            "favorite_games": profile.get("favorite_games", ""),
            "platforms": profile.get("platforms", ""),
            "budget_range": profile.get("budget_range", ""),
        }
        result = await self.session.execute(
            select(UserPreference).where(UserPreference.session_id == session_id)
        )
        if result.scalar_one_or_none():
            await self.session.execute(
                update(UserPreference)
                .where(UserPreference.session_id == session_id)
                .values(**values)
            )
        else:
            self.session.add(UserPreference(session_id=session_id, **values))

    async def get_profile(self, session_id: str) -> dict | None:
        result = await self.session.execute(
            select(UserPreference)
            .where(UserPreference.session_id == session_id)
            .order_by(UserPreference.updated_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row:
            return {
                "favorite_genres": row.favorite_genres or "",
                "favorite_games": row.favorite_games or "",
                "platforms": row.platforms or "",
                "budget_range": row.budget_range or "",
            }
        return None
