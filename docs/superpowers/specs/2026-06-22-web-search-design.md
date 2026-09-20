# 联网搜索工具设计文档

- **日期：** 2026-06-22
- **范围：** 通用联网搜索能力 —— DDG + Tavily 两级回退
- **状态：** ✅ 已完成

---

## 概述

项目原有的 Steam/RAWG/CheapShark 等 API 只能查询游戏元数据，无法回答开放性问题（如「红色沙漠什么时候发售」「鸣潮最新版本评价」）。新增通用联网搜索能力解决此问题。

## 架构

```
用户提问
    │
    ▼
Query Agent (ReAct)
    │
    ├─ SteamSearch / RAWGGameSearch / ...（优先，快速）
    │
    └─ WebSearch（回退，联网）
        │
        ├─ [1] DuckDuckGo HTML 搜索 (8s 超时)
        │   ├─ 成功 → 返回结果
        │   └─ 超时/无结果/被拦截 → 进入回退
        │
        └─ [2] Tavily API (10s 超时)
            ├─ 成功 → 返回结果
            └─ 失败 → "搜索失败" 降级提示
```

## 双层回退策略

| 层 | 方案 | 费用 | 方式 | 超时 |
|----|------|------|------|------|
| 1 | DuckDuckGo | 免费 | HTML 抓取 | 8s |
| 2 | Tavily | 月免 1000 次 | Python SDK | 10s |

## 实现

### 项目内工具 (LangChain Agent)

- **文件：** `src/tools/web_search.py`
- **类：** `WebSearchTool` 继承 `GameDataTool`
- **接入：** Query Agent 工具列表

### MCP Server (独立复用)

- **文件：** `src/mcp/web_search_server.py`
- **框架：** `mcp` 包 v1.27.2 + `FastMCP`
- **传输：** stdio
- **暴露工具：** `web_search(query, max_results=5)`
- **配置：** `.claude/mcp.json`

### 依赖

- `httpx` — HTTP 客户端 (已有)
- `BeautifulSoup` — HTML 解析 (已有)
- `tavily-python` — Tavily SDK (新增)
- `mcp` — MCP 协议框架 (用于 MCP Server, 已有)

## 配置

### .env
```
TAVILY_API_KEY=tvly-REDACTED
```

### .claude/mcp.json
```json
{
  "mcpServers": {
    "web-search": {
      "command": "python",
      "args": ["-m", "src.mcp.web_search_server"],
      "env": {
        "TAVILY_API_KEY": "tvly-REDACTED",
        "PYTHONPATH": "D:/ClaudeAI/game-ai-agent"
      }
    }
  }
}
```

## 使用方式

### 项目内
Query Agent 自动调用，当 Steam/RAWG 无法回答时触发。

### MCP（跨项目）
Claude Code 加载后，在任意会话中均可调用 `web_search` 工具。

## 测试结果 (2026-06-22)

| 查询 | DDG | Tavily | 结果 |
|------|-----|--------|------|
| 鸣潮 Wuthering Waves | 反爬 | 正常 | Wikipedia + Epic + X |
| 红色沙漠 Crimson Desert | 反爬 | 正常 | Wikipedia + Pearl Abyss 官方 |
| CS2 在线人数 | - | - | 走 SteamCurrentPlayers 更快 |

当前环境 DDG 返回验证页面，实际使用中走 Tavily 回退路径。对用户完全透明。

## 保存现有

`src/tools/web_search.py`（LangChain 工具版）和 `src/mcp/web_search_server.py`（MCP 版）独立共存。
