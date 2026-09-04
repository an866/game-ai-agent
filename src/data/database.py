"""MySQL 数据库连接管理（SQLAlchemy async）

engine / session factory 均由 src.deps 惰性持有，
业务代码通过 deps.get_session_factory() 取用（见 src/deps.py 约定）。
"""

from src.deps import get_engine


async def create_tables():
    """创建所有表（从 ORM 模型）"""
    from src.data.models import Base
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables():
    """删除所有表"""
    from src.data.models import Base
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)