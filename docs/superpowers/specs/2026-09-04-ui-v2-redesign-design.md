# UI V2 重设计 —— 聊天主场 · 三套主题 · 单页面板架构

日期：2026-09-04

## 背景与目标

现有 UI（Streamlit 多页 `st.navigation` + 6 个 `_pages/*`）经上一轮重构后逻辑层（services/theme-agnostic）已干净，但界面本身仍是
默认 Streamlit 外观、6 页平等导航、聊天不是焦点。本轮重设计 UI 模块（约 812 行 → 预计 1200+ 行）：

1. **以聊天为中心**：聊天是唯一主场，其余功能降级为"随唤随走"的工具面板
2. **信息架构重排**：单页面板架构，图标栏 6 入口
3. **交互体验升级**：三列布局、流式打磨、胶囊筛选、面板状态隔离
4. **视觉升级**：三套可切换主题（霓虹电竞默认 / 暗夜游戏风 / 明亮现代）

**范围边界**：只动 `src/ui/`。后端（services / agents / tools / data / config）零改动——
上一轮重构的成果（deps、llm 工厂、services、事务边界、async 方针）原样复用。

## 决策记录（用户已确认）

| # | 决策 | 选择 |
|---|---|---|
| D1 | 布局方向 | **A · 聊天主场 + 图标侧栏**（Discord 式） |
| D2 | 视觉风格 | **霓虹电竞为默认**，暗夜游戏风、明亮现代为可切换主题（三套色板） |
| D3 | 会话列表形态 | **X · 三列式**：图标栏 + 会话列 + 聊天区 |
| D4 | 实现架构 | **方案 1 · 单页面板架构**；`st.fragment` 优化与真 SSE 记为后续备选 |
| D5 | 图标栏顺序 | 💬 对话 → 🏠 概览 → 🎯 推荐 → 💰 价格 → 📰 新闻 → 🔍 搜索 |
| D6 | 流式输出 | 保留现有 `stream_sync` + `astream_events` 管线（等价 SSE 效果），打磨渲染体验；真 SSE（FastAPI+EventSource）作后续备选 |
| D7 | 主题实现 | CSS 变量 + 运行时注入（不依赖 Streamlit 内置主题） |

### 执行偏差（Task 9 收尾注记）

- 快捷指令胶囊最终语义：**点击即发送**（原设计"填入不发送"因 Streamlit 无法
  区分填充 run 与后续 run 而放弃；与"停止按钮"同类限制）。
- 其余偏差：悬浮复制按钮 / 气泡平滑动画未实现（装饰性，与 V1 一致）；
  inject_theme 兜底仅覆盖非法主题名（异常注入不再静默吞错）；
  会话删除无 st.dialog 确认（V1 亦为直接删除）。均记录在案，不做返工。

## 布局架构

```
Streamlit 窗口
├─ 侧栏 = 图标栏（64px）        ：6 图标 + 底部主题切换器（3 色块按钮）
└─ 主区
   ├─ 聊天模式：st.columns([1, 4]) = 会话列 + 聊天区
   └─ 工具模式：整宽渲染面板，顶部"← 返回对话"面包屑
```

- 图标栏用 Streamlit 原生 sidebar（自然支持窄屏折叠；V1 多页侧栏消失，替代为图标列）
- 点击图标切换 `ui["tab"]`；再点当前图标回到聊天（或面包屑返回）
- 面板返回聊天时不丢面板状态（见状态管理）

## 状态管理

- `st.session_state["ui"]` 唯一 UI 状态对象，由 `src/ui/ui_state.py` 统一读写：
  ```
  ui = {
    "tab": "chat" | "overview" | "recommend" | "price" | "news" | "search",
    "theme": "neon" | "night" | "light",
    "panel_state": { search: {...}, price: {...}, ... }  # 面板各自命名空间
  }
  ```
- 面板切换不丢状态：搜索结果、筛选条件、监控表单都留在 `panel_state` 内
- 聊天的 `chat_sessions` / `active_session_id` 既有 session_state 体系保留不动
- 数据获取仍走 `src/services/*` + `st.cache_data`（服务层零改动）

## 主题系统（theme.py）

三套 CSS 变量组，运行时注入 `:root`：

| 变量 | 霓虹电竞 neon（默认） | 暗夜游戏风 night | 明亮现代 light |
|---|---|---|---|
| `--bg` | `#0a0a12` | `#0f1420` | `#f3f5fa` |
| `--panel` | `#12121e` | `#171f31` | `#ffffff` |
| `--panel-2`（次级面板） | `#181834` | `#1e2942` | `#f8fafc` |
| `--accent1` | `#ff3d81` | `#2b4a9e` | `#3a6ff0` |
| `--accent2` | `#a855f7` | `#3b6ad8` | `#3a6ff0` |
| `--ok` | `#22d3ee` | `#4ade80` | `#16a34a` |
| `--warn` | `#f0a03a` | `#f0a03a` | `#d97706` |
| `--danger` | `#ff5d5d` | `#ef4444` | `#dc2626` |
| `--text` | `#e8e8ff` | `#c8d3ea` | `#33415c` |
| `--text-dim` | `#8a8ab8` | `#8a97b8` | `#5a6b8a` |
| `--border` | `#2a2a55` | `#2c3c61` | `#e0e5f0` |
| `--glow`（发光） | `0 0 12px rgba(255,61,129,.35)` | `none` | 柔和阴影 |

