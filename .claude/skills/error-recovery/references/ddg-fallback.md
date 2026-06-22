# DuckDuckGo Search Failure

## 错误签名
DDG 返回 HTTP 202 + 空结果 / 8s 超时 / 0 条 `.result` 元素。

## 根因
DDG 反爬机制在当前网络触发验证页面。

## 已验证解法
项目已内置 Tavily 回退链：
```
DDG (8s) → 失败 → Tavily API (10s) → 结果
```
代码：`src/tools/web_search.py` / `src/mcp/web_search_server.py`
配置：`.env` 中 `TAVILY_API_KEY`
