"""Redis 连接管理 —— 进程级单例，实现在 src.deps"""

import redis.asyncio as redis
from src.deps import get_redis as _deps_get_redis


async def get_redis() -> redis.Redis:
    """获取 Redis 连接（单例由 deps 持有，进程生命周期内不复用关闭）"""
    return _deps_get_redis()