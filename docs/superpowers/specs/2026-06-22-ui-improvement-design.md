# UI 改进设计文档

- **日期：** 2026-06-22
- **范围：** Streamlit 前端 6 页面全面改进
- **状态：** ✅ 已完成 (2026-06-22)
- **实施计划：** [2026-06-22-ui-improvement.md](../plans/2026-06-22-ui-improvement.md)

---

## 概述

当前 UI 存在三类问题：
1. **数据不真实** — 首页指标和热门游戏为硬编码
2. **功能不完整** — 筛选器未生效、按钮无效、区块功能重叠
3. **体验不一致** — 空状态、加载态、错误处理各页自成一派

改进分 4 批推进，每批独立可验证。

---

## 批次 A：首页数据对接

**目标：** 首页指标卡和热门游戏从假数据变为实时数据。

**改动文件：** `src/ui/_pages/home.py`

| 项 | 当前 | 改为 |
|----|------|------|
| 活跃监控 | 写死 `"0"` | 查询 `watchlist` 表 `status='active'` COUNT |
| 待读告警 | 写死 `"0"` | 查询 `price_alerts` 表 `is_read=0` COUNT |
| 新闻库 | 写死 `"0"` | 查询 ChromaDB `collection.count()` |
| 最低折扣 | 写死 `"-"` | 查 CheapShark deals 第一条的 `savings` 百分比 |
| 热门游戏 | 硬编码 5 款游戏列表 | 调用 `RAWGGameSearchTool` + `SteamCurrentPlayersTool` 动态获取 |
| 加载态 | 无 | 首次加载时显示 `st.spinner`，数据到达后渲染 |

**关键逻辑：**
- 4 个指标卡使用 `run_async_safe()` 并行获取数据
- 热门游戏使用 5 个预定义 appid 批量查询 Steam 在线人数（730, 570, 578080, 1172470, 1085660）
- 所有数据源故障时显示 `"-"` 而非崩溃

---

## 批次 B：搜索 + 推荐页修复

**目标：** 筛选器生效，「查看详情」按钮可用。

**改动文件：** `src/ui/_pages/search.py`、`src/ui/_pages/recommend.py`

### 搜索页

- 平台和类型筛选传入搜索查询。RAWG API 支持 `platforms` 和 `genres` 参数（当前工具未暴露），需在 `RAWGGameSearchTool._search()` 增加 `platforms`/`genres` 可选参数
- 「查看详情」按钮改为调用 `RAWGGameDetailTool` 并在 `st.expander` 中展开
- 无搜索结果时提示「尝试缩短关键词或减少筛选条件」

### 推荐页

- 偏好类型和平台传入推荐结果用于排序（匹配度加权）
- 每款推荐游戏增加 `st.expander` 查看详情区域
- 空推荐结果时引导用户搜索其他游戏

---

## 批次 C：新闻 + 价格监控重构

**目标：** 缓存稳健，功能区块清晰。

**改动文件：** `src/ui/_pages/news.py`、`src/ui/_pages/price_watch.py`

### 价格监控页

- 用 `run_async_safe()` 替代 `asyncio.run()`，消除事件循环冲突风险
- 监控列表改用 `st.dataframe` 表格展示
- 删除操作添加 `st.dialog` 二次确认

### 新闻页

- 搜索区块和最新资讯区块合并为统一 Tab 布局（Tab1: 新闻搜索，Tab2: 最新资讯）
- 游戏/来源/时间筛选器实际应用到 `search_news()`。当前 retriever 仅支持 `source_filter`，需扩展：`game_filter` 通过 ChromaDB metadata 过滤 `game_name` 字段，`days_filter` 通过 `published_iso` 日期比较
- 默认加载 RSS 失败时静默降级，显示引导文字而非报错

---

## 批次 D：对话页 + 全局统一

**目标：** 体验收尾。

**改动文件：** `src/ui/_pages/chat.py`、`src/ui/session_state.py`、新增 `src/ui/components/`

### 对话页

- 侧边栏从「清除历史 + 计数」改为历史对话列表（展示每条对话的前 30 字摘要）
- 点击摘要可继续该对话上下文

### 全局统一

- 新增 `src/ui/components/_loading.py` — `show_loading(message)` 上下文管理器
- 新增 `src/ui/components/_error.py` — `show_error(e, fallback_message)` 统一错误展示
- 各页改用统一组件，移除分散的 try/except + st.error/warning/info 模式

---

## 不改的部分

- `config/settings.py` — 无 UI 配置变更
- `config/agents.yaml` — Agent prompt 不变
- `src/tools/` — 工具层 API 调用逻辑不变
- `src/agents/` — Agent 行为不变
- `src/rag/` — RAG 检索逻辑不变

---

## 验证方式

每批完成后运行 `python -m streamlit run src/ui/app.py` 做手动验证：

| 批次 | 验证点 |
|------|--------|
| A | 首页指标卡显示真实数字；热门游戏列表动态变化 |
| B | 搜索页筛选器真正过滤结果；「查看详情」展开完整信息；推荐页偏好生效 |
| C | 价格监控刷新无报错；删除有确认弹窗；新闻筛选生效；RSS 故障时降级 |
| D | 对话历史侧边栏可点击切换；各页错误/加载态统一 |

---

## 实施记录 (2026-06-22)

共 15 个任务，16 个提交，全部在 `master` 分支完成。

| 提交 | 批次 | 内容 |
|------|------|------|
| `927a2b2` | A | 首页指标卡对接 DB 统计数据 |
| `d07eaf9` | A | 首页新闻库计数 + 最低折扣对接真实数据 |
| `107abdb` | A | 首页热门游戏对接 Steam 实时在线人数 |
| `4c18f0b` | B | RAWG 搜索工具增加 platforms/genres 过滤参数 |
| `a517a79` | B | 搜索页平台和类型筛选器实际生效 |
| `b2f3e05` | B | 搜索页查看详情改为内联 expander 展开 |
| `36ad9cc` | B | 推荐页偏好匹配度排序 + 内联详情展开 |
| `07adc6e` | C | Retriever 增加 game_filter 和 days_filter 支持 |
| `daf2d6e` | C | 价格监控页统一异步模式，移除 asyncio.run |
| `435831b` | C | 价格监控删除操作增加确认对话框 |
| `f83a230` | C | 新闻页改为 Tab 布局，筛选器实际生效，RSS 故障降级 |
| `8f06777` | D | 添加统一 loading 状态组件 |
| `52a8c75` | D | 添加统一错误展示组件 |
| `3a2ce62` | D | 对话页支持多轮会话管理，侧边栏历史列表 |
| `dee32f0` | D | 全局应用统一 loading 和 error 组件 |

### 新增文件
- `src/ui/components/_loading.py` — 统一 loading 上下文管理器
- `src/ui/components/_error.py` — 统一 error 上下文管理器
- `.vscode/launch.json` — VS Code 调试配置
- `.vscode/settings.json` — VS Code 工作区设置
