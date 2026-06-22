---
name: error-recovery
description: >
  Use when encountering any error in the game-ai-agent project —
  Python path issues, GateGuard denials, encoding errors, API failures,
  async conflicts, tool blocking, or search API issues.
  This skill catalogs recurring errors with verified fixes so you never
  waste time re-diagnosing known problems. Check it BEFORE debugging
  from scratch.
---

# Error Recovery — game-ai-agent 错误速查

当在本项目中遇到错误时，**先查此处**。每条错误都有签名 → 根因 → 已验证解法的完整链路。

## 如何使用

1. 遇到错误时，先匹配「错误签名」表
2. 命中后打开对应的 `references/<file>.md` 查看详细解法
3. 如果错误不在表中，按相同格式新增一条 reference 文档

## 错误签名速查

| 签名 | 参考文件 |
|------|----------|
| `ModuleNotFoundError: No module named 'config'` | [python-path.md](references/python-path.md) |
| GateGuard denial — 首次编辑/写入被拒 | [gateguard.md](references/gateguard.md) |
| `UnicodeEncodeError: 'gbk' codec` | [encoding.md](references/encoding.md) |
| `401 Unauthorized` from external API | [api-401.md](references/api-401.md) |
| `asyncio.run()` event loop error | [async-conflict.md](references/async-conflict.md) |
| DuckDuckGo 搜索超时/空结果 | [ddg-fallback.md](references/ddg-fallback.md) |
| Write tool blocked by classifier | [tool-blocked.md](references/tool-blocked.md) |
| Steam/RAWG Chinese search returns 0 | [chinese-search.md](references/chinese-search.md) |

## 新增错误

发现新错误模式时：
1. 在 `references/` 下新建 `<name>.md`
2. 包含：错误签名 / 根因 / 已验证解法 / 代码示例
3. 更新上方速查表
