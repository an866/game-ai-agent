"""Redis 连接池管理"""

import redis.asyncio as redis
from config.settings import get_settings

settings = get_settings()

_redis_pool: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    """获取 Redis 连接"""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password or None,
            decode_responses=True,
        )
    return _redis_pool

# 注意：_redis_pool 不做显式关闭——进程生命周期内复用；
# 测试环境如需隔离请通过 monkeypatch 替换 get_redis。
