"""MySQL 数据库连接管理（SQLAlchemy async）"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from config.settings import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.mysql_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI 风格的依赖注入获取数据库会话"""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_tables():
    """创建所有表（从 ORM 模型）"""
    from src.data.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables():
    """删除所有表"""
    from src.data.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
