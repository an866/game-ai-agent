"""SQLAlchemy ORM 模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, DECIMAL
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Watchlist(Base):
    """价格监控列表"""
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_name = Column(String(200), nullable=False, comment="游戏名称")
    steam_appid = Column(Integer, nullable=True, comment="Steam App ID")
    target_price = Column(DECIMAL(10, 2), nullable=False, comment="目标价格")
    currency = Column(String(10), default="CNY", comment="货币")
    status = Column(String(20), default="active", comment="状态: active/paused/triggered")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    last_checked_at = Column(DateTime, nullable=True, comment="最后检查时间")


class PriceAlert(Base):
    """降价告警记录"""
    __tablename__ = "price_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    watchlist_id = Column(Integer, ForeignKey("watchlist.id"), nullable=False, comment="关联监控项")
    current_price = Column(DECIMAL(10, 2), nullable=False, comment="当前价格")
    target_price = Column(DECIMAL(10, 2), nullable=False, comment="目标价格")
    store_name = Column(String(100), default="Unknown", comment="商店名称")
    triggered_at = Column(DateTime, default=datetime.now, comment="触发时间")
    is_read = Column(Boolean, default=False, comment="是否已读")


class UserPreference(Base):
    """用户偏好（用于个性化推荐）"""
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    favorite_genres = Column(Text, nullable=True, comment="偏好类型（逗号分隔）")
    favorite_games = Column(Text, nullable=True, comment="偏好游戏（逗号分隔）")
    platforms = Column(String(200), nullable=True, comment="偏好平台")
    budget_range = Column(String(50), nullable=True, comment="预算范围")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ChatHistory(Base):
    """对话历史"""
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(String(20), nullable=False, comment="user / assistant")
    content = Column(Text, nullable=False, comment="消息内容")
    intent = Column(String(50), nullable=True, comment="意图分类")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
