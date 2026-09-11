---
feature: deepseek-chat-ui
status: delivered
updated: 2026-09-11
branch: current working tree (sandbox blocked `git worktree add`)
commits: uncommitted local changes on detached HEAD a24c006
---

# DeepSeek 风格对话 UI

## Report

**What was built** — 对话面板改为 DeepSeek 网页版形态：用户右侧实心气泡、助手无重气泡并走 Markdown 渲染、空态居中欢迎与建议问题卡片、通栏输入、会话列表弱化轮次噪音。配色仍绑定 neon/night/light CSS 变量，聊天代码无裸 HEX。

**Verification** — `py -3.14 -m pytest -q` → 239 passed；UI `http://127.0.0.1:8501` HTTP 200；`tests/test_message_list.py` / `test_theme.py` / `test_chat_panel.py` / `test_app_shell.py` 通过。

**Journey log**
- 环境禁止 `git worktree add`（隔离子会话），按覆盖规则在当前工作树实现。
- Streamlit 无法把 Markdown 嵌进 HTML div，助手消息改为纯 `st.markdown`。
- 评审修复：键盘提交 pending+rerun + `st.chat_input`（新回复不再画在输入框下）；`last_submitted` 按会话 sid 键控并在切换时重置；删除无效 sticky 输入条与未接线 CSS。

## [S1] Problem

现有对话页是「双侧彩色气泡 + 生硬输入框 + 三列工具感布局」，与 DeepSeek 网页版聊天体验差距大：
用户气泡过重、助手回复被 HTML 转义导致 Markdown 表格不渲染、空态没有欢迎感、输入区不像对话产品。

## [S2] Design

### 范围
- 仅改对话面板：`src/ui/chat/*` + 主题中与聊天相关的 CSS 覆盖。
- 概览/推荐/价格/新闻/搜索面板、agent 后端、流式管线（`chat_stream`/`stream_sync`）不动。
- 颜色继续走现有 `neon` / `night` / `light` CSS 变量；聊天代码禁止裸 HEX（`tests/test_theme.py`）。

### 视觉与结构（对齐 DeepSeek 网页版）
1. **用户消息**：右侧实心气泡（accent 渐变），圆角，最大宽约 72%，纯文本转义。
2. **助手消息**：左侧**无重气泡**——贴左正文区，用 Streamlit Markdown 渲染（表格/列表可渲染），流式光标用字符 `▌`。
3. **空态欢迎**：居中「有什么可以帮你的？」+ 副标题 + 4 个建议问题卡片；点击即发送。
4. **输入区**：主聊天下方通栏输入，placeholder 引导示例；`last_submitted` 防重逻辑保留。
5. **会话列**：弱化轮次/摘要噪音，活跃会话 primary 高亮。
6. **流式进度**：`.ds-progress` 弱化文案。

### 契约
- `user_bubble_html` / `assistant_markdown` / `bubble_html`（兼容）/ `render_message_list` / `render_streaming_cursor`。
- 流式节流 `_STREAM_PAINT_INTERVAL` 与事件协议不变。

### 错误行为
- 空回复仍显示「抱歉，出错了。」
- 流式 error 仍 `st.error` + 入窗。

## [S3] Out of Scope
- 不新增主题色、不改 neon/night/light 色值语义。
- 不做 DeepSeek 顶栏模型选择器、文件上传、联网开关。
- 不改 scheduler / agent / 工具链路。
- 不迁移到非 Streamlit 框架。

## Tasks
- [x] T1: message_list DeepSeek 消息形态 — acceptance: 单测覆盖 user/assistant 形态与转义 (covers: S2)
- [x] T2: theme 注入聊天 CSS — acceptance: `.ds-*` 类进入 `get_theme_css`；UI 目录无裸 HEX (covers: S2)
- [x] T3: chat_panel 空态欢迎 + 输入区布局 — acceptance: 欢迎与建议卡；防重逻辑仍在 (covers: S2)
- [x] T4: session_list 弱化装饰 — acceptance: 可切换/新建/删除；无裸 HEX (covers: S2)
- [x] T5: 回归测试与冒烟 — acceptance: 相关 pytest + UI HTTP 200 (covers: S2)
