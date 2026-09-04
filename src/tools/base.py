"""工具基类 —— 统一缓存、重试、超时、HTTP 客户端"""

import asyncio
import hashlib
import json
from typing import Any
from abc import ABC, abstractmethod
import httpx
from langchain_core.tools import BaseTool
from loguru import logger

from src.data.redis_client import get_redis


GAME_AGENT_UA = "GameAI-Agent/1.0"

_shared_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """获取共享 HTTP 客户端（连接池复用）"""
    global _shared_client
    if _shared_client is None:
        _shared_client = httpx.AsyncClient(
            headers={"User-Agent": GAME_AGENT_UA},
            timeout=httpx.Timeout(15.0),
            follow_redirects=True,
        )
    return _shared_client


def get_headers(extra: dict | None = None) -> dict:
    """获取带统一 User-Agent 的请求头"""
    headers = {"User-Agent": GAME_AGENT_UA}
    if extra:
        headers.update(extra)
    return headers


class GameDataTool(BaseTool, ABC):
    """所有游戏数据工具的基类，提供缓存 + 重试能力"""

    name: str
    description: str
    cache_ttl: int = 300
    max_retries: int = 3
    request_timeout: int = 10

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        # 同步工具接口：在线程池新循环执行（不 close loop，见 async_utils 方针）
        from src.utils.async_utils import run_coro_sync
        return run_coro_sync(lambda: self._arun(*args, **kwargs))

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    def _cache_key(self, *args, **kwargs) -> str:
        raw = f"{self.name}:{json.dumps(args, sort_keys=True)}:{json.dumps(kwargs, sort_keys=True)}"
        return f"tool_cache:{hashlib.md5(raw.encode()).hexdigest()}"

    async def _cached_call(self, func, *args, **kwargs):
        """带缓存的 API 调用"""
        cache_key = self._cache_key(*args, **kwargs)
        try:
            redis = await get_redis()
            cached = await redis.get(cache_key)
            if cached:
                logger.debug(f"[Cache HIT] {self.name}")
                return json.loads(cached)
        except Exception as exc:
            logger.warning(f"[Cache MISS 读失败] {self.name}: {exc}")

        result = await self._call_with_retry(func, *args, **kwargs)

        try:
            redis = await get_redis()
            await redis.setex(cache_key, self.cache_ttl, json.dumps(result, ensure_ascii=False))
        except Exception as exc:
            logger.warning(f"[Cache 写失败] {self.name}: {exc}")

        return result

    async def _call_with_retry(self, func, *args, **kwargs):
        """带指数退避重试的调用"""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.request_timeout,
                )
            except asyncio.TimeoutError:
                last_error = TimeoutError(f"{self.name}: 请求超时 ({self.request_timeout}s)")
                logger.warning(f"[Retry {attempt+1}/{self.max_retries}] {last_error}")
            except Exception as e:
                last_error = e
                logger.warning(f"[Retry {attempt+1}/{self.max_retries}] {self.name}: {e}")

            if attempt < self.max_retries - 1:
                await asyncio.sleep(2 ** attempt)

        raise last_error
