# 游戏 AI 助手（Game AI Agent）

面向 PC 游戏场景的智能助手：**对话问答 / 游戏查询 / 跨商店比价 / 资讯聚合 / 相似推荐**。  
后端为 LangGraph 多智能体编排 + 多源游戏数据工具，前端为 Streamlit 单页应用（DeepSeek 风格对话 UI）。

> 请通过 `python -m src.main …` 在项目根目录运行，不要直接 `python src/main.py`（`sys.path` 会缺失）。

## 功能

| 模块 | 能力 |
|------|------|
| **对话** | 意图路由 → 查游戏 / 比价格 / 要推荐 / 看新闻 / 闲聊；流式输出、会话管理、消息压缩 |
| **概览** | 监控数、告警、新闻库、折扣摘要 + Steam 热门在线（并行加载） |
| **搜索** | 按名称搜游戏（RAWG 优先，失败回退 Steam） |
| **推荐** | 基于种子游戏的相似推荐；RAWG `suggested` 不可用时精选列表 / 同类型 / 联网兜底 |
| **价格** | CheapShark + ITAD 比价、目标价监控、降价告警 |
| **新闻** | RSS / Steam / RAG 检索 + 联网兜底；单源超时，不拖死整页 |

## 技术栈

- **Python 3.14** · LangChain / LangGraph · OpenAI 兼容 LLM（如 DeepSeek）
- **Streamlit** 单页 UI（主题 CSS 变量 · 无业务逻辑，只调 services）
- **MySQL**（会话/监控）· **Redis**（工具结果缓存）· **Chroma**（新闻向量，可选本地 embedding）
- 数据源：Steam / RAWG / CheapShark / ITAD / RSS / DuckDuckGo（Tavily 可选回退）

## 架构速览

```
CLI (src/main.py)
  ├─ ui         → Streamlit  src/ui/app.py
  ├─ scheduler  → APScheduler（价格 6h / 新闻 2h 等）
  └─ init-db    → 建表

src/ui/         页面与组件（聊天 DeepSeek 风格；工具面板）
src/services/   业务层（chat / price_monitor / watchlist / dashboard / game_lookup）★ UI 唯一数据入口
src/agents/     LangGraph：router → query|price|recommend|news|general → aggregator
src/llm.py      LLM 工厂（角色温度 / streaming / 超时）
src/tools/      API 工具（缓存 + 重试 + soft-fail）
src/rag/        新闻向量检索（doc_count 不强制加载模型）
src/deps.py     进程级单例组合根
src/utils/      异步桥：进程级**单一**共享事件循环（禁止每消息 new loop）
config/         pydantic-settings + YAML
```

### 重要工程约定（摘录）

- 异步只用 `run_async_safe` / `stream_sync` / `run_coro_sync` / `submit_coro`；**禁止** `asyncio.run`、`loop.close()`、每条消息 `new_event_loop`。
- HTTP 一律 `get_http_client()`；工具走 `GameDataTool._arun`（缓存/重试）。
- LLM 温度 / streaming 集中在 `src/llm.py`；意图路由在 `src/agents/graph.py::INTENT_ROUTE`。
- UI **禁止裸 HEX**，颜色走 `src/ui/theme.py` CSS 变量。
- Repository **不做 commit**；事务在 service 层。

## 快速开始

### 1. 依赖

```bash
pip install -r requirements.txt
```

### 2. 配置（切勿把真实 Key 提交到仓库）

```bash
cp .env.example .env
```

在 `.env` 中填写（均保持在本地 / 私有环境）：

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `LLM_MODEL` | OpenAI 兼容端点与模型 |
| `LLM_REQUEST_TIMEOUT` / `LLM_MAX_RETRIES` | LLM 请求超时与重试（可选，默认见 settings） |
| `EMBEDDING_MODEL` | 设为 `local` 可用本机中文向量模型 |
| `RAWG_API_KEY` / `ITAD_API_KEY` | 游戏库 / 比价；未配置时自动降级 Steam/联网 |
| `STEAM_API_KEY` / `TAVILY_API_KEY` | 可选 |
| `MYSQL_*` / `REDIS_*` | 数据库与缓存 |

**安全**

- `.env` 已在 `.gitignore` 中，**不要**提交真实密钥。
- 克隆本仓库后只需复制 `.env.example` → `.env` 再填自己的 Key。
- 若曾把密钥写进文档或旧提交，请在对应平台**轮换密钥**。

### 3. 初始化与运行

```bash
# 建表（需 MySQL 可用）
py -3.14 -m src.main init-db

# 可选：后台调度（价格巡检 / 新闻抓取）
py -3.14 -m src.main scheduler

# 前端（默认 http://localhost:8501）
py -3.14 -m src.main ui
```

Windows 下若使用 Python 启动器，请将 `py -3.14` 换成你的 `python` 版本。

Redis 未启动时工具缓存会降级（功能仍可用，但更慢）。本地可用：

```powershell
# 示例：本机 Redis 可执行文件路径按实际安装调整
redis-server
```

## 对话 UI（DeepSeek 风格）

- 用户消息：右侧气泡；助手消息：Markdown 正文（无重气泡）
- 空态欢迎 + 建议问题；`st.chat_input` 沉底输入
- 会话列表：左键切换；**右键标题**弹出 重命名 / 置顶 / 分享 / 多选 / 删除（后四者为占位，删除已实现）；另有 `⋯` 菜单备份
- 主题：`neon` / `night` / `light`（侧栏可切换）
- 复制快捷键：已屏蔽 Streamlit 清缓存对 Ctrl+C 的误触发

## 测试

```bash
py -3.14 -m pytest
py -3.14 scripts/smoke_check.py
# 可选：SMOKE_DB=1 时额外探测 MySQL/Redis
```

- 默认排除 `@pytest.mark.integration`（见 `pytest.ini`）
- 服务层测试使用 fake repository，不依赖真实外网 API

## 仓库与许可

- 远程示例：GitHub `an866/game-ai-agent` · 极狐 GitLab `an164138/game-ai-agent`
- 开发者约定与目录细节见 [`CLAUDE.md`](./CLAUDE.md)
- 历史 README 备份：[`docs/README.backup-20260912.md`](./docs/README.backup-20260912.md)

未声明开源协议时，按仓库所有者约定使用；对外分享前请再次确认不含密钥与私有配置。