- `get_theme_css(theme) -> str` 纯函数：主题名 → 完整 CSS（`:root` 变量 + `.stApp` 背景/输入框/按钮/表格/dialog 覆盖）
- 注入：`st.markdown(get_theme_css(ui["theme"]), unsafe_allow_html=True)`
- 切换：图标栏底部三色块按钮 → `ui["theme"]` 变更 → 整页重跑重新注入
- 硬性约定：V2 起 UI 代码禁止裸 HEX 颜色，一律走变量（单测可查）
- 失败降级：CSS 注入异常静默回退默认霓虹，不阻断渲染

## 聊天中心（src/ui/chat/）

### session_list.py —— 会话列
- 顶部：➕ 新建对话、会话搜索框
- 列表项：标题、轮数、摘要标记 📋；当前项 accent 高亮边框
- 删除：🗑 → `st.dialog` 确认（迁移现有逻辑）
- 宽度主区 1/4，窄屏随 Streamlit 折叠

### message_list.py —— 气泡流
- 用户气泡：`--accent1→--accent2` 渐变、右对齐、霓虹下带外发光
- 助手气泡：`--panel-2` 左对齐；悬浮复制按钮
- 流式渲染：保留 `stream_sync(chat_stream)` 管线原样；打字光标动画（`▌` 平滑闪烁）、
  气泡平滑出现、进度文案（NODE_LABELS）以极小字号置于气泡上方、流式"停止"按钮
- 空态引导：无消息时 3 个示例问题卡（点击直接发送）

### quick_commands.py —— 快捷指令
- 输入框上方胶囊：💰 查价格 / 🎯 找推荐 / 📰 看新闻 / 🔍 搜游戏
- 点击：填入输入框（不自动发送）；`/price` 等文本指令继续兼容

### chat_panel.py —— 编排
- 三列数据流、会话创建/切换、`_after_message` 持久化管线（ChatService）迁移至此

## 工具面板×5（src/ui/panels/，由现有 `_pages/*` 迁移）

| 面板 | 迁移要点 |
|---|---|
| overview | 原 home：统计卡升级（霓虹渐变数字 + icon）、热门游戏、快捷入口卡（直达对应面板） |
| search | 原 search：筛选器改可折叠胶囊、结果用升级版 game_card |
| price | 原 price_watch：监控表单卡片化、价格数字 `--ok` 强调、告警 Tab 保留 |
| news | 原 news：双 Tab、时间筛选胶囊、rss_card 升级 |
| recommend | 原 recommend：画像已生效小标签（build_profile_text 非空时显示）、推荐卡流 |

统一：面板顶部"← 返回对话"面包屑；面板内状态挂 `ui["panel_state"][<panel>]`。

## 组件升级（components/）

- `game_card`：渐变描边卡片 + 折扣价标签（`--ok`）
- `rss_card` / 新增 `metric_card`（统计卡）：全部 CSS 变量驱动
- `_loading` / `_error`：接口不变，配色变量化
- `chat/` 下组件为 V2 新增

## 错误处理与降级

- 面板级 `show_error` + loguru 既有管线不变
- 主题注入失败回退默认主题
- 聊天流式抛错 → 现有 error 事件文案机制保留

## 文件结构（V2 目标）

```
src/ui/
  app.py              # 主壳：图标栏 + 模式分发 + 主题注入
  theme.py            # 新增：3 套 CSS 变量 + get_theme_css + 注入
  ui_state.py         # 新增：ui 状态对象读写（替代 session_state.py 大部分职责）
  chat/{__init__,chat_panel,session_list,message_list,quick_commands}.py   # 新增
  panels/{__init__,overview,search,price_watch,news,recommend}.py          # 由 _pages 迁移
  components/         # game_card / rss_card / metric_card / _loading / _error
  session_state.py    # 保留：仅聊天会话体系（chat_sessions 等），通用部分并入 ui_state
```

删除：`src/ui/_pages/`（6 文件迁移后移除）。

## 测试与验证

| 类型 | 内容 |
|---|---|
| 单测 | `theme.py`：3 套变量键集合一致、无缺失/非法值、无裸 HEX 漏网（扫描 components/panels/chat 源码） |
| 单测 | `ui_state.py`：分区读写、面板切换不丢状态 |
| 单测 | import sweep 自动覆盖新目录（test_imports.py 已参数化全模块） |
| 手动冒烟 | 三主题 × 6 面板；流式 3 意图（价格/推荐/新闻）；面板切换返回状态保留；窄屏折叠；对话框确认 |
| 回归 | `py -3.14 -m pytest -q` 全绿（UI 层改动不应影响 86 个既有用例） |

## 后续优化备选（本轮不做，记录在案）

1. `st.fragment` 面板隔离（面板操作不重跑聊天渲染）
2. 真 SSE 流式通道（FastAPI + EventSource / 自定义组件）——若 V2 流式仍不满足体验
3. 会话列拖拽排序 / 会话导出