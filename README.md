# 游戏 AI 助手

PC 游戏信息查询、价格追踪、新闻聚合、智能推荐的 AI 助手。基于 LangChain/LangGraph 多智能体编排，Streamlit 前端。

## 架构

```
src/main.py  ──┬─ ui        → Streamlit (src/ui/app.py → _pages/*6)
 (CLI 入口)    ├─ scheduler → APScheduler (价格巡检 6h / 新闻抓取 2h / 清理 3:07)
               └─ init-db   → 建表

src/ui/            Streamlit 页面（无业务逻辑，只调 services + st.cache_data）
src/services/      业务服务层（ChatService / price_monitor / watchlist / dashboard）★ 页面唯一数据入口
src/agents/        LangGraph Supervisor：router → query|price|recommend|news|general → aggregator
src/llm.py         LLM 工厂（角色温度表 + 惰性单例）★ 全项目唯一 ChatOpenAI 构造点
src/tools/         API 工具（GameDataTool 基类：Redis 缓存 + 重试 + 超时）
src/rag/           ChromaDB 新闻索引（scheduler 写、news 页读）
src/scheduler/     APScheduler 任务（逻辑在 services/，此处只是壳）
src/data/          repository（无 commit，事务归 service）+ models + redis
src/deps.py        组合根（进程级单例唯一定义处，override() 供测试注入）
src/utils/         stream_bridge / async_utils（单例线程池 + 不 close loop）
config/            settings.py（pydantic-settings）/ loader.py（YAML 单例加载器）
```

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env        # 填入各 API Key
py -3.14 -m src.main init-db    # 建表（需 MySQL）
py -3.14 -m src.main scheduler  # 后台任务（可选）
py -3.14 -m src.main ui         # 启动前端 http://localhost:8501
```

> 注意：`python src/main.py` 直接运行会因 sys.path 缺失而失败，必须用 `python -m src.main`（从项目根目录）。

## 配置（.env）

| 变量 | 默认 | 说明 |
|---|---|---|
| OPENAI_API_KEY / BASE_URL / LLM_MODEL | — / api.openai.com / gpt-4o-mini | 语言模型；兼容任意 OpenAI 风格端点 |
| EMBEDDING_MODEL | text-embedding-3-small | 设为 `local` 用本机 text2vec（cpu） |
| RAWG_API_KEY / ITAD_API_KEY / STEAM_API_KEY / TAVILY_API_KEY | 空 | 外部 API（Tavily 仅作 DDG 搜索回退，可不配） |
| MYSQL_* / REDIS_* | localhost / game_agent | MySQL 8 + Redis 6+ |
| PRICE_CHECK_INTERVAL_HOURS / NEWS_FETCH_INTERVAL_HOURS | 6 / 2 | 调度间隔 |
| TIMEZONE | Asia/Shanghai | 调度器时区 |
| MEMORY_MAX_MESSAGES / MEMORY_COMPRESS_THRESHOLD / MEMORY_RECENT_KEEP | 20 / 0.85 / 8 | 对话压缩窗口 |

## 测试

```bash
py -3.14 -m pytest              # 单测（默认排除 integration）
py -3.14 scripts/smoke_check.py # import + 配置完整性冒烟（SMOKE_DB=1 时含 DB/Redis 探测）
```

测试覆盖：导入断链回归、deps 注入、LLM 工厂、ChatService（fake repo）、价格巡回去重、路由映射、web 搜索回退链。

## 架构决策记录

- **48h 告警去重**（C10）：同一监控项 48h 窗口内只触发一次告警；"全部已读"按钮清除窗口以便重发。
- **线程池 + 不 close 事件循环**（C13/C7）：SQLAlchemy 异步引擎析构需要存活的事件循环；每个桥接任务新建 loop 且不主动关闭（GC 回收），线程池为进程级单例。**不要**在别处新增 `loop.close()`。
- **Repository 不做 commit**（C12）：事务边界归 service 层；repo 的增改删只作用于 session，调用方统一 commit/rollback。
- **LLM 温度唯一真源**是 `src/llm.py` 的 ROLE_TEMPERATURES；改温度只改那里，不要散落硬编码。
- **意图→节点映射唯一真源**是 `src/agents/graph.py` 的 INTENT_ROUTE；加新意图时同步加节点与 `NODE_LABELS`。
- **MCP server 安全**：`.claude/mcp.json` 不存 API key（从 .env 读）；模板见 `.claude/mcp.example.json`。仓库 git 历史中曾出现过 Tavily key 明文，使用过旧配置的请轮换。

## MCP（可选）

可向本仓库的桌面版 Claude 注册联网搜索工具：

```bash
cp .claude/mcp.example.json .claude/mcp.json
```

server 从 `.env` 的 `TAVILY_API_KEY` 读取搜索回退 key；未配置时 DDG 免费通道仍可用。