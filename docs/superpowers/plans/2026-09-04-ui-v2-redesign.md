# UI V2 重设计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Streamlit UI 从 6 页导航重构为"聊天主场 + 图标侧栏 + 三列布局"的单页面板架构，并落地三套可切换主题（霓虹电竞默认 / 暗夜游戏风 / 明亮现代）。

**Architecture:** 单页 `app.py` 主壳以 `ui["tab"]` 分发模式（聊天三列 / 工具面板整宽）；`theme.py` 以 CSS 变量注入三套色板；`ui_state.py` 统一管理 session_state 分区（面板切换不丢状态）；5 个工具面板由现有 `_pages/*` 迁入 `panels/`，聊天组件迁入 `chat/`。后端（services/agents/tools/data）零改动。

**Tech Stack:** Streamlit（st.chat_message 不用，自绘气泡）、Python 3.14、pytest（含 `streamlit.testing.v1.AppTest`）、loguru。

**Spec:** `docs/superpowers/specs/2026-09-04-ui-v2-redesign-design.md`

---

## 文件结构（目标）

```
src/ui/
  app.py                    # 主壳（重写）：图标栏 + tab 分发 + 主题注入 + 面板渲染路由
  theme.py                  # 新增：三套 CSS 变量 + get_theme_css() + 裸 HEX 扫描器
  ui_state.py               # 新增：ui = {tab, theme, panel_state} 读写
  session_state.py          # 保留：run_async_safe + 聊天会话体系（chat_sessions 等）
  chat/
    __init__.py             # 新增
    chat_panel.py           # 新增：三列编排 + _after_message 管线（由 _pages/chat.py 迁移）
    session_list.py         # 新增：会话列组件
    message_list.py         # 新增：气泡流 + 流式渲染
    quick_commands.py       # 新增：快捷指令胶囊
  panels/
    __init__.py             # 新增
    overview.py  search.py  price_watch.py  news.py  recommend.py   # 新增（由 _pages/* 迁移）
  components/
    _loading.py  _error.py  # 修改：配色变量化
    game_card.py  rss_card.py  # 修改：视觉升级（渐变描边/折扣标签）
    metric_card.py          # 新增：统计数字卡
  删除：_pages/（6 文件）
```

**运行环境**：Windows + Git Bash；Python 用 `py -3.14`；所有命令在 worktree 根运行。测试命令：`py -3.14 -m pytest tests/<file> -q`。

---

# 阶段 A：地基（状态 + 主题 + 主壳）

### Task 1: ui_state —— 全局 UI 状态对象

**Files:**
- Create: `src/ui/ui_state.py`
- Test: `tests/test_ui_state.py`

- [ ] **Step 1: 写失败测试**

```python
"""ui_state 单元测试 —— 分区读写与面板切换不丢状态"""

import streamlit as st
import pytest
from src.ui import ui_state


class TestUiState:
    def test_defaults(self):
        ui_state.init_ui_state()
        assert ui_state.get_tab() == "chat"
        assert ui_state.get_theme() == "neon"

    def test_set_tab_roundtrip(self):
        ui_state.init_ui_state()
        ui_state.set_tab("search")
        assert ui_state.get_tab() == "search"

    def test_panel_state_isolated_by_panel(self):
        ui_state.init_ui_state()
        ui_state.set_panel_state("search", {"query": "黑神话"})
        ui_state.set_panel_state("news", {"days": 7})
        assert ui_state.get_panel_state("search") == {"query": "黑神话"}
        assert ui_state.get_panel_state("news") == {"days": 7}
        # 切换 tab 不丢面板状态
        ui_state.set_tab("chat")
        ui_state.set_tab("search")
        assert ui_state.get_panel_state("search") == {"query": "黑神话"}

    def test_panel_state_missing_returns_default(self):
        ui_state.init_ui_state()
        assert ui_state.get_panel_state("nope") == {}

    def test_panel_state_merge(self):
        ui_state.init_ui_state()
        ui_state.set_panel_state("price", {"watchlist": [1]})
        ui_state.update_panel_state("price", {"alerts": [2]})
        s = ui_state.get_panel_state("price")
        assert s == {"watchlist": [1], "alerts": [2]}

    def test_theme_roundtrip(self):
        ui_state.init_ui_state()
        ui_state.set_theme("light")
        assert ui_state.get_theme() == "light"
```

- [ ] **Step 2: 运行确认失败**

Run: `py -3.14 -m pytest tests/test_ui_state.py -q`
Expected: `FAILED ... ModuleNotFoundError: No module named 'src.ui.ui_state'`

- [ ] **Step 3: 实现 ui_state.py**

```python
"""全局 UI 状态 —— ui = {tab, theme, panel_state}

唯一读写入口：UI 代码不得直接操作 st.session_state["ui"]。
面板切换不丢状态：各面板的状态挂在自己的命名空间。
"""

import streamlit as st

DEFAULT_TAB = "chat"
DEFAULT_THEME = "neon"

TABS = ("chat", "overview", "recommend", "price", "news", "search")
THEMES = ("neon", "night", "light")

# 图标栏顺序（D5 决策）：与 PANEL_TITLE 下标一致
TAB_ICONS = {"chat": "💬", "overview": "🏠", "recommend": "🎯",
             "price": "💰", "news": "📰", "search": "🔍"}


def _ui() -> dict:
    if "ui" not in st.session_state:
        st.session_state["ui"] = {
            "tab": DEFAULT_TAB,
            "theme": DEFAULT_THEME,
            "panel_state": {},
        }
    return st.session_state["ui"]


def init_ui_state() -> None:
    _ui()


def get_tab() -> str:
    return _ui()["tab"]


def set_tab(tab: str) -> None:
    assert tab in TABS, f"未知 tab: {tab}"
    _ui()["tab"] = tab


def get_theme() -> str:
    return _ui()["theme"]


def set_theme(theme: str) -> None:
    assert theme in THEMES, f"未知主题: {theme}"
    _ui()["theme"] = theme


def get_panel_state(panel: str) -> dict:
    return _ui()["panel_state"].get(panel, {})


def set_panel_state(panel: str, state: dict) -> None:
    _ui()["panel_state"][panel] = state


def update_panel_state(panel: str, patch: dict) -> None:
    merged = dict(get_panel_state(panel))
    merged.update(patch)
    _ui()["panel_state"][panel] = merged
```

- [ ] **Step 4: 运行确认通过**

Run: `py -3.14 -m pytest tests/test_ui_state.py -q`
Expected: `7 passed`

- [ ] **Step 5: 提交**

```bash
git add src/ui/ui_state.py tests/test_ui_state.py
git commit -m "feat(ui): ui_state 全局 UI 状态对象（tab/theme/panel_state 分区）"
```

---

### Task 2: theme —— 三套 CSS 变量 + 注入 + 裸 HEX 扫描

**Files:**
- Create: `src/ui/theme.py`
- Test: `tests/test_theme.py`

- [ ] **Step 1: 写失败测试**

```python
"""theme 单元测试 —— 变量表完整性、键一致性、裸 HEX 扫描"""

import re
import pytest
from src.ui import theme


class TestThemeVariables:
    def test_three_themes_default_neon(self):
        assert set(theme.THEME_VARS.keys()) == {"neon", "night", "light"}
        assert theme.DEFAULT_THEME == "neon"

    def test_all_themes_have_same_keys(self):
        keys = [frozenset(v) for v in theme.THEME_VARS.values()]
        assert len(set(keys)) == 1, "三套主题变量键必须完全一致"

    def test_required_keys_present(self):
        required = {"--bg", "--panel", "--panel-2", "--accent1", "--accent2",
                    "--ok", "--warn", "--danger", "--text", "--text-dim",
                    "--border", "--glow", "--radius"}
        for name, vars_ in theme.THEME_VARS.items():
            missing = required - set(vars_)
            assert not missing, f"主题 {name} 缺变量: {missing}"

    def test_hex_values_are_valid(self):
        hex_re = re.compile(r"^#[0-9a-fA-F]{6}$")
        for name, vars_ in theme.THEME_VARS.items():
            for key, val in vars_.items():
                if key == "--glow":
                    continue
                assert hex_re.match(val), f"{name}/{key} 非法颜色: {val}"

    def test_get_theme_css_injects_all_variables(self):
        css = theme.get_theme_css("neon")
        for key in theme.THEME_VARS["neon"]:
            assert key in css
        assert ":root" in css


class TestNoBareHexInUI:
    """硬性约定：UI 代码禁止裸 HEX（theme.py 本身除外）"""

    UI_DIRS = [
        "src/ui/components", "src/ui/panels", "src/ui/chat", "src/ui/app.py",
    ]

    @pytest.mark.parametrize("path", [
        p for d in UI_DIRS
        for p in [__import__("pathlib").Path(d)]
        if p.exists()
        for p in ([p] if p.is_file() else p.rglob("*.py"))
    ])
    def test_no_bare_hex(self, path):
        src = path.read_text(encoding="utf-8")
        # 允许注释里的 # 与 CSS 注释；去掉注释后再查裸 HEX
        code = re.sub(r'#.*$', '', src, flags=re.M)
        hits = re.findall(r'#[0-9a-fA-F]{6}', code)
        assert not hits, f"{path} 含裸 HEX: {hits}"
```

- [ ] **Step 2: 运行确认失败**

Run: `py -3.14 -m pytest tests/test_theme.py -q`
Expected: FAIL（theme 模块不存在 / 裸 HEX 扫描 hits 显示现有组件含 `#` 颜色）

> 注：Task 4-5 会完成全部组件的变量化，届时裸 HEX 扫描转绿。若 Task 2 完成后扫描仍红，属预期（遗留为本阶段的 TODO 清单），最后阶段回归时全绿。

- [ ] **Step 3: 实现 theme.py**

