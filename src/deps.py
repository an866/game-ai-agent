"""依赖组合根 —— 进程级单例的唯一定义处

背景：engine/session_factory/redis_pool/chroma_store/agent 此前各自
模块级惰性单例、互不知晓，测试无法替换。此处统一登记惰性工厂：
- get_* 惰性构造 + 缓存（首次调用才建）
- override() 提供测试注入，with 退出还原
- reset_all() 供测试隔离与 settings 变更后重建

约定：业务代码一律通过 get_* 取依赖，不要缓存到模块级变量；
这样 override/reset 才能生效。
"""

from contextlib import contextmanager
from typing import Any, Callable, Iterator

_factories: dict[str, Callable[[], Any]] = {}
_instances: dict[str, Any] = {}
_saved: list[tuple[str, Callable[[], Any]]] = []


def _register(key: str, factory: Callable[[], Any]) -> None:
    _factories[key] = factory


def _get(key: str) -> Any:
    if key not in _instances:
        _instances[key] = _factories[key]()
    return _instances[key]


def reset_all() -> None:
    """清空已构造实例（测试隔离 / settings 变更后重建）"""
    _instances.clear()


@contextmanager
def override(key: str, impl: Any) -> Iterator[None]:
    """临时替换某依赖的实现；with 退出后还原（测试用）"""
    _saved.append((key, _factories[key]))
    _factories[key] = (lambda v: lambda: v)(impl)
    _instances.pop(key, None)
    try:
        yield
    finally:
        _factories[key] = _saved.pop()[1]
        _instances.pop(key, None)


def _register_defaults() -> None:
    """注册全部生产实现（惰性执行，避免与各模块循环 import）"""
    if _factories:
        return

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from config.settings import get_settings

    def _engine():
        settings = get_settings()
        return create_async_engine(
            settings.mysql_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )

    def _session_factory():
        return async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )

    def _redis():
        import redis.asyncio as redis
        settings = get_settings()
        return redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password or None,
            decode_responses=True,
        )

    def _vector_store():
        from src.rag.store import _create_store
        return _create_store()

    def _graph():
        from src.agents.graph import build_graph
        return build_graph()

    def _general_agent():
        from src.agents.graph import _create_general_agent
        return _create_general_agent()

    def _recommend_agent():
        from src.agents.recommend import _create_recommend_agent
        return _create_recommend_agent()

    _register("engine", _engine)
    _register("session_factory", _session_factory)
    _register("redis", _redis)
    _register("vector_store", _vector_store)
    _register("graph", _graph)
    _register("general_agent", _general_agent)
    _register("recommend_agent", _recommend_agent)


# ---- 对外 getter（首次调用即完成默认注册）----

def get_engine():
    _register_defaults()
    return _get("engine")


def get_session_factory():
    _register_defaults()
    return _get("session_factory")


def get_redis():
    _register_defaults()
    return _get("redis")


def get_vector_store():
    _register_defaults()
    return _get("vector_store")


def get_graph():
    _register_defaults()
    return _get("graph")


def get_general_agent():
    _register_defaults()
    return _get("general_agent")


def get_recommend_agent():
    _register_defaults()
    return _get("recommend_agent")