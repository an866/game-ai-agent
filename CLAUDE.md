# CLAUDE.md

游戏 AI 助手（LangGraph + Streamlit）的开发者指南。

## 目录地图

- `src/main.py` — CLI 入口（ui / scheduler / init-db），必须 `python -m src.main` 运行
- `src/ui/` — Streamlit 页面。**页面只调 services + st.cache_data + run_async_safe**，不直接碰 repository/engine/agent
- `src/services/` — 业务服务层（chat_service / price_monitor_service / watchlist_service / dashboard_service），UI 与 scheduler 的唯一数据入口
- `src/agents/` — LangGraph graph（router→5 专业节点→aggregator）；各专业节点是 agent 文件的薄包装
- `src/llm.py` — LLM 工厂。**新建 agent/LM 调用一律走 `get_llm(role)`**；新角色先在此登记温度
- `src/deps.py` — 组合根。进程级单例（engine/session_factory/redis/vector_store/graph/agents）只能在这里注册；测试用 `override()` 
- `src/tools/` — API 工具。继承 `GameDataTool` 自动获得缓存/重试/超时；HTTP 请求必须走 `get_http_client()`
- `src/data/repository.py` — **不做 commit**（见决策记录）；只暴露增删改查 + flush
- `src/utils/async_utils.py` — 事件循环方针的唯一实现处（不 close loop）
- `config/settings.py` — pydantic-settings；`config/loader.py` — YAML 单例加载器

## 铁律（断链高发点）

1. **新增/删除模块后必须跑** `py -3.14 -m pytest tests/test_imports.py -q`——它枚举全部模块逐个 import，
   任何 ImportError 立刻显形。历史上 web_search.py / stream_bridge.py 缺失、langchain 1.x API 变更
   （create_react_agent→create_agent）都靠它拦截，视为 CI 级门槛。
2. 工具/HTTP 统一 `get_http_client()`；禁止新建 `httpx.AsyncClient()`、禁止硬编码 UA。
3. `GameDataTool._arun` 优先；scheduler/agent 不要直接调 `_search_*` 私有方法（会绕过缓存/重试）。
4. 异步桥接只用 `run_async_safe` / `stream_sync` / `run_coro_sync`；**禁止 `asyncio.run` 和 `loop.close()`**
   （SQLAlchemy 池清理崩溃的历史教训，见 git 6aa30a7 前后）。
5. 温度、意图路由映射只能改 `src/llm.py` 与 `src/agents/graph.py::INTENT_ROUTE`。

## 约定

- 测试：`tests/` 下按模块分文件；依赖真实 DB/API 的用例标 `@pytest.mark.integration`（默认被 `pytest.ini` 排除）；
  服务层测试用 fake repository（参考 tests/test_chat_service.py 的 monkeypatch 模式）。
- 提交：一个逻辑变更一个 commit，每条消息带 `feat/fix/refactor/docs/test` 前缀（见 git log 风格）。
- 依赖单例（LLM/DB session）不要缓存到模块级变量——`get_settings()`/`deps.get_*()` 惰性取用，否则测试无法注入。
- 新增模块的注册位：LLM → `src/llm.py`；进程级单例 → `src/deps.py`；页面数据 → `src/services/`。

## 运行验证

```bash
py -3.14 -m pytest -q                                  # 单测
py -3.14 scripts/smoke_check.py                        # 冒烟（1XX 检查通过即 OK）
py -3.14 -m src.main ui                                # 前端手动冒烟
```