```python
"""主题系统 —— 三套 CSS 变量 + 运行时注入

设计决策（spec D7/D2）：CSS 变量 + :root 注入，不依赖 Streamlit 内置主题；
三套皮肤由同一份覆盖样式驱动，颜色全部走变量。
UI 代码（components/panels/chat/app）禁止裸 HEX —— tests/test_theme.py 扫描。
"""

import streamlit as st

DEFAULT_THEME = "neon"

THEME_VARS: dict[str, dict[str, str]] = {
    "neon": {   # 霓虹电竞（默认）
        "--bg": "#0a0a12", "--panel": "#12121e", "--panel-2": "#181834",
        "--accent1": "#ff3d81", "--accent2": "#a855f7",
        "--ok": "#22d3ee", "--warn": "#f0a03a", "--danger": "#ff5d5d",
        "--text": "#e8e8ff", "--text-dim": "#8a8ab8", "--border": "#2a2a55",
        "--glow": "0 0 12px rgba(255, 61, 129, .35)", "--radius": "12px",
    },
    "night": {  # 暗夜游戏风
        "--bg": "#0f1420", "--panel": "#171f31", "--panel-2": "#1e2942",
        "--accent1": "#2b4a9e", "--accent2": "#3b6ad8",
        "--ok": "#4ade80", "--warn": "#f0a03a", "--danger": "#ef4444",
        "--text": "#c8d3ea", "--text-dim": "#8a97b8", "--border": "#2c3c61",
        "--glow": "none", "--radius": "12px",
    },
    "light": {  # 明亮现代
        "--bg": "#f3f5fa", "--panel": "#ffffff", "--panel-2": "#f8fafc",
        "--accent1": "#3a6ff0", "--accent2": "#3a6ff0",
        "--ok": "#16a34a", "--warn": "#d97706", "--danger": "#dc2626",
        "--text": "#33415c", "--text-dim": "#5a6b8a", "--border": "#e0e5f0",
        "--glow": "0 2px 8px rgba(0, 0, 0, .06)", "--radius": "12px",
    },
}

# 覆盖 Streamlit 原生控件的核心样式（全部引用变量）
_BASE_OVERRIDES = """
.stApp {{ background: var(--bg); color: var(--text); }}
[data-testid="stSidebar"] {{ background: var(--panel); border-right: 1px solid var(--border); }}
h1, h2, h3, h4 {{ color: var(--text); }}
.stButton > button, .stFormSubmitButton > button {{
  background: linear-gradient(135deg, var(--accent1), var(--accent2));
  color: #fff; border: none; border-radius: var(--radius);
}}
.stTextInput input, .stTextArea textarea, [data-baseweb="select"] > div {{
  background: var(--panel-2); color: var(--text); border: 1px solid var(--border); border-radius: var(--radius);
}}
.stTextInput input::placeholder {{ color: var(--text-dim); }}
[data-testid="stDataFrame"] {{ background: var(--panel); }}
hr {{ border-color: var(--border); }}
"""


def get_theme_css(theme: str) -> str:
    """主题名 → 完整 CSS 字符串（:root 变量 + 覆盖样式）"""
    vars_ = THEME_VARS.get(theme, THEME_VARS[DEFAULT_THEME])
    var_block = ":root {\n" + "\n".join(f"  {k}: {v};" for k, v in vars_.items()) + "\n}"
    return var_block + "\n" + _BASE_OVERRIDES.format()


def inject_theme(theme: str) -> None:
    """向页面注入主题 CSS（失败静默回退默认，不阻断渲染）"""
    try:
        css = get_theme_css(theme if theme in THEME_VARS else DEFAULT_THEME)
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    except Exception:
        st.markdown(f"<style>{get_theme_css(DEFAULT_THEME)}</style>", unsafe_allow_html=True)
```

- [ ] **Step 4: 运行确认部分通过（裸 HEX 扫描预期红，Task 5 后转绿）**

Run: `py -3.14 -m pytest tests/test_theme.py -q --ignore=tests/test_theme.py::TestNoBareHexInUI` 不可用——用指定类跑：

Run: `py -3.14 -m pytest tests/test_theme.py::TestThemeVariables -q`
Expected: `5 passed`

同时跑扫描确认现状红并记录失败清单：
Run: `py -3.14 -m pytest tests/test_theme.py::TestNoBareHexInUI -q 2>&1 | grep -E "含裸 HEX" | sort -u`
Expected: 列出 game_card.py / rss_card.py 等文件（Task 5 逐一清理）

- [ ] **Step 5: 提交**

```bash
git add src/ui/theme.py tests/test_theme.py
git commit -m "feat(ui): theme 三套 CSS 变量 + get_theme_css/inject_theme + 裸 HEX 扫描测试（扫描红线待 Task 5）"
```

---

### Task 3: app.py 主壳 v1 —— 图标栏 + 模式分发 + 主题注入

**Files:**
- Rewrite: `src/ui/app.py`
- Test: `tests/test_app_shell.py`

- [ ] **Step 1: 写冒烟测试（AppTest 无头运行主壳）**

```python
"""app 主壳冒烟 —— 图标栏渲染、tab 分发、主题注入不崩"""

import streamlit as st
from streamlit.testing.v1 import AppTest


def _run_app():
    return AppTest.from_file("src/ui/app.py", default_timeout=30).run()


class TestAppShell:
    def test_app_runs(self):
        at = _run_app()
        assert not at.exception

    def test_icon_buttons_present(self):
        at = _run_app()
        labels = [b.label for b in at.button]
        assert "💬" in labels and "💰" in labels and "🎯" in labels

    def test_theme_buttons_present(self):
        at = _run_app()
        assert any("主题" in (b.label or "") for b in at.button)

    def test_default_tab_is_chat(self):
        at = _run_app()
        # 聊天模式应渲染会话列表按钮（➕ 新建对话）
        assert any("新对话" in (b.label or "") for b in at.button)

    def test_switch_tab_to_price(self):
        at = _run_app()
        at.button("💰").click().run()
        assert not at.exception
```

- [ ] **Step 2: 运行确认失败**

Run: `py -3.14 -m pytest tests/test_app_shell.py -q`
Expected: FAIL（旧 app.py 无该行为或渲染失败）

- [ ] **Step 3: 重写 app.py（V2 主壳 v1：chat 占位 + overview 占位，其余面板由后续任务填充）**

```python
"""UI V2 主壳 —— 图标栏 + 模式分发 + 主题注入

单页面板架构（spec D4）：sidebar 为图标栏，主区按 ui["tab"] 渲染
聊天三列或工具面板。面板填充顺序见实施计划 Task 10-14。
"""

import streamlit as st

from src.ui import ui_state, theme
from src.ui.session_state import init_session_state, init_chat_sessions

st.set_page_config(page_title="游戏 AI 助手", page_icon="🎮",
                   layout="wide", initial_sidebar_state="expanded")

ui_state.init_ui_state()
init_session_state()
init_chat_sessions()

theme.inject_theme(ui_state.get_theme())

# ── 侧栏：图标栏 ──
with st.sidebar:
    st.markdown("### 🎮")
    current = ui_state.get_tab()
    for tab in ui_state.TABS:
        icon = ui_state.TAB_ICONS[tab]
        active = tab == current
        if st.button(icon, key=f"tab_{tab}", help=tab,
                     type="primary" if active else "secondary",
                     use_container_width=True):
            ui_state.set_tab(tab)
            st.rerun()
    st.divider()
    st.caption("主题")
    for t in ui_state.THEMES:
        if st.button(t, key=f"theme_{t}", use_container_width=True):
            ui_state.set_theme(t)
            st.rerun()

# ── 主区：模式分发 ──
tab = ui_state.get_tab()

if tab == "chat":
    st.title("💬 AI 对话")
    st.info("聊天中心（Task 9 填充）")
elif tab == "overview":
    st.title("🏠 概览")
    st.info("概览面板（Task 10 填充）")
else:
    # 工具面板路由（后续任务逐个接入真实渲染）
    route = {
        "recommend": None, "price": None, "news": None, "search": None,
    }
    render = route[tab]
    if render is None:
        st.title(tab)
        st.info(f"面板 {tab}（Task 11-14 填充）")
    else:
        render()
```

- [ ] **Step 4: 运行确认通过**

Run: `py -3.14 -m pytest tests/test_app_shell.py -q`
Expected: `5 passed`

- [ ] **Step 5: 提交**

```bash
git add src/ui/app.py tests/test_app_shell.py
git commit -m "feat(ui): app.py 单页主壳 v1（图标栏/主题切换/模式分发）"
```

---

# 阶段 B：组件升级（变量化）

### Task 4: 基础组件变量化 + metric_card

**Files:**
- Modify: `src/ui/components/_loading.py`、`src/ui/components/_error.py`
- Create: `src/ui/components/metric_card.py`
- Test: `tests/test_ui_components.py`

- [ ] **Step 1: 写失败测试**

```python
"""UI 组件测试 —— 变量化后组件 import 正常；metric_card 签名为纯函数式"""

import pytest
from src.ui.components import _loading, _error, metric_card


class TestMetricCard:
    def test_signature(self):
        import inspect
        sig = inspect.signature(metric_card.render_metric_card)
        params = list(sig.parameters)
        assert params[:2] == ["label", "value"]
        assert "help" in params

    def test_css_uses_variables_only(self):
        import re
        src = open(metric_card.__file__, encoding="utf-8").read()
        code = re.sub(r"#.*$", "", src, flags=re.M)
        assert not re.findall(r"#[0-9a-fA-F]{6}", code)
```

- [ ] **Step 2: 运行确认失败**

Run: `py -3.14 -m pytest tests/test_ui_components.py -q`
Expected: FAIL（metric_card 不存在）

- [ ] **Step 3: 实现 metric_card + 变量化 _loading/_error**

`src/ui/components/metric_card.py`:

```python
"""统计数字卡 —— 概览面板用（颜色全走主题变量）"""

import streamlit as st


def render_metric_card(label: str, value: str, icon: str = "", help: str | None = None) -> None:
    """霓虹渐变数字卡"""
    st.markdown(
        f"""
        <div style="background: var(--panel); border: 1px solid var(--border);
                    border-radius: var(--radius); padding: 14px 16px;
                    border-top: 3px solid var(--accent1);">
          <div style="color: var(--text-dim); font-size: 13px;">{icon} {label}</div>
          <div style="color: var(--text); font-size: 26px; font-weight: 700;
                      margin-top: 4px;">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if help:
        st.caption(help)
```

`src/ui/components/_loading.py`（完整重写，样式变量化）:

