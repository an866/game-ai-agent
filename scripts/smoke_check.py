"""冒烟检查 —— import 全量 + 配置完整性 + 可选 DB/Redis/Chroma 探测

用法:
    py -3.14 scripts/smoke_check.py             # import + settings 完整性
    SMOKE_DB=1 py -3.14 scripts/smoke_check.py  # 额外 ping MySQL/Redis/Chroma

退出码 0 = 通过。任何一级失败打印原因并不为 0 退出。
"""

import importlib
import os
import pkgutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Windows 控制台默认 GBK，无法输出 ✓/中文 —— 强制 UTF-8 输出
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"

failures: list[str] = []


def ok(msg: str):
    print(f"{GREEN}✓{RESET} {msg}")


def fail(msg: str):
    print(f"{RED}✗{RESET} {msg}")
    failures.append(msg)


def main() -> int:
    print("== 1/3 全模块 import ==")
    modules = ["src.main", "scripts.init_db", "src.deps", "src.llm", "src.services"]
    import src.main  # noqa: F401 确保 ROOT 被加入 sys.path 后 src 可解析
    for package in ("src.agents", "src.data", "src.mcp", "src.rag",
                    "src.scheduler", "src.services", "src.tools",
                    "src.utils", "src.ui"):
        pkg = importlib.import_module(package)
        for mod_info in pkgutil.walk_packages(pkg.__path__, prefix=f"{package}."):
            modules.append(mod_info.name)
    modules = sorted(set(modules))

    for name in modules:
        try:
            importlib.import_module(name)
        except Exception as exc:
            fail(f"{name}: {type(exc).__name__}: {exc}")
    ok(f"import {len(modules)} 个模块"
       if not failures else f"import 完成，{len(failures)} 个失败")

    print("== 2/3 配置完整性 ==")
    try:
        from config.settings import get_settings
        s = get_settings()
        # 字段存在性（值允许为空——本地开发可不配 key）
        required_fields = ["openai_api_key", "llm_model", "mysql_url",
                           "redis_host", "memory_max_messages", "tavily_api_key"]
        missing = [f for f in required_fields if not hasattr(s, f)]
        assert not missing, f"缺失字段: {missing}"
        # mysql_url 格式检查（protocol 正确即认为可解析）
        assert s.mysql_url.startswith("mysql+aiomysql://"), "mysql_url 协议异常"
        ok("settings 字段齐全，mysql_url 格式正确")
    except Exception as exc:
        fail(f"settings: {exc}")

    if os.environ.get("SMOKE_DB") == "1":
        print("== 3/3 DB 探测 ==")
        import asyncio
        from sqlalchemy import text

        async def _probe() -> None:
            # MySQL
            try:
                from src.deps import get_session_factory
                async with get_session_factory()() as session:
                    await session.execute(text("SELECT 1"))
                ok("MySQL SELECT 1 通过")
            except Exception as exc:
                fail(f"MySQL: {exc}")
            # Redis
            try:
                from src.data.redis_client import get_redis as gr
                redis = await gr()
                if await redis.ping():
                    ok("Redis ping 通过")
                else:
                    fail("Redis ping 失败")
            except Exception as exc:
                fail(f"Redis: {exc}")
            # Chroma
            try:
                from src.rag.store import get_doc_count
                ok(f"Chroma 打开，文档数={get_doc_count()}")
            except Exception as exc:
                fail(f"Chroma: {exc}")

        asyncio.run(_probe())

    if failures:
        print(f"\n{RED}冒烟失败：{len(failures)} 项{RESET}")
        return 1
    print(f"\n{GREEN}冒烟全部通过 ✓{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())