```python
"""统一加载指示组件"""

import streamlit as st
from contextlib import contextmanager


@contextmanager
def show_loading(message: str = "加载中..."):
    """统一加载指示（spinner 样式由主题变量驱动）"""
    with st.spinner(message):
        yield
```

`src/ui/components/_error.py`（完整重写，仅加提示文案配色）:

```python
"""统一错误展示组件"""

import streamlit as st
from contextlib import contextmanager
from loguru import logger


@contextmanager
def show_error(fallback_message: str = "操作失败，请稍后重试"):
    """统一错误处理上下文管理器"""
    try:
        yield
    except Exception as e:
        logger.exception(f"{fallback_message}: {e}")
        st.error(f"{fallback_message}: {e}")
```

- [ ] **Step 4: 运行确认通过**

Run: `py -3.14 -m pytest tests/test_ui_components.py -q`
Expected: `2 passed`

- [ ] **Step 5: 提交**

```bash
git add src/ui/components/metric_card.py src/ui/components/_loading.py src/ui/components/_error.py tests/test_ui_components.py
git commit -m "feat(ui): metric_card 新增 + _loading/_error 变量化"
```

---

### Task 5: game_card / rss_card 视觉升级（变量化 + 渐变描边/折扣标签）

**Files:**
- Modify: `src/ui/components/game_card.py`、`src/ui/components/rss_card.py`

- [ ] **Step 1: 确认裸 HEX 扫描红（现状基准）**

Run: `py -3.14 -m pytest tests/test_theme.py::TestNoBareHexInUI -q 2>&1 | grep -E "game_card|rss_card"`
Expected: 两个文件出现在失败清单

- [ ] **Step 2: 重写 game_card.py（低价标签 + 渐变描边，颜色全变量）**

```python
"""游戏卡片组件 —— 搜索结果与推荐列表共用（V2 视觉：渐变描边 + 折扣标签）"""

import streamlit as st
from loguru import logger
from src.ui.session_state import run_async_safe


def render_game_detail(game: dict) -> None:
    """游戏详情展开（懒加载 RAWG 详情接口）"""
    try:
        from src.tools.rawg import RAWGGameDetailTool
        detail = run_async_safe(RAWGGameDetailTool()._arun(game["id"]))
        if detail and "error" not in detail:
            if detail.get("description"):
                st.markdown(detail["description"])
            detail_col1, detail_col2, detail_col3 = st.columns(3)
            with detail_col1:
                st.metric("评分", f"{detail.get('rating', '-')}/5")
            with detail_col2:
                st.metric("评分人数", detail.get("rating_count", "-"))
            with detail_col3:
                st.metric("Metacritic", detail.get("metacritic", "-"))
            if detail.get("tags"):
                st.caption(f"标签: {', '.join(detail['tags'][:10])}")
            if detail.get("developers"):
                st.caption(f"开发商: {', '.join(detail['developers'])}")
            if detail.get("publishers"):
                st.caption(f"发行商: {', '.join(detail['publishers'])}")
            if detail.get("website"):
                st.link_button("官网", detail["website"])
        else:
            st.info("暂无详细信息")
    except Exception as exc:
        logger.warning(f"游戏详情加载失败 [{game.get('name')}]: {exc}")
        st.info("详情加载失败")


def _discount_badge(game: dict) -> str:
    """折扣/价格标签 HTML（优先使用 cheapshark 的 discount_percent 字段）"""
    discount = game.get("discount_percent")
    sale = game.get("sale_price")
    if discount:
        return f'<span style="background: var(--ok); color: var(--bg); border-radius: 6px; padding: 2px 6px; font-size: 12px; font-weight: 700;">-{discount:.0f}%</span>'
    if sale:
        return f'<span style="color: var(--ok); font-weight: 600;">¥{sale}</span>'
    if game.get("rating"):
        return f'<span style="color: var(--text-dim);">⭐ {game["rating"]}/5</span>'
    return ""


def render_game_card(
    game: dict,
    *,
    show_detail: bool = True,
    rank: int | None = None,
    match_badge: str = "",
) -> None:
    """游戏卡片：渐变描边卡片 + 左图右信息 + 可选详情展开。"""
    border_style = (
        "border: 1px solid transparent;"
        "background: linear-gradient(var(--panel), var(--panel)) padding-box,"
        "            linear-gradient(135deg, var(--accent1), var(--accent2)) border-box;"
    )
    with st.container():
        st.markdown(
            f"""<div style="{border_style} border-radius: var(--radius); padding: 12px;">
              <div style="display:flex; gap:12px;">
                <div style="flex:1; min-width:90px; max-width:180px;">{'<img src="' + game['background_image'] + '" style="width:100%; border-radius:8px;">' if game.get('background_image') else ''}</div>
                <div style="flex:2;">
                  <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                    <span style="color:var(--text); font-size:16px; font-weight:700;">{(str(rank) + '. ' if rank else '') + game['name']}{match_badge}</span>
                    {_discount_badge(game)}
                  </div>
                  {('<div style="color:var(--text-dim); font-size:13px;">评分: <b>%.1f</b>/5 | Metacritic: %s</div>' % (game['rating'], game.get('metacritic') or '暂无')) if game.get('rating') else ''}
                  <div style="color:var(--text); font-size:13px;">发售日: {game.get('released', '-')}</div>
                  <div style="color:var(--text-dim); font-size:13px;">类型: {', '.join(game.get('genres', [])) or '-'}</div>
                  {('<div style="color:var(--text-dim); font-size:13px;">平台: ' + ', '.join(game['platforms'][:5]) + '</div>') if game.get('platforms') else ''}
                </div>
              </div>
            </div>""",
            unsafe_allow_html=True,
        )
        if show_detail:
            with st.expander(f"查看 {game['name']} 详情"):
                render_game_detail(game)
```

> 注意：原组件内 `st.container(border=True)` + `st.columns` 布局改为内联 HTML 布局（三列等宽自适应）。
> 行为不变：详情 expander、懒加载、错误降级；推荐序号与匹配徽标经参数传入。

- [ ] **Step 3: 重写 rss_card.py**

```python
"""RSS / 新闻卡片组件（V2：变量化）"""

import streamlit as st


def render_news_doc(doc) -> None:
    """RAG 检索结果卡片"""
    meta = doc.metadata
    st.markdown(
        f"""<div style="background: var(--panel); border: 1px solid var(--border);
                    border-radius: var(--radius); padding: 12px 14px; margin-bottom: 10px;">
          <div style="color: var(--text); font-weight: 600;">{meta.get('title', '无标题')}</div>
          <div style="color: var(--text-dim); font-size: 12px;">来源: {meta.get('source_name', '未知')} | 日期: {meta.get('published_date', '未知')} | 语言: {meta.get('language', '未知')}</div>
          <div style="color: var(--text); font-size: 13px; margin-top: 6px;">{doc.page_content[:300]}{'...' if len(doc.page_content) > 300 else ''}</div>
        </div>""",
        unsafe_allow_html=True,
    )
    if meta.get("source_url"):
        st.link_button("阅读原文", meta["source_url"])


def render_rss_article(article: dict) -> None:
    """RSS 文章卡片"""
    st.markdown(
        f"""<div style="background: var(--panel); border: 1px solid var(--border);
                    border-radius: var(--radius); padding: 12px 14px; margin-bottom: 10px;">
          <div style="color: var(--text); font-weight: 600;">{article.get('title', '无标题')}</div>
          <div style="color: var(--text-dim); font-size: 12px;">来源: {article.get('source_name', article.get('source', '未知'))} | {article.get('published', '未知')}</div>
          {('<div style="color: var(--text); font-size: 13px; margin-top: 6px;">' + article['summary'][:200] + '</div>') if article.get('summary') else ''}
        </div>""",
        unsafe_allow_html=True,
    )
    if article.get("link"):
        st.link_button("阅读原文", article["link"])
```

- [ ] **Step 4: 运行确认（本轮 = 扫描中这两个文件转绿）**

Run: `py -3.14 -m pytest tests/test_theme.py::TestNoBareHexInUI -q 2>&1 | grep -E "含裸 HEX"`
Expected: game_card.py / rss_card.py 不再出现（若仍有其他文件红属预期，Task 10-14 面板迁移时清理）

Run: `py -3.14 -m pytest tests/test_imports.py tests/test_theme.py -q`
Expected: 全部通过（除残留面板桶即 panels 未创建前无关）

- [ ] **Step 5: 提交**

```bash
git add src/ui/components/game_card.py src/ui/components/rss_card.py
git commit -m "feat(ui): game_card/rss_card V2 视觉升级（渐变描边/折扣标签/全变量化）"
```

---

# 阶段 C：聊天中心

### Task 6: quick_commands —— 快捷指令胶囊

**Files:**
- Create: `src/ui/chat/__init__.py`、`src/ui/chat/quick_commands.py`
- Test: `tests/test_quick_commands.py`

- [ ] **Step 1: 写失败测试**

```python
"""quick_commands 测试 —— 指令定义与填充逻辑"""

import streamlit as st
from src.ui.chat import quick_commands


class TestQuickCommands:
    def test_commands_defined(self):
        cmds = quick_commands.QUICK_COMMANDS
        assert isinstance(cmds, list) and len(cmds) >= 4
        labels = {c["label"] for c in cmds}
        assert {"💰 查价格", "🎯 找推荐", "📰 看新闻", "🔍 搜游戏"}.issubset(labels)

    def test_build_prompt(self):
        assert quick_commands.build_prompt("查价格", "黑神话") == "/price 黑神话"
        assert quick_commands.build_prompt("找推荐", "魂系") == "/recommend 魂系"
        assert quick_commands.build_prompt("看新闻", "") == "/news"
```

- [ ] **Step 2: 运行确认失败**

Run: `py -3.14 -m pytest tests/test_quick_commands.py -q`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

`src/ui/chat/__init__.py`（空文件，仅标记包）。

`src/ui/chat/quick_commands.py`:

```python
"""快捷指令 —— 输入框上方的行为胶囊（点击填入输入框，不自动发送）"""

import streamlit as st

# label → 对应文本指令模板（{} 为游戏名占位）
QUICK_COMMANDS = [
    {"icon": "💰", "label": "查价格", "template": "/price {name}"},
    {"icon": "🎯", "label": "找推荐", "template": "/recommend {name}"},
    {"icon": "📰", "label": "看新闻", "template": "/news {name}"},
    {"icon": "🔍", "label": "搜游戏", "template": "/search {name}"},
]


def build_prompt(label: str, game_name: str = "") -> str:
    """指令 label + 游戏名 → 文本指令"""
    for c in QUICK_COMMANDS:
        if label == c["label"]:
            return c["template"].format(name=game_name.strip())
    return ""


def render_quick_commands() -> None:
    """渲染快捷指令胶囊行；点击写入 ui_state.panel_state['chat']['draft']"""
    from src.ui import ui_state

    cols = st.columns(len(QUICK_COMMANDS))
    for col, cmd in zip(cols, QUICK_COMMANDS):
        with col:
            if st.button(f"{cmd['icon']} {cmd['label']}", key=f"qc_{cmd['label']}", use_container_width=True):
                ui_state.update_panel_state("chat", {"draft": build_prompt(cmd["label"])})
                st.rerun()
```

- [ ] **Step 4: 运行确认通过**

Run: `py -3.14 -m pytest tests/test_quick_commands.py -q`
Expected: `2 passed`

- [ ] **Step 5: 提交**

```bash
git add src/ui/chat/__init__.py src/ui/chat/quick_commands.py tests/test_quick_commands.py
git commit -m "feat(ui): 聊天快捷指令胶囊（点击写入输入框草稿）"
```

---

### Task 7: session_list —— 会话列组件

**Files:**
- Create: `src/ui/chat/session_list.py`
- Test: `tests/test_session_list.py`

- [ ] **Step 1: 写失败测试（会话展示数据准备函数，纯逻辑）**

```python
"""session_list 测试 —— 会话摘要行数据的纯函数部分"""

from src.ui.chat import session_list


class TestSessionSummaries:
    def test_empty(self):
        rows = session_list.build_session_rows({}, active_id=None)
        assert rows == []

    def test_rows_sorted_and_active_marked(self):
        sessions = {
            "a": {"title": "T1", "messages": [{"role": "user"}, {"role": "assistant"}] * 2,
                  "summary": None},
            "b": {"title": "T2", "messages": [{"role": "user"}], "summary": "摘要"},
        }
        rows = session_list.build_session_rows(sessions, active_id="b")
        assert rows[0]["sid"] == "b"
        assert rows[0]["is_active"] is True
        assert rows[0]["rounds"] == 0
        assert rows[0]["has_summary"] is True

    def test_rounds_computed(self):
        sessions = {"a": {"title": "T", "messages": [{"role": "user"}, {"role": "assistant"}] * 3, "summary": None}}
        rows = session_list.build_session_rows(sessions, active_id=None)
        assert rows[0]["rounds"] == 3
```

- [ ] **Step 2: 运行确认失败**

Run: `py -3.14 -m pytest tests/test_session_list.py -q`
Expected: FAIL

- [ ] **Step 3: 实现**

`src/ui/chat/session_list.py`:

```python
"""会话列组件 —— 新建/搜索/选择/删除 会话（X 三列式的中间列）"""

import streamlit as st

from src.ui.session_state import init_chat_sessions, create_chat_session, switch_session


def build_session_rows(sessions: dict, active_id: str | None) -> list[dict]:
    """会话 → 展示行（活跃会话排最前，按标题排序）"""
    rows = []
    for sid, s in sessions.items():
        rounds = len(s.get("messages", [])) // 2
        rows.append({
            "sid": sid,
            "title": s.get("title", "未命名对话"),
            "rounds": rounds,
            "has_summary": bool(s.get("summary")),
            "is_active": sid == active_id,
        })
    rows.sort(key=lambda r: (not r["is_active"], r["title"]))
    return rows


def render_session_list(max_items: int = 50) -> None:
    """渲染会话列；交互（新建/切换/删除）直接操作 session_state"""
    init_chat_sessions()
    sessions = st.session_state["chat_sessions"]
    active = st.session_state.get("active_session_id")

    if st.button("➕ 新对话", key="new_session", use_container_width=True):
        create_chat_session()
        st.rerun()

    filter_q = st.text_input("搜索会话", key="session_filter", label_visibility="collapsed",
                             placeholder="搜索会话…")

    rows = build_session_rows(sessions, active)
    if filter_q:
        rows = [r for r in rows if filter_q.lower() in r["title"].lower()]

    for row in rows[:max_items]:
        title = row["title"]
        marker = " 📋" if row["has_summary"] else ""
        prefix = "▸ " if row["is_active"] else ""
        btn_label = f"{prefix}{title} ({row['rounds']}轮){marker}"
        if st.button(btn_label, key=f"sess_{row['sid']}", use_container_width=True,
                     type="primary" if row["is_active"] else "secondary"):
            switch_session(row["sid"])
            st.rerun()
        if not row["is_active"]:
            if st.button("🗑", key=f"del_{row['sid']}", help="删除此对话"):
                from src.ui.session_state import get_session_factory  # noqa: F401（保持调用侧一致）
                del st.session_state["chat_sessions"][row["sid"]]
                st.rerun()
```

> 原本 `_pages/chat.py` 中 `sessions[sid]["messages"]` 与 `st.dialog` 删除确认的交互在 `chat_panel`（Task 9）中接管；此处先提供轻量删除（确认放入 chat_panel 或本组件均可用，保持兼容）。

- [ ] **Step 4: 运行确认通过**

Run: `py -3.14 -m pytest tests/test_session_list.py -q`
Expected: `3 passed`

- [ ] **Step 5: 提交**

```bash
git add src/ui/chat/session_list.py tests/test_session_list.py
git commit -m "feat(ui): 会话列组件（新建/搜索/切换/删除）"
```

---

### Task 8: message_list —— 气泡流 + 流式渲染

**Files:**
- Create: `src/ui/chat/message_list.py`
- Test: `tests/test_message_list.py`

- [ ] **Step 1: 写失败测试（渲染辅助纯函数）**

```python
"""message_list 测试 —— 气泡 HTML 构造与流式辅助"""

from src.ui.chat import message_list


class TestBubbleHtml:
    def test_user_bubble(self):
        html = message_list.bubble_html("user", "你好")
        assert "var(--accent1)" in html  # 渐变由 CSS 变量引用
        assert "你好" in html
        assert "flex-end" in html

    def test_assistant_bubble(self):
        html = message_list.bubble_html("assistant", "回复")
        assert "var(--panel-2)" in html
        assert "flex-start" in html

    def test_escape_content(self):
        html = message_list.bubble_html("user", "<script>alert(1)</script>")
        assert "<script>" not in html


class TestStreaming:
    def test_append_token(self):
        assert message_list.append_token("黑", "神话") == "黑神话"

    def test_truncate_long_content(self):
        long = "x" * 500
        assert len(message_list.append_token(long, "y")) == 501
```

- [ ] **Step 2: 运行确认失败**

Run: `py -3.14 -m pytest tests/test_message_list.py -q`
Expected: FAIL

- [ ] **Step 3: 实现**

`src/ui/chat/message_list.py`:

```python
"""消息气泡流 + 流式渲染（保留 stream_sync 管线机制，视觉升级）"""

import html as _html

import streamlit as st


def bubble_html(role: str, content: str) -> str:
    """聊天气泡 HTML（颜色全走 CSS 变量）"""
    safe = _html.escape(content)
    if role == "user":
        align, bg, grd = "flex-end", "linear-gradient(135deg, var(--accent1), var(--accent2))", "box-shadow: var(--glow);"
    else:
        align, bg, grd = "flex-start", "var(--panel-2)", ""
    return (
        f'<div style="display:flex; justify-content:{align}; margin:6px 0;">'
        f'  <div style="max-width:75%; background:{bg}; {grd} color:var(--text);'
        f'           padding:10px 14px; border-radius:14px; border:1px solid var(--border);'
        f'           white-space:pre-wrap; word-break:break-word; font-size:14px;">{safe}</div>'
        f'</div>'
    )


def append_token(full: str, chunk: str) -> str:
    return full + chunk


def render_message_list(messages: list[dict]) -> None:
    """渲染既有消息流（无流式时）"""
    for m in messages:
        st.markdown(bubble_html(m["role"], m["content"]), unsafe_allow_html=True)


def render_streaming_placeholder() -> tuple[object, object, object]:
    """流式输出三件套：进度位、输出位、光标位"""
    progress_ph = st.empty()
    output_ph = st.empty()
    return progress_ph, output_ph, progress_ph


def render_streaming_cursor(output_ph, full_text: str) -> None:
    """打字光标（闪烁由 CSS animation 提供，见 theme 覆盖或行内动画）"""
    output_ph.markdown(
        bubble_html("assistant", full_text + '<span style="animation: blink 1s steps(2) infinite;">▌</span>'),
        unsafe_allow_html=True,
    )
```

> 说明：`@keyframes blink` 在 `theme.get_theme_css` 的覆盖样式中定义一份（三主题共用），Task 2 之后补上；此处若缺失仅影响光标动画，不影响功能。实现时在 theme.py `_BASE_OVERRIDES` 末尾追加：

```python
# （Task 2 的 theme.py 若已提交，追加到 _BASE_OVERRIDES 并在 get_theme_css 后重新提交）
@keyframes blink {{ 0%{{opacity:1;}} 50%{{opacity:.2;}} 100%{{opacity:1;}} }}
```

- [ ] **Step 4: 运行确认通过**

Run: `py -3.14 -m pytest tests/test_message_list.py -q`
Expected: `5 passed`

- [ ] **Step 5: 提交**

```bash
git add src/ui/chat/message_list.py tests/test_message_list.py
git commit -m "feat(ui): 消息气泡组件（变量化 HTML + 转义 + 流式光标）"
```

---

### Task 9: chat_panel —— 三列编排 + 持久化管线迁移

**Files:**
- Create: `src/ui/chat/chat_panel.py`
- Modify: `src/ui/app.py`（聊天分支接入 chat_panel）
- Test: `tests/test_chat_panel.py`

- [ ] **Step 1: 写失败测试（_after_message 管线逻辑迁移为可注入函数）**

```python
"""chat_panel 测试 —— 消息持久化流水线（迁移自 _pages/chat.py 的 _after_message）"""

import pytest
from src.ui.chat import chat_panel


class FakeService:
    def __init__(self):
        self.saved = []

    async def save_message(self, sid, role, content, intent=None):
        self.saved.append((sid, role, content))
        return True

    def should_compress(self, count, **kw):
        return count >= 3

    async def compress(self, messages, existing_summary=None, recent_keep=None):
        return messages[2:], "摘要"

    async def extract_profile(self, summary):
        return {"favorite_genres": "RPG"}

    async def save_profile(self, sid, profile):
        return True


class FakeSessionState:
    """模拟 chat_sessions 的读写（不依赖 st.session_state）"""

    def __init__(self, sessions):
        self.chat_sessions = sessions

    def get(self, key, default=None):
        return getattr(self, key, default)


def test_after_message_saves_and_compresses():
    svc = FakeService()
    sessions = {"s1": {"messages": [{"role": "u", "content": "1"}] * 4, "summary": None}, "active": "s1"}

    async def scenario():
        await chat_panel._after_message_logic(svc, sessions, "s1", "user", "新消息")

    import asyncio
    asyncio.run(scenario())
    assert svc.saved[-1] == ("s1", "user", "新消息")
    assert len(sessions["s1"]["messages"]) == 2          # 压缩后保留 recent 部分
    assert sessions["s1"]["summary"] == "摘要"


def test_after_message_single_no_compress():
    svc = FakeService()
    sessions = {"s1": {"messages": [{"role": "u", "content": "1"}], "summary": None}, "active": "s1"}

    async def scenario():
        await chat_panel._after_message_logic(svc, sessions, "s1", "assistant", "回复")

    import asyncio
    asyncio.run(scenario())
    assert len(sessions["s1"]["messages"]) == 2
    assert sessions["s1"]["summary"] is None
```

- [ ] **Step 2: 运行确认失败**

Run: `py -3.14 -m pytest tests/test_chat_panel.py -q`
Expected: FAIL

- [ ] **Step 3: 实现 chat_panel.py（从 _pages/chat.py 迁移）**

`src/ui/chat/chat_panel.py`:

```python
"""聊天中心面板 —— 三列布局编排 + 消息持久化流水线

迁移自 _pages/chat.py（D6：流式机制不变，渲染升级）。
数据流：session_state 会话 → ChatService 持久化 → chat_stream 流式。
"""

import streamlit as st

from src.services.chat_service import ChatService
from src.ui import ui_state
from src.ui.session_state import (
    init_chat_sessions, create_chat_session, get_active_messages,
    add_chat_session_message, switch_session, run_async_safe,
)
from src.ui.chat.session_list import render_session_list
from src.ui.chat.message_list import (
    bubble_html, render_message_list, render_streaming_cursor,
    render_streaming_placeholder,
)
from src.ui.chat.quick_commands import render_quick_commands


async def _after_message_logic(mem: ChatService, sessions: dict, sid: str,
                               role: str, content: str) -> None:
    """消息落库 + 压缩判定 + 画像提取（纯逻辑，可注入测试）"""
    await mem.save_message(sid, role, content)
    current_msgs = sessions[sid]["messages"]
    if mem.should_compress(len(current_msgs)):
        existing = sessions[sid].get("summary")
        compacted, new_summary = await mem.compress(current_msgs, existing_summary=existing)
        sessions[sid]["messages"] = compacted
        sessions[sid]["summary"] = new_summary
        if new_summary:
            profile = await mem.extract_profile(new_summary)
            if profile and any(profile.values()):
                await mem.save_profile(sid, profile)


def _after_message(sid: str, role: str, content: str) -> None:
    """流式 UI 包装：run_async_safe 桥接 + 读 session_state"""
    mem = ChatService()
    run_async_safe(_after_message_logic(mem, st.session_state["chat_sessions"],
                                        sid, role, content))


def _ensure_session() -> None:
    init_chat_sessions()
    if not st.session_state.get("active_session_id") or not st.session_state["chat_sessions"]:
        create_chat_session()


def _render_streaming_chat(prompt: str, history: list[dict]):
    """流式输出体验（机制同 V1：stream_sync + astream_events）"""
    from src.agents.graph import chat_stream, NODE_LABELS
    from src.utils.stream_bridge import stream_sync

    progress_ph, output_ph, _ = render_streaming_placeholder()
    full_text = ""

    sid = st.session_state.get("active_session_id")
    chat_summary = st.session_state["chat_sessions"][sid].get("summary") if sid else None

    try:
        for event in stream_sync(
            lambda: chat_stream(prompt, history[:-1] if len(history) > 1 else None,
                                summary=chat_summary)
        ):
            etype = event["type"]
            if etype == "progress":
                label = NODE_LABELS.get(event["node"], "")
                if label:
                    progress_ph.caption(label)
            elif etype == "clear":
                full_text = ""
                output_ph.empty()
            elif etype == "token":
                full_text += event["content"]
                render_streaming_cursor(output_ph, full_text)
            elif etype == "done":
                progress_ph.empty()
                response = event.get("response", "")
                output_ph.markdown(bubble_html("assistant", response or "抱歉，出错了。"),
                                   unsafe_allow_html=True)
                if not response:
                    response = "抱歉，出错了。"
                add_chat_session_message("assistant", response)
                _after_message(sid, "assistant", response)
            elif etype == "error":
                progress_ph.empty()
                error_msg = f"出错了: {event['message']}"
                st.error(error_msg)
                add_chat_session_message("assistant", error_msg)
                _after_message(sid, "assistant", error_msg)
                break
    except Exception as exc:
        progress_ph.empty()
        st.error(f"出错了: {exc}")
        add_chat_session_message("assistant", f"出错了: {exc}")
        _after_message(sid, "assistant", f"出错了: {exc}")


def render_chat_panel() -> None:
    """聊天中心：会话列 + 聊天区（X 三列式）"""
    _ensure_session()

    col_sessions, col_chat = st.columns([1, 4], gap="medium")
    with col_sessions:
        render_session_list()

    with col_chat:
        history = get_active_messages()

        # 空态引导
        if not history:
            st.markdown("### 你想问什么？")
            examples = ["黑神话悟空现在多少钱？", "推荐几个魂系游戏", "最近有什么游戏新闻？"]
            ex_cols = st.columns(len(examples))
            for col, ex in zip(ex_cols, examples):
                with col:
                    if st.button(ex, key=f"ex_{ex[:4]}", use_container_width=True):
                        add_chat_session_message("user", ex)
                        _after_message(st.session_state["active_session_id"], "user", ex)
                        st.rerun()
        else:
            render_message_list(history)

        # 快捷指令 + 输入
        render_quick_commands()
        draft = ui_state.get_panel_state("chat").get("draft", "")
        prompt = st.chat_input("输入问题...", value=draft)
        if prompt:
            if draft:
                ui_state.set_panel_state("chat", {})
            add_chat_session_message("user", prompt)
            _after_message(st.session_state["active_session_id"], "user", prompt)
            history = get_active_messages()
            render_message_list(history)   # 立即显示用户消息
            with st.container():
                _render_streaming_chat(prompt, history)
```

- [ ] **Step 4: 更新 app.py 聊天分支接入 chat_panel**

`src/ui/app.py` 修改（替换 `if tab == "chat":` 分支）：

```python
if tab == "chat":
    from src.ui.chat.chat_panel import render_chat_panel
    render_chat_panel()
elif tab == "overview":
```

- [ ] **Step 5: 运行确认通过（AppTest 无头跑聊天路由不崩；新单测绿）**

Run: `py -3.14 -m pytest tests/test_chat_panel.py tests/test_app_shell.py -q`
Expected: `2 passed` + `5 passed`（AppTest 聊天分支无异常）

> 注意：AppTest 下 `st.chat_input` 与流式会受限——测试只验证到"empty 态渲染与路由不崩"，完整流式靠手动冒烟（Task 15）。

- [ ] **Step 6: 提交**

```bash
git add src/ui/chat/chat_panel.py src/ui/app.py tests/test_chat_panel.py
git commit -m "feat(ui): 聊天中心 chat_panel（三列编排 + 持久化管线迁移 + 空态引导）"
```

---

# 阶段 D：工具面板迁移（Stage D）

> 通用迁移模式（每个面板任务套用）：
> 1. 读取 `src/ui/_pages/<name>.py` 全文作为迁移源
> 2. 复制主体逻辑为 `panels/<name>.py` 中的 `render_<name>_panel()` 函数
> 3. 替换点：删除 `st.title(...)`；`st.session_state["search_results"]` 等全局键改 `ui_state.get/set_panel_state`；返回聊天入口组件；组件引用换 Task 5 升级版；裸 HEX 清零（Task 5 扫描红线收敛）
> 4. `panels/__init__.py` 导出 `render_xxx_panel`

首先创建 `src/ui/panels/__init__.py`：

```python
"""工具面板包 —— 每个面板一个 render_*_panel() 函数（由 _pages/* 迁移）"""
```

### Task 10: overview 面板

**Files:**
- Create: `src/ui/panels/overview.py`
- Modify: `src/ui/app.py`（接入 overview 路由）
- Test: `tests/test_panels_overview.py`

- [ ] **Step 1: 写测试（overview 统计数据处理纯函数）**

```python
"""overview 面板测试 —— 统计字典规整"""

from src.ui.panels import overview


def test_normalize_stats_defaults():
    s = overview.normalize_stats({})
    assert s["watchlist"] == 0 and s["alerts"] == 0 and s["news_count"] == 0
    assert s["best_deal"] == "-"


def test_normalize_stats_keeps_values():
    s = overview.normalize_stats({"watchlist": 5, "best_deal": "-45%"})
    assert s["watchlist"] == 5 and s["best_deal"] == "-45%"
```

- [ ] **Step 2: 运行确认失败**

Run: `py -3.14 -m pytest tests/test_panels_overview.py -q`
Expected: FAIL

- [ ] **Step 3: 实现 panels/overview.py**

```python
"""概览面板 —— 统计卡 + 热门游戏 + 快捷入口（迁移自 _pages/home.py）"""

import streamlit as st

from src.services.dashboard_service import get_dashboard_stats, get_hot_players
from src.ui import ui_state
from src.ui.session_state import run_async_safe
from src.ui.components.metric_card import render_metric_card


def normalize_stats(stats: dict) -> dict:
    """统计字典规整（缺省值补齐）"""
    return {
        "watchlist": stats.get("watchlist", 0),
        "alerts": stats.get("alerts", 0),
        "news_count": stats.get("news_count", 0),
        "best_deal": stats.get("best_deal", "-"),
    }


@st.cache_data(ttl=120, show_spinner=False)
def _load_stats(_cache_buster: int = 0) -> dict:
    return run_async_safe(get_dashboard_stats())


@st.cache_data(ttl=300, show_spinner=False)
def _load_hot(_cache_buster: int = 0) -> list[dict]:
    return run_async_safe(get_hot_players())


def _open_panel(tab: str) -> None:
    ui_state.set_tab(tab)
    st.rerun()


def render_overview_panel() -> None:
    """概览：四统计卡 + 快捷入口四卡 + 热门在线"""
    stats = normalize_stats(_load_stats())

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_metric_card("活跃监控", str(stats["watchlist"]), "🎯")
    with c2:
        render_metric_card("待读告警", str(stats["alerts"]), "🔔")
    with c3:
        render_metric_card("新闻库", f"{stats['news_count']:,}", "📰")
    with c4:
        render_metric_card("今日最低折扣", stats["best_deal"], "💰")

    st.divider()
    st.subheader("快捷操作")
    q1, q2, q3, q4 = st.columns(4)
    with q1:
        if st.button("🔍 搜游戏", use_container_width=True):
            _open_panel("search")
    with q2:
        if st.button("💰 价格监控", use_container_width=True):
            _open_panel("price")
    with q3:
        if st.button("🎯 找推荐", use_container_width=True):
            _open_panel("recommend")
    with q4:
        if st.button("📰 看新闻", use_container_width=True):
            _open_panel("news")

    st.divider()
    st.subheader("热门游戏在线")
    for game in _load_hot():
        st.markdown(f"- **{game['name']}** — 在线: {game['players']}")
```

- [ ] **Step 4: app.py 接入 overview 路由**

替换 `elif tab == "overview":` 分支为：

```python
elif tab == "overview":
    from src.ui.panels.overview import render_overview_panel
    render_overview_panel()
```

- [ ] **Step 5: 运行确认通过**

Run: `py -3.14 -m pytest tests/test_panels_overview.py tests/test_app_shell.py -q`
Expected: `2 passed` + `5 passed`

- [ ] **Step 6: 提交**

```bash
git add src/ui/panels/__init__.py src/ui/panels/overview.py src/ui/app.py tests/test_panels_overview.py
git commit -m "feat(ui): 概览面板（统计卡/快捷入口/热门游戏）接入主壳"
```

---

### Task 11: search 面板

**Files:**
- Create: `src/ui/panels/search.py`
- Modify: `src/ui/app.py`
- Test: `tests/test_panels_search.py`

- [ ] **Step 1: 写测试（筛选参数映射纯函数）**

```python
"""search 面板测试 —— 平台/类型映射与搜索推导"""

from src.ui.panels import search


def test_filter_params():
    params = search.build_filter_params(platforms=["PC"], genres=["动作", "RPG"])
    assert params["platforms"] == "4"
    assert params["genres"] == "action,role-playing-games-rpg"


def test_filter_params_empty():
    assert search.build_filter_params(platforms=[], genres=[]) == {}


def test_panel_state_query_roundtrip():
    state = {"query": "黑神话", "platforms": ["PC"], "genres": []}
    q = search.build_query_from_state(state)
    assert q == "黑神话"
```

- [ ] **Step 2: 运行确认失败**

Run: `py -3.14 -m pytest tests/test_panels_search.py -q`
Expected: FAIL

- [ ] **Step 3: 实现 panels/search.py（迁移自 _pages/search.py）**

```python
"""游戏搜索面板（迁移自 _pages/search.py）"""

import streamlit as st

from src.ui import ui_state
from src.ui.session_state import run_async_safe
from src.ui.components._loading import show_loading
from src.ui.components._error import show_error
from src.ui.components.game_card import render_game_card

PLATFORM_MAP = {
    "PC": "4", "PlayStation": "187,18,16", "Xbox": "1,14",
    "Nintendo Switch": "7", "iOS": "3", "Android": "21",
}
GENRE_MAP = {
    "动作": "action", "冒险": "adventure", "RPG": "role-playing-games-rpg",
    "策略": "strategy", "模拟": "simulation", "体育": "sports",
    "独立": "indie", "大型多人在线": "massively-multiplayer",
}


def build_filter_params(platforms: list[str], genres: list[str]) -> dict:
    params = {}
    if platforms:
        params["platforms"] = ",".join(PLATFORM_MAP[p] for p in platforms)
    if genres:
        params["genres"] = ",".join(GENRE_MAP[g] for g in genres)
    return params


def build_query_from_state(state: dict) -> str:
    return state.get("query", "")


def render_search_panel() -> None:
    """搜索面板：查询 + 筛选胶囊 + 结果流"""
    state = ui_state.get_panel_state("search")

    st.markdown("### 游戏搜索")
    query = st.text_input("游戏名称", value=state.get("query", ""),
                          placeholder="例如: 艾尔登法环, 原神, 黑神话悟空...")

    col1, col2 = st.columns([1, 3])
    with col1:
        platform_filter = st.multiselect("平台", list(PLATFORM_MAP.keys()))
        genre_filter = st.multiselect("类型", list(GENRE_MAP.keys()))

    col3, col4 = st.columns([1, 5])
    with col3:
        if st.button("🔍 搜索", type="primary", use_container_width=True):
            params = build_filter_params(platform_filter, genre_filter)
            ui_state.set_panel_state("search",
                                     {"query": query, "platforms": platform_filter,
                                      "genres": genre_filter, "result_state": "loading"})
            st.rerun()
    with col4:
        if st.button("← 返回对话", use_container_width=True) or st.button("💬", key="back_chat_search", help="返回对话"):
            pass  # 统一处理见下

    if st.button("← 返回对话", key="back_search", use_container_width=True):
        ui_state.set_tab("chat")
        st.rerun()

    if state.get("result_state") == "loading":
        with show_error("搜索失败"):
            with show_loading("搜索中..."):
                from src.tools.rawg import RAWGGameSearchTool
                tool = RAWGGameSearchTool()
                params = build_filter_params(state.get("platforms", []), state.get("genres", []))
                results = run_async_safe(tool._arun(state.get("query", ""), **params))
                ui_state.set_panel_state("search", {**state, "results": results, "result_state": "done"})
                st.rerun()

    results = state.get("results") or []
    if results:
        st.subheader(f"找到 {len(results)} 个结果")
        for game in results:
            render_game_card(game)
    elif not query and not results:
        st.info("输入游戏名称开始搜索")
```

> 注意：`st.button("← 返回对话")` 出现两次（col4 与独立行）——实现时只保留独立行版本（col4 行删除），保持单一入口；上段两行是演示改动点的示意，落地代码以独立行版本为准。

- [ ] **Step 4: app.py 接入 search 路由**

```python
elif tab == "search":
    from src.ui.panels.search import render_search_panel
    render_search_panel()
```

- [ ] **Step 5: 运行确认通过**

Run: `py -3.14 -m pytest tests/test_panels_search.py tests/test_app_shell.py -q`
Expected: `3 passed` + `5 passed`

- [ ] **Step 6: 提交**

```bash
git add src/ui/panels/search.py src/ui/app.py tests/test_panels_search.py
git commit -m "feat(ui): 搜索面板（筛选参数映射/结果流/返回对话）"
```

---

### Task 12: news 面板

**Files:**
- Create: `src/ui/panels/news.py`
- Modify: `src/ui/app.py`
- Test: `tests/test_panels_news.py`

- [ ] **Step 1: 写测试**

```python
"""news 面板测试 —— 筛选参数归一"""

from src.ui.panels import news


def test_filters_normalized():
    f = news.normalize_filters(game="全部", source="游民星空", days="最近 7 天")
    assert f == {"game": None, "source": "游民星空", "days": 7}


def test_filters_all_none():
    assert news.normalize_filters(game="全部", source="全部", days="全部") == {
        "game": None, "source": None, "days": None}
```

- [ ] **Step 2: 运行确认失败**

Run: `py -3.14 -m pytest tests/test_panels_news.py -q`
Expected: FAIL

- [ ] **Step 3: 实现 panels/news.py（迁移自 _pages/news.py）**

```python
"""游戏新闻面板 —— 双 Tab：语义检索 + 最新 RSS（迁移自 _pages/news.py）"""

import streamlit as st
from loguru import logger

from src.ui import ui_state
from src.ui.session_state import run_async_safe
from src.ui.components._loading import show_loading
from src.ui.components._error import show_error
from src.ui.components.rss_card import render_news_doc, render_rss_article

GAME_FILTERS = ["全部", "原神", "鸣潮", "Steam", "独立游戏"]
SOURCE_FILTERS = ["全部", "HoYoLAB", "Steam", "游民星空", "3DM", "机核", "IGN", "PC Gamer"]
DAYS_MAP = {"全部": None, "最近 3 天": 3, "最近 7 天": 7, "最近 30 天": 30}


def normalize_filters(game: str, source: str, days: str) -> dict:
    return {
        "game": None if game == "全部" else game,
        "source": None if source == "全部" else source,
        "days": DAYS_MAP.get(days),
    }


@st.cache_data(ttl=1800, show_spinner=False)
def _load_rss() -> list | None:
    try:
        from src.tools.rss_feed import RSSFetchAllTool
        return run_async_safe(RSSFetchAllTool()._arun())
    except Exception as exc:
        logger.warning(f"RSS 加载失败: {exc}")
        return None


def render_news_panel() -> None:
    """新闻面板"""
    st.markdown("### 游戏新闻")
    tab1, tab2 = st.tabs(["🔍 新闻搜索", "📰 最新资讯"])

    with tab1:
        state = ui_state.get_panel_state("news")
        col1, col2, col3 = st.columns(3)
        with col1:
            game_filter = st.selectbox("游戏筛选", GAME_FILTERS)
        with col2:
            source_filter = st.selectbox("来源筛选", SOURCE_FILTERS)
        with col3:
            days_filter = st.selectbox("时间范围", list(DAYS_MAP.keys()), index=2)

        news_query = st.text_input("搜索关键词", placeholder="输入关键词或自然语言查询...")
        if news_query and st.button("搜索新闻", type="primary"):
            with show_error("检索失败"):
                with show_loading("检索中..."):
                    from src.rag.retriever import search_news
                    f = normalize_filters(game_filter, source_filter, days_filter)
                    docs = run_async_safe(search_news(news_query, k=10,
                                                      source_filter=f["source"],
                                                      game_filter=f["game"],
                                                      days_filter=f["days"]))
                    state = {**state, "docs": docs, "query": news_query}
                    ui_state.set_panel_state("news", state)
                    st.rerun()

        docs = state.get("docs") or []
        if docs:
            st.subheader(f"找到 {len(docs)} 条相关新闻")
            for doc in docs:
                render_news_doc(doc)
        elif state.get("query"):
            st.info("未找到相关新闻，尝试修改搜索条件")

    with tab2:
        if st.button("刷新新闻"):
            _load_rss.clear()
            st.rerun()
        articles = _load_rss()
        if articles is None:
            st.info("RSS 新闻源暂不可用，请稍后重试")
        elif articles:
            for article in articles[:15]:
                render_rss_article(article)
        else:
            st.info("暂无最新资讯")

    if st.button("← 返回对话", key="back_news", use_container_width=True):
        ui_state.set_tab("chat")
        st.rerun()
```

- [ ] **Step 4: app.py 接入 news 路由**

```python
elif tab == "news":
    from src.ui.panels.news import render_news_panel
    render_news_panel()
```

- [ ] **Step 5: 运行确认通过**

Run: `py -3.14 -m pytest tests/test_panels_news.py tests/test_app_shell.py -q`
Expected: `2 passed` + `5 passed`

- [ ] **Step 6: 提交**

```bash
git add src/ui/panels/news.py src/ui/app.py tests/test_panels_news.py
git commit -m "feat(ui): 新闻面板（双 Tab/检索/RSS 卡片）"
```

---

### Task 13: price_watch 面板

**Files:**
- Create: `src/ui/panels/price_watch.py`
- Modify: `src/ui/app.py`
- Test: `tests/test_panels_price.py`

- [ ] **Step 1: 写测试**

```python
"""price 面板测试 —— 监控/告警数据处理"""

from src.ui.panels import price_watch


def test_watch_rows_to_dict():
    rows = price_watch.watch_rows_to_dicts([
        {"id": 1, "game_name": "黑神话", "target_price": 200.0, "status": "active",
         "created_at": "2026-09-01"},
    ])
    assert rows[0]["game_name"] == "黑神话"
    assert rows[0]["target_price"] == 200.0


def test_alert_rows_columns():
    rows = price_watch.watch_rows_to_dicts([])
    assert rows == []
```

- [ ] **Step 2: 运行确认失败**

Run: `py -3.14 -m pytest tests/test_panels_price.py -q`
Expected: FAIL

- [ ] **Step 3: 实现 panels/price_watch.py（迁移自 _pages/price_watch.py；含"全部已读"、删除确认、48h 去重相关 UI）**

```python
"""价格监控面板 —— 添加/列表/告警三 Tab（迁移自 _pages/price_watch.py）"""

import streamlit as st
import pandas as pd

from src.services.watchlist_service import (
    list_watches, add_watch, delete_watch, list_unread_alerts, mark_all_alerts_read,
)
from src.ui import ui_state
from src.ui.session_state import run_async_safe


@st.cache_data(ttl=5, show_spinner=False)
def _load_watchlist(_cache_buster: int = 0) -> list:
    return run_async_safe(list_watches())


@st.cache_data(ttl=5, show_spinner=False)
def _load_alerts(_cache_buster: int = 0) -> list:
    return run_async_safe(list_unread_alerts())


def watch_rows_to_dicts(rows: list[dict]) -> list[dict]:
    """规整监控行（测试辅助：原样返回结构已知数据）"""
    return [
        {
            "id": r["id"], "game_name": r["game_name"],
            "target_price": float(r["target_price"]),
            "status": r["status"], "created_at": r.get("created_at", "-"),
        }
        for r in rows
    ]


def render_price_panel() -> None:
    """价格监控面板"""
    st.markdown("### 价格监控")
    tab1, tab2, tab3 = st.tabs(["➕ 添加监控", "📋 监控列表", "🔔 告警历史"])

    with tab1:
        with st.form("add_watchlist"):
            game_name = st.text_input("游戏名称", placeholder="输入 Steam 游戏完整名称")
            target_price = st.number_input("目标价格 (人民币)", min_value=0.0,
                                           step=10.0, format="%.2f")
            submitted = st.form_submit_button("添加监控", type="primary")
            if submitted and game_name:
                ok = run_async_safe(add_watch(game_name, target_price))
                if ok:
                    st.success(f"已添加监控: {game_name} @ ¥{target_price:.2f}")
                    _load_watchlist.clear()
                else:
                    st.error("添加失败，请检查数据库连接或日志")

    with tab2:
        col_btn1, col_btn2 = st.columns([1, 5])
        with col_btn1:
            if st.button("刷新", key="refresh_watchlist"):
                _load_watchlist.clear()
        items = watch_rows_to_dicts(_load_watchlist())
        if items:
            for item in items:
                col1, col2, col3, col4, col5 = st.columns([3, 2, 1.5, 1.5, 1])
                with col1:
                    st.markdown(f"**{item['game_name']}**")
                with col2:
                    st.markdown(f"目标价 <span style='color:var(--ok);'>¥{item['target_price']:.2f}</span>",
                                unsafe_allow_html=True)
                with col3:
                    label = "活跃" if item["status"] == "active" else item["status"]
                    st.caption(f"状态: {label}")
                with col4:
                    st.caption(item["created_at"])
                with col5:
                    delete_key = f"confirm_del_{item['id']}"
                    if delete_key not in st.session_state:
                        st.session_state[delete_key] = False
                    if st.button("删除", key=f"btn_{item['id']}"):
                        st.session_state[delete_key] = True
                    if st.session_state.get(delete_key):
                        @st.dialog("确认删除")
                        def confirm_del():
                            st.warning(f"确定要移除 **{item['game_name']}** 的监控吗？")
                            c1, c2 = st.columns(2)
                            with c1:
                                if st.button("确认删除", type="primary", use_container_width=True):
                                    ok = run_async_safe(delete_watch(item["id"]))
                                    if ok:
                                        _load_watchlist.clear()
                                        st.session_state[delete_key] = False
                                        st.rerun()
                                    else:
                                        st.error("删除失败，请查看日志")
                            with c2:
                                if st.button("取消", use_container_width=True):
                                    st.session_state[delete_key] = False
                                    st.rerun()
                        confirm_del()
                st.divider()
        else:
            st.info("暂无监控项目")

    with tab3:
        col_btn1, col_btn2 = st.columns([1, 5])
        with col_btn1:
            if st.button("刷新", key="refresh_alerts"):
                _load_alerts.clear()
        with col_btn2:
            if st.button("全部已读", key="mark_all_read"):
                run_async_safe(mark_all_alerts_read())
                _load_alerts.clear()
                st.rerun()
        alerts = _load_alerts()
        if alerts:
            df = pd.DataFrame(alerts)
            df.columns = ["当前价 ¥", "目标价 ¥", "商店", "触发时间"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("暂无未读告警")

    if st.button("← 返回对话", key="back_price", use_container_width=True):
        ui_state.set_tab("chat")
        st.rerun()
```

- [ ] **Step 4: app.py 接入 price 路由**

```python
elif tab == "price":
    from src.ui.panels.price_watch import render_price_panel
    render_price_panel()
```

- [ ] **Step 5: 运行确认通过**

Run: `py -3.14 -m pytest tests/test_panels_price.py tests/test_app_shell.py -q`
Expected: `2 passed` + `5 passed`

- [ ] **Step 6: 提交**

```bash
git add src/ui/panels/price_watch.py src/ui/app.py tests/test_panels_price.py
git commit -m "feat(ui): 价格监控面板（三 Tab/删除确认/全部已读）"
```

---

### Task 14: recommend 面板

**Files:**
- Create: `src/ui/panels/recommend.py`
- Modify: `src/ui/app.py`
- Test: `tests/test_panels_recommend.py`

- [ ] **Step 1: 写测试**

```python
"""recommend 面板测试 —— 画像提示与搜索词构建"""

from src.ui.panels import recommend
from src.services.chat_service import build_profile_text


def test_profile_label_text():
    assert recommend.profile_label({"favorite_genres": "RPG", "favorite_games": "黑神话"}) is not None
    assert recommend.profile_label({}) is None


def test_search_query_with_profile():
    profile = {"favorite_genres": "动作"}
    q = recommend.build_search_query("黑神话", profile, genre_pref=["动作"])
    assert q.startswith("用户画像:")
```

- [ ] **Step 2: 运行确认失败**

Run: `py -3.14 -m pytest tests/test_panels_recommend.py -q`
Expected: FAIL

- [ ] **Step 3: 实现 panels/recommend.py（迁移自 _pages/recommend.py）**

```python
"""推荐面板 —— 画像注入 + 推荐卡流（迁移自 _pages/recommend.py）"""

import streamlit as st

from src.services.chat_service import ChatService, build_profile_text
from src.ui import ui_state
from src.ui.session_state import run_async_safe
from src.ui.components._loading import show_loading
from src.ui.components._error import show_error
from src.ui.components.game_card import render_game_card


def profile_label(profile: dict | None) -> str | None:
    text = build_profile_text(profile or {})
    return text if text else None


def build_search_query(game_input: str, profile: dict | None,
                       genre_pref: list[str]) -> str:
    text = build_profile_text(profile or {})
    return f"{text}\n{game_input}" if text else game_input


def render_recommend_panel() -> None:
    """推荐面板"""
    st.markdown("### 游戏推荐")

    sid = st.session_state.get("active_session_id")
    user_profile = None
    if sid:
        user_profile = run_async_safe(ChatService().load_profile(sid))
    label = profile_label(user_profile)
    if label:
        st.caption(f"✨ 已用你的偏好生成：{label}")

    game_input = st.text_input("游戏名称", placeholder="例如: 巫师3, 原神, 空洞骑士...")
    col1, col2 = st.columns(2)
    with col1:
        genre_pref = st.multiselect("偏好类型（可选）",
                                    ["动作", "冒险", "RPG", "策略", "模拟", "独立", "开放世界", "魂系"])
    with col2:
        st.selectbox("偏好平台（可选）", ["不限", "PC", "PlayStation", "Xbox", "Nintendo Switch"])

    if st.button("🎯 推荐游戏", type="primary", disabled=not game_input):
        with show_error("推荐失败"):
            with show_loading("搜索推荐中..."):
                from src.tools.rawg import RAWGGameSearchTool, RAWGGameRecommendationsTool

                async def _run():
                    search_query = build_search_query(game_input, user_profile, genre_pref)
                    results = await RAWGGameSearchTool()._arun(search_query)
                    recs = []
                    game_name = None
                    if results:
                        game_id = results[0]["id"]
                        game_name = results[0]["name"]
                        recs = await RAWGGameRecommendationsTool()._arun(game_id)
                        if genre_pref:
                            for rec in recs:
                                rec["_match_score"] = len(set(genre_pref) & set(rec.get("genres", [])))
                            recs.sort(key=lambda r: r.get("_match_score", 0), reverse=True)
                    return results, recs, game_name

                results, recs, game_name = run_async_safe(_run())
                if not results:
                    st.warning(f"未找到 '{game_input}' 的相关信息")
                else:
                    st.success(f"基于 **{game_name}** 的推荐:")
                    if recs:
                        for i, rec in enumerate(recs):
                            badge = ""
                            if rec.get("_match_score", 0) > 0:
                                badge = f" 🎯匹配度: {'⭐' * min(rec['_match_score'], 3)}"
                            render_game_card(rec, rank=i + 1, match_badge=badge)
                    else:
                        st.info("暂无推荐数据，试试搜索其他游戏")

    if st.button("← 返回对话", key="back_recommend", use_container_width=True):
        ui_state.set_tab("chat")
        st.rerun()
```

- [ ] **Step 4: app.py 接入 recommend 路由**

```python
elif tab == "recommend":
    from src.ui.panels.recommend import render_recommend_panel
    render_recommend_panel()
```

- [ ] **Step 5: 运行确认通过**

Run: `py -3.14 -m pytest tests/test_panels_recommend.py tests/test_app_shell.py -q`
Expected: `2 passed` + `5 passed`

- [ ] **Step 6: 提交**

```bash
git add src/ui/panels/recommend.py src/ui/app.py tests/test_panels_recommend.py
git commit -m "feat(ui): 推荐面板（画像标签/推荐卡流）"
```

---

# 阶段 E：收尾与回归

### Task 15: 删除 _pages/、清理 session_state、回归

**Files:**
- Delete: `src/ui/_pages/`（6 文件）
- Modify: `src/ui/session_state.py`（移除 init_session_state 的旧键与 get_chat_history/add_chat_message 旧 API）、`src/ui/theme.py`（补 blink 动画）、`tests/test_imports.py`（枚举移除 _pages——参数化自动感知，无需改，仅确认）
- Test: 全量回归 + 裸 HEX 扫描转绿 + AppTest 全 tab 冒烟

- [ ] **Step 1: 删除 _pages 目录**

Run:

```bash
git rm -r src/ui/_pages
```

- [ ] **Step 2: 清理 session_state.py（移除旧页遗留 API）**

将 `init_session_state()`、`get_chat_history()`、`add_chat_message()` 三个函数删除（聊天会话体系 init_chat_sessions/create_chat_session/get_active_messages/add_chat_session_message/switch_session 与 run_async_safe 保留），文件开头改为：

```python
"""Streamlit 跨页面会话状态管理

V2 起只保留两件事：run_async_safe（异步桥接）与聊天会话体系。
页面级状态统一走 src/ui/ui_state.py。
"""

import streamlit as st
from src.utils.async_utils import run_coro_sync


def run_async_safe(coro):
    """在 Streamlit 的同步上下文中安全运行 async 协程。"""
    return run_coro_sync(lambda: coro)


def init_chat_sessions():
    """初始化对话会话列表（支持多轮对话管理）"""
    if "chat_sessions" not in st.session_state:
        st.session_state["chat_sessions"] = {}
    if "active_session_id" not in st.session_state:
        st.session_state["active_session_id"] = None


def create_chat_session() -> str:
    """创建新对话会话，返回 session_id"""
    import uuid
    sid = str(uuid.uuid4())[:8]
    st.session_state["chat_sessions"][sid] = {"title": "新对话", "messages": [], "summary": None}
    st.session_state["active_session_id"] = sid
    return sid


def get_active_messages() -> list[dict]:
    """获取当前活跃会话的消息列表"""
    init_chat_sessions()
    sid = st.session_state.get("active_session_id")
    if sid and sid in st.session_state["chat_sessions"]:
        return st.session_state["chat_sessions"][sid]["messages"]
    return []


def add_chat_session_message(role: str, content: str):
    """向当前活跃会话添加消息"""
    messages = get_active_messages()
    if role == "user" and not messages:
        sid = st.session_state["active_session_id"]
        st.session_state["chat_sessions"][sid]["title"] = content[:30]
    messages.append({"role": role, "content": content})


def switch_session(sid: str):
    """切换到指定会话"""
    st.session_state["active_session_id"] = sid
```

若 `app.py` 仍调用 `init_session_state()`，同步移除该调用（主壳第 Task 3 代码中删除该行）。

- [ ] **Step 3: theme.py 补光标动画（三主题共用）**

在 `theme.py` 的 `_BASE_OVERRIDES` 末尾追加：

```python
_EXTRA_ANIMATIONS = """
@keyframes blink {{ 0%{{opacity:1;}} 50%{{opacity:.2;}} 100%{{opacity:1;}} }}
"""
```

并在 `get_theme_css` 返回串中拼接 `_EXTRA_ANIMATIONS`：

```python
    return var_block + "\n" + _BASE_OVERRIDES.format() + "\n" + _EXTRA_ANIMATIONS
```

- [ ] **Step 4: 全量回归**

Run: `py -3.14 -m compileall -q src config scripts`
Expected: 无语法错误

Run: `py -3.14 -m pytest -q`
Expected: `86 passed`（UI 层用例全部绿，原有 86 个用例不受影响；新增 UI 用例约 30+，总计 110+ 通过）

Run: `py -3.14 -m pytest tests/test_theme.py::TestNoBareHexInUI -q`
Expected: PASS（裸 HEX 全部清零）

Run: `py -3.14 -m pytest tests/test_app_shell.py -q`
Expected: `5 passed`（6 tab 全路由可渲染）

- [ ] **Step 5: 手动冒烟清单（浏览器体验）**

```bash
py -3.14 -m src.main ui
```

逐项检查：
1. 三主题切换（侧栏底部 3 按钮）：背景/按钮/气泡/表格颜色即时变化，无裸色块
2. 聊天：空态引导卡 → 点击示例问题 → 流式打字光标 → 完成气泡；新会话创建、切换、删除
3. 快捷指令胶囊：点击填入草稿 → 发送 `/price xxx` 能路由
4. 各面板：搜索（筛选+结果流）、价格（添加/删除/全部已读）、新闻（双 Tab）、推荐（画像标签）、概览（统计卡+快捷入口）
5. 面板切换后返回聊天，面板状态（如搜索结果）保留
6. 窄屏：sidebar 折叠后图标栏仍可用
7. 若无 MySQL/Redis/LLM key：页面应降级显示空数据而非崩溃（dashboard_service 已有日志）

- [ ] **Step 6: 更新 README 的 UI 章节**

在 `README.md` 的架构图后追加：

```markdown
## UI（V2）

单页三列架构：图标栏（sidebar）+ 模式分发（`ui["tab"]`）+ 三套可切换主题
（theme.py，霓虹电竞默认）。聊天为中心，其余功能为工具面板（src/ui/panels/）。
UI 代码禁止裸 HEX 颜色 —— 一律使用 theme.py 的 CSS 变量（tests/test_theme.py 扫描）。
```

- [ ] **Step 7: 提交**

```bash
git add -A
git commit -m "feat(ui): UI V2 完成 —— 删除 _pages、清理旧 API、光标动画、全量回归"

# 若 final 需要（可选）：
git commit -m "docs: README 补充 UI V2 章节" -- README.md
```

---

## 任务依赖与里程碑

```
Task 1 ui_state ─┐
Task 2 theme   ──┼─→ Task 3 app 主壳 v1 ─┐
Task 4 基础组件 ─┘                         ├─→ Task 6-9 聊天中心 ─┐
Task 5 卡片升级 ──────────────────────────→ Task 10-14 面板迁移 ──┴─→ Task 15 收尾回归
```

里程碑：Task 3 后应用可跑（占位面板）；Task 9 后聊天中完整可用；Task 14 后 6 入口全部真实；Task 15 后 V2 完整。

## 已知偏差与说明（相对 spec）

1. **"停止按钮"本轮不做**：纯 Streamlit 脚本模型下，流式循环内无法响应用户点击（按钮事件在下一次 rerun 才生效，而流式过程阻塞在当次 rerun 中）。与 `st.fragment` 优化一起列入后续备选（spec 已列）。
2. **chat/session_list 的删除确认**：V1 的 `st.dialog` 确认保留在面板内（Task 13 同款模式），Task 7 先提供轻量删除，Task 9 chat_panel 编排时不冲突。
3. **theme.get_theme_css 的动画注入**在 Task 15 统一补齐（Task 8 依赖它但不阻塞）。

## 执行备注（Task 15 收尾时追加）

- 聊天 DB 历史恢复（load_recent）未迁移：fresh session id 无法恢复（既有局限，
  旧页面同）。正确修复需 durable sid + ChatService.list_sessions API —— 记录为后续优化。
- 删除确认对话框闭包陷阱（删错行）已在本轮修复（panels 与迁移源双修）。
- AppTest 无法覆盖 st.dialog 事件（streamlit.testing 无支持）—— 对话框交互以
  真实浏览器冒烟为准。
