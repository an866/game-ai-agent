# UI 改进实施计划

> ✅ **状态：已完成** (2026-06-22) — 全部 15 个任务、16 个提交已合入 `master`
>
> 详细记录见 [设计文档](../specs/2026-06-22-ui-improvement-design.md)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Streamlit 前端 6 页面全面改进 —— 数据对接、功能修复、体验统一

**Architecture:** 分 4 批 15 个任务，逐批推进。每批结束时页面可独立验证。改动触及 6 个页面文件、2 个工具文件、1 个 retriever、2 个新增组件。

**Tech Stack:** Python 3.14, Streamlit, LangChain Chroma, SQLAlchemy Async, httpx

---

## 文件结构

```
修改:
  src/ui/_pages/home.py          — 批次 A: 数据对接
  src/tools/rawg.py              — 批次 B: 增加 platforms/genres 参数
  src/ui/_pages/search.py        — 批次 B: 筛选 + 详情
  src/ui/_pages/recommend.py     — 批次 B: 偏好过滤
  src/ui/_pages/price_watch.py   — 批次 C: 异步 + 表格 + 确认
  src/rag/retriever.py           — 批次 C: 扩展 filter 支持
  src/ui/_pages/news.py          — 批次 C: Tab 布局 + 筛选
  src/ui/_pages/chat.py          — 批次 D: 历史侧边栏
  src/ui/session_state.py        — 批次 D: 历史管理
  src/ui/app.py                  — 批次 D: 初始化调用

新增:
  src/ui/components/_loading.py  — 批次 D: 统一 loading 组件
  src/ui/components/_error.py    — 批次 D: 统一 error 组件
```

---

### Task A1: 首页 — DB 统计数据

**Files:**
- Modify: `src/ui/_pages/home.py`

- [ ] **Step 1: 替换指标卡数据加载逻辑**

用 `run_async_safe()` 从数据库获取 watchlist 计数和告警计数。将 `home.py` 改为：

```python
"""首页 —— 仪表盘概览"""

import streamlit as st
from src.ui.session_state import run_async_safe

st.title("游戏 AI 助手")
st.markdown("PC 游戏信息查询 | 价格追踪 | 新闻聚合 | 智能推荐")


# ---------- 加载统计数据 ----------

@st.cache_data(ttl=60, show_spinner=False)
def load_stats(_cache_buster: int = 0) -> dict:
    """加载首页仪表盘统计数据（缓存 60 秒）"""
    async def _fetch():
        from src.data.database import async_session_factory
        from src.data.repository import WatchlistRepository, PriceAlertRepository

        async with async_session_factory() as session:
            watchlist_count = await WatchlistRepository(session).get_count()
            alert_count = await PriceAlertRepository(session).get_count_unread()
        return {"watchlist": watchlist_count, "alerts": alert_count}

    return run_async_safe(_fetch())


stats = load_stats()

# ---------- 指标卡 ----------

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(label="活跃监控", value=stats["watchlist"])
with col2:
    st.metric(label="待读告警", value=stats["alerts"])
with col3:
    st.metric(label="新闻库", value="-", help="已索引的新闻文档数")
with col4:
    st.metric(label="今日最低折扣", value="-")

st.divider()

st.subheader("快捷操作")

quick_col1, quick_col2, quick_col3, quick_col4 = st.columns(4)

with quick_col1:
    if st.button("查游戏信息", use_container_width=True):
        st.switch_page("search")

with quick_col2:
    if st.button("看最新折扣", use_container_width=True):
        st.switch_page("price_watch")

with quick_col3:
    if st.button("找类似游戏", use_container_width=True):
        st.switch_page("recommend")

with quick_col4:
    if st.button("看游戏新闻", use_container_width=True):
        st.switch_page("news")

st.divider()

st.subheader("热门游戏")

hot_games = [
    {"name": "Counter-Strike 2", "players": "-", "appid": 730},
    {"name": "Dota 2", "players": "-", "appid": 570},
    {"name": "PUBG: BATTLEGROUNDS", "players": "-", "appid": 578080},
    {"name": "Apex Legends", "players": "-", "appid": 1172470},
    {"name": "原神", "players": "-", "appid": None},
]

for game in hot_games:
    st.markdown(f"- **{game['name']}** — 在线: {game['players']}")
```

- [ ] **Step 2: 运行验证**

```bash
python -m streamlit run src/ui/app.py --server.port 8501
```

预期：首页指标卡「活跃监控」「待读告警」显示数据库真实数字（若 DB 为空则显示 0），「新闻库」「最低折扣」暂为 `-`。

- [ ] **Step 3: 提交**

```bash
git add src/ui/_pages/home.py
git commit -m "feat: 首页指标卡对接数据库统计数据"
```

---

### Task A2: 首页 — ChromaDB + CheapShark 数据

**Files:**
- Modify: `src/ui/_pages/home.py`

- [ ] **Step 1: 扩展 load_stats 函数**

在 `load_stats()` 函数中增加 ChromaDB 文档计数和 CheapShark 最低折扣查询：

```python
@st.cache_data(ttl=120, show_spinner=False)
def load_stats(_cache_buster: int = 0) -> dict:
    """加载首页仪表盘统计数据（缓存 120 秒）"""
    async def _fetch():
        from src.data.database import async_session_factory
        from src.data.repository import WatchlistRepository, PriceAlertRepository

        async with async_session_factory() as session:
            watchlist_count = await WatchlistRepository(session).get_count()
            alert_count = await PriceAlertRepository(session).get_count_unread()

        return {
            "watchlist": watchlist_count,
            "alerts": alert_count,
        }

    def _chroma_count():
        try:
            from src.rag.store import get_vector_store
            store = get_vector_store()
            return store._collection.count()
        except Exception:
            return 0

    def _best_deal():
        try:
            from src.tools.cheapshark import CheapSharkDealsTool
            tool = CheapSharkDealsTool()
            deals = run_async_safe(tool._arun("", on_sale=True))
            if deals:
                best = deals[0]
                return f"{best['savings']:.0f}% ({best['title'][:20]})"
        except Exception:
            pass
        return "-"

    stats = run_async_safe(_fetch())
    stats["news_count"] = _chroma_count()
    stats["best_deal"] = _best_deal()
    return stats
```

- [ ] **Step 2: 更新指标卡列**

```python
with col3:
    st.metric(label="新闻库", value=stats.get("news_count", 0), help="已索引的新闻文档数")
with col4:
    st.metric(label="今日最低折扣", value=stats.get("best_deal", "-"))
```

- [ ] **Step 3: 运行验证**

预期：ChromaDB 有数据时显示文档数；CheapShark API 正常时显示最低折扣（如 `85% (Elden Ring)`），两者故障时均降级显示 `0` / `-` 不崩溃。

- [ ] **Step 4: 提交**

```bash
git add src/ui/_pages/home.py
git commit -m "feat: 首页新闻库计数和最低折扣对接真实数据"
```

---

### Task A3: 首页 — 热门游戏实时在线人数

**Files:**
- Modify: `src/ui/_pages/home.py`

- [ ] **Step 1: 添加动态加载函数并替换热门游戏列表**

在文件 `hot_games` 列表处替换为调用 `SteamCurrentPlayersTool`：

```python
@st.cache_data(ttl=300, show_spinner=False)
def load_hot_games(_cache_buster: int = 0) -> list[dict]:
    """加载热门游戏实时在线人数（缓存 5 分钟）"""
    hot_games = [
        {"name": "Counter-Strike 2", "appid": 730},
        {"name": "Dota 2", "appid": 570},
        {"name": "PUBG: BATTLEGROUNDS", "appid": 578080},
        {"name": "Apex Legends", "appid": 1172470},
        {"name": "Genshin Impact", "appid": None},
    ]

    async def _fetch_players():
        from src.tools.steam_api import SteamCurrentPlayersTool
        tool = SteamCurrentPlayersTool()
        results = {}
        for game in hot_games:
            if game["appid"] is None:
                results[game["name"]] = None
                continue
            try:
                data = await tool._arun(game["appid"])
                results[game["name"]] = data.get("current_players", 0)
            except Exception:
                results[game["name"]] = None
        return results

    players = run_async_safe(_fetch_players())

    result = []
    for game in hot_games:
        count = players.get(game["name"])
        if count is not None:
            result.append({"name": game["name"], "players": f"{count:,}"})
        else:
            result.append({"name": game["name"], "players": "-"})
    return result


# 替换原来的 hot_games 硬编码列表和渲染循环:
hot_games = load_hot_games()
for game in hot_games:
    st.markdown(f"- **{game['name']}** — 在线: {game['players']}")
```

- [ ] **Step 2: 运行验证**

预期：热门游戏列表显示 Steam 实时在线人数（如 `Counter-Strike 2 — 在线: 1,523,847`），Steam API 故障时显示 `-`。

- [ ] **Step 3: 提交**

```bash
git add src/ui/_pages/home.py
git commit -m "feat: 首页热门游戏对接 Steam 实时在线人数"
```

---

### Task B1: RAWG 工具 — 支持 platforms/genres 参数

**Files:**
- Modify: `src/tools/rawg.py:12-55`

- [ ] **Step 1: 扩展 RAWGSearchInput 和 _search 方法**

```python
class RAWGSearchInput(BaseModel):
    query: str = Field(description="游戏名称")
    page: int = Field(default=1, description="页码")
    platforms: str | None = Field(default=None, description="平台过滤，多个用逗号分隔，如 'pc,playstation'")
    genres: str | None = Field(default=None, description="类型过滤，多个用逗号分隔，如 'action,rpg'")


class RAWGGameSearchTool(GameDataTool):
    """搜索 RAWG 游戏数据库"""
    name: str = "rawg_search_game"
    description: str = "在 RAWG 游戏数据库中搜索游戏，返回游戏 ID、名称、评分、类型等。输入为游戏名称。"
    args_schema: type[BaseModel] = RAWGSearchInput
    cache_ttl: int = 600

    async def _arun(self, query: str, page: int = 1, platforms: str | None = None,
                    genres: str | None = None, **kwargs: Any) -> Any:
        return await self._cached_call(self._search, query, page, platforms, genres)

    async def _search(self, query: str, page: int = 1,
                      platforms: str | None = None, genres: str | None = None) -> list[dict]:
        url = "https://api.rawg.io/api/games"
        params: dict[str, str | int] = {
            "key": settings.rawg_api_key,
            "search": query,
            "page": page,
            "page_size": 10,
        }
        if platforms:
            params["platforms"] = platforms
        if genres:
            params["genres"] = genres

        async with httpx.AsyncClient(headers=get_headers(), follow_redirects=True) as client:
            resp = await client.get(url, params=params, timeout=self.request_timeout)
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "id": game["id"], "name": game["name"], "slug": game["slug"],
                    "rating": game.get("rating"), "released": game.get("released"),
                    "genres": [g["name"] for g in game.get("genres", [])],
                    "platforms": [p["platform"]["name"] for p in game.get("platforms", [])],
                    "background_image": game.get("background_image"),
                    "metacritic": game.get("metacritic"),
                }
                for game in data.get("results", [])
            ]
```

- [ ] **Step 2: 运行验证**

```bash
python -c "import asyncio; from src.tools.rawg import RAWGGameSearchTool; t = RAWGGameSearchTool(); print(len(asyncio.run(t._arun('Elden Ring', platforms='pc'))))"
```

预期：正常返回搜索结果。

- [ ] **Step 3: 提交**

```bash
git add src/tools/rawg.py
git commit -m "feat: RAWG 搜索工具增加 platforms/genres 过滤参数"
```

---

### Task B2: 搜索页 — 筛选器实际生效

**Files:**
- Modify: `src/ui/_pages/search.py`

- [ ] **Step 1: 映射 UI 选项到 RAWG API 参数，传入搜索调用**

在搜索按钮逻辑中添加筛选参数映射：

```python
PLATFORM_MAP = {
    "PC": "4",
    "PlayStation": "187,18,16",
    "Xbox": "1,14",
    "Nintendo Switch": "7",
    "iOS": "3",
    "Android": "21",
}

GENRE_MAP = {
    "动作": "action",
    "冒险": "adventure",
    "RPG": "role-playing-games-rpg",
    "策略": "strategy",
    "模拟": "simulation",
    "体育": "sports",
    "独立": "indie",
    "大型多人在线": "massively-multiplayer",
}

if query and st.button("搜索", type="primary"):
    with st.spinner("搜索中..."):
        try:
            plat_param = ",".join(PLATFORM_MAP[p] for p in platform_filter) if platform_filter else None
            genre_param = ",".join(GENRE_MAP[g] for g in genre_filter) if genre_filter else None

            from src.tools.rawg import RAWGGameSearchTool
            tool = RAWGGameSearchTool()
            results = run_async_safe(tool._arun(query, platforms=plat_param, genres=genre_param))

            if results:
                st.session_state["search_results"] = results
            else:
                st.warning("未找到匹配的游戏，尝试缩短关键词或减少筛选条件")
        except Exception as e:
            st.error(f"搜索失败: {e}")
```

- [ ] **Step 2: 运行验证**

选择平台「PC」和类型「RPG」，搜索「Final Fantasy」，预期结果只返回 PC 平台的 RPG 游戏。

- [ ] **Step 3: 提交**

```bash
git add src/ui/_pages/search.py
git commit -m "feat: 搜索页平台和类型筛选器实际生效"
```

---

### Task B3: 搜索页 — 查看详情展开

**Files:**
- Modify: `src/ui/_pages/search.py`

- [ ] **Step 1: 将「查看详情」替换为 expander 内联展开**

替换结果卡片中的「查看详情」按钮：

```python
    results = st.session_state.get("search_results")
    if results:
        st.subheader(f"找到 {len(results)} 个结果")
        for game in results:
            with st.container(border=True):
                game_col1, game_col2 = st.columns([1, 3])
                with game_col1:
                    if game.get("background_image"):
                        st.image(game["background_image"], use_container_width=True)
                with game_col2:
                    st.markdown(f"### {game['name']}")
                    if game.get("rating"):
                        st.markdown(f"评分: **{game['rating']}/5** | Metacritic: {game.get('metacritic', '暂无')}")
                    if game.get("released"):
                        st.markdown(f"发售日: {game['released']}")
                    if game.get("genres"):
                        st.markdown(f"类型: {', '.join(game['genres'])}")
                    if game.get("platforms"):
                        st.markdown(f"平台: {', '.join(game['platforms'][:5])}")

                with st.expander(f"查看 {game['name']} 详情"):
                    try:
                        from src.tools.rawg import RAWGGameDetailTool
                        detail_tool = RAWGGameDetailTool()
                        detail = run_async_safe(detail_tool._arun(game["id"]))
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
                            if detail.get("developers"):
                                st.caption(f"开发商: {', '.join(detail['developers'])}")
                            if detail.get("publishers"):
                                st.caption(f"发行商: {', '.join(detail['publishers'])}")
                            if detail.get("website"):
                                st.link_button("官网", detail["website"])
                        else:
                            st.info("暂无详细信息")
                    except Exception:
                        st.info("详情加载失败")
    elif not query:
        st.info("输入游戏名称开始搜索")
```

- [ ] **Step 2: 运行验证**

搜索游戏后点展开详情，预期在卡片内展开显示描述、评分、开发商等信息。

- [ ] **Step 3: 提交**

```bash
git add src/ui/_pages/search.py
git commit -m "feat: 搜索页查看详情改为内联 expander 展开"
```

---

### Task B4: 推荐页 — 偏好过滤并增加详情

**Files:**
- Modify: `src/ui/_pages/recommend.py`

- [ ] **Step 1: 偏好传入推荐排序逻辑，每款游戏增加 expander**

替换 `if st.button("推荐游戏"...):` 后的整个逻辑块：

```python
if st.button("推荐游戏", type="primary", disabled=not game_input):
    with st.spinner("搜索推荐中..."):
        try:
            from src.tools.rawg import RAWGGameSearchTool, RAWGGameRecommendationsTool, RAWGGameDetailTool

            async def _run():
                search_tool = RAWGGameSearchTool()
                results = await search_tool._arun(game_input)
                recs = []
                game_name = None
                if results:
                    game_id = results[0]["id"]
                    game_name = results[0]["name"]
                    rec_tool = RAWGGameRecommendationsTool()
                    recs = await rec_tool._arun(game_id)

                    if genre_pref:
                        for rec in recs:
                            match = len(set(genre_pref) & set(rec.get("genres", [])))
                            rec["_match_score"] = match
                        recs.sort(key=lambda r: r.get("_match_score", 0), reverse=True)

                return results, recs, game_name

            results, recs, game_name = run_async_safe(_run())

            if not results:
                st.warning(f"未找到 '{game_input}' 的相关信息")
            else:
                st.success(f"基于 **{game_name}** 的推荐 ({len(recs)} 个):")

                if recs:
                    for i, rec in enumerate(recs):
                        with st.container(border=True):
                            r_col1, r_col2 = st.columns([1, 3])
                            with r_col1:
                                if rec.get("background_image"):
                                    st.image(rec["background_image"], use_container_width=True)
                            with r_col2:
                                match_badge = ""
                                if rec.get("_match_score", 0) > 0:
                                    match_badge = f" 🎯匹配度: {'⭐' * min(rec['_match_score'], 3)}"
                                st.markdown(f"### {i+1}. {rec['name']}{match_badge}")
                                if rec.get("rating"):
                                    st.markdown(f"评分: {rec['rating']}/5")
                                if rec.get("released"):
                                    st.markdown(f"发售日: {rec['released']}")
                                if rec.get("genres"):
                                    st.markdown(f"类型: {', '.join(rec['genres'])}")

                            with st.expander(f"{rec['name']} 详情"):
                                try:
                                    detail_tool = RAWGGameDetailTool()
                                    detail = run_async_safe(detail_tool._arun(rec["id"]))
                                    if detail and detail.get("description"):
                                        st.markdown(detail["description"][:800])
                                        if detail.get("tags"):
                                            st.caption(f"标签: {', '.join(detail['tags'][:10])}")
                                    else:
                                        st.info("暂无更多信息")
                                except Exception:
                                    st.info("详情加载失败")
                else:
                    st.info("暂无推荐数据，试试搜索其他游戏")
        except Exception as e:
            st.error(f"推荐失败: {e}")
```

- [ ] **Step 2: 运行验证**

搜索「巫师3」获取推荐，选偏好 RPG + 开放世界，预期匹配度高的排前面带 ⭐ 标记。

- [ ] **Step 3: 提交**

```bash
git add src/ui/_pages/recommend.py
git commit -m "feat: 推荐页偏好匹配度排序 + 内联详情展开"
```

---

### Task C1: 价格监控 — 统一异步模式

**Files:**
- Modify: `src/ui/_pages/price_watch.py`

- [ ] **Step 1: 用 run_async_safe 替代 asyncio.run()**

替换 `_load_watchlist` 和 `_load_alerts` 函数：

```python
@st.cache_data(ttl=5, show_spinner=False)
def _load_watchlist(_cache_buster: int = 0) -> list:
    """加载活跃监控列表"""
    from src.data.database import async_session_factory
    from src.data.repository import WatchlistRepository

    async def _run():
        async with async_session_factory() as session:
            items = await WatchlistRepository(session).get_all_active()
            return [
                {
                    "id": item.id,
                    "game_name": item.game_name,
                    "target_price": float(item.target_price),
                    "status": item.status,
                    "created_at": str(item.created_at)[:10] if item.created_at else "-",
                }
                for item in items
            ]
    return run_async_safe(_run())


@st.cache_data(ttl=5, show_spinner=False)
def _load_alerts(_cache_buster: int = 0) -> list:
    """加载未读告警"""
    from src.data.database import async_session_factory
    from src.data.repository import PriceAlertRepository

    async def _run():
        async with async_session_factory() as session:
            items = await PriceAlertRepository(session).get_unread(20)
            return [
                {
                    "current_price": float(a.current_price),
                    "target_price": float(a.target_price),
                    "store_name": a.store_name,
                    "triggered_at": str(a.triggered_at)[:19] if a.triggered_at else "-",
                }
                for a in items
            ]
    return run_async_safe(_run())
```

- [ ] **Step 2: 更新 Tab2 中对 item 的访问（ORM 对象 → dict）**

```python
items = _load_watchlist()
if items:
    for item in items:
        col1, col2, col3, col4, col5 = st.columns([3, 2, 1.5, 1.5, 1])
        with col1:
            st.markdown(f"**{item['game_name']}**")
        with col2:
            st.caption(f"目标价 ¥{item['target_price']:.2f}")
        with col3:
            status_label = "活跃" if item['status'] == "active" else item['status']
            st.caption(f"状态: {status_label}")
        with col4:
            st.caption(item['created_at'])
        with col5:
            if st.button("删除", key=f"del_{item['id']}"):
                run_async_safe(delete_item(item['id']))
                _load_watchlist.clear()
                st.rerun()
        st.divider()
```

- [ ] **Step 3: 更新 Tab3 中使用 _load_alerts 返回值的部分**

```python
alerts = _load_alerts()
if alerts:
    df = pd.DataFrame(alerts)
    df.columns = ["当前价 ¥", "目标价 ¥", "商店", "触发时间"]
    st.dataframe(df, use_container_width=True, hide_index=True)
```

- [ ] **Step 4: 移除顶部的 `import asyncio`（已不需要）**

- [ ] **Step 5: 运行验证**

切换三个 Tab，刷新监控列表和告警，确认无 WebSocket/AsyncIO 错误。

- [ ] **Step 6: 提交**

```bash
git add src/ui/_pages/price_watch.py
git commit -m "refactor: 价格监控页统一异步模式，移除 asyncio.run"
```

---

### Task C2: 价格监控 — 删除确认对话框

**Files:**
- Modify: `src/ui/_pages/price_watch.py`

- [ ] **Step 1: 删除操作加入 st.dialog 确认**

在 Tab2 循环的删除按钮处添加确认：

```python
with col5:
    delete_key = f"del_{item['id']}"
    if delete_key not in st.session_state:
        st.session_state[delete_key] = False

    if st.button("删除", key=f"btn_{item['id']}"):
        st.session_state[delete_key] = True

    if st.session_state.get(delete_key):
        @st.dialog(f"确认删除")
        def confirm_del():
            st.warning(f"确定要移除 **{item['game_name']}** 的监控吗？")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("确认删除", type="primary", use_container_width=True):
                    run_async_safe(delete_item(item['id']))
                    _load_watchlist.clear()
                    st.session_state[delete_key] = False
                    st.rerun()
            with c2:
                if st.button("取消", use_container_width=True):
                    st.session_state[delete_key] = False
                    st.rerun()
        confirm_del()
```

- [ ] **Step 2: 运行验证**

点击删除按钮 → 弹确认对话框 → 确认后列表刷新，取消后恢复。

- [ ] **Step 3: 提交**

```bash
git add src/ui/_pages/price_watch.py
git commit -m "feat: 价格监控删除操作增加确认对话框"
```

---

### Task C3: Retriever — 扩展 game/days 过滤

**Files:**
- Modify: `src/rag/retriever.py:23-38`

- [ ] **Step 1: 扩展 search_news 签名和 filter 构建逻辑**

```python
async def search_news(
    query: str,
    k: int = 5,
    source_filter: str | None = None,
    game_filter: str | None = None,
    days_filter: int | None = None,
) -> list[Document]:
    """搜索新闻 —— MMR 语义检索 + 可选来源/游戏/时间过滤"""
    from src.rag.store import get_retriever, get_vector_store
    from datetime import datetime, timedelta

    filter_conditions: list[dict] = []

    if source_filter:
        filter_conditions.append({"source_name": source_filter})
    if game_filter:
        filter_conditions.append({"game_name": game_filter})
    if days_filter:
        cutoff = (datetime.now() - timedelta(days=days_filter)).isoformat()
        filter_conditions.append({"published_iso": {"$gte": cutoff}})

    if filter_conditions:
        chroma_filter = filter_conditions[0] if len(filter_conditions) == 1 else {"$and": filter_conditions}
        retriever = get_vector_store().as_retriever(
            search_type="mmr",
            search_kwargs={"k": k, "fetch_k": 20, "filter": chroma_filter},
        )
    else:
        retriever = get_retriever(k=k, fetch_k=20)

    docs = await retriever.ainvoke(query)
    return docs
```

- [ ] **Step 2: 运行验证**

```bash
python -c "import asyncio; from src.rag.retriever import search_news; docs = asyncio.run(search_news('游戏更新', k=3, source_filter='Steam')); print(len(docs), set(d.metadata.get('source_name') for d in docs))"
```

预期：只返回 Steam 来源的新闻。

- [ ] **Step 3: 提交**

```bash
git add src/rag/retriever.py
git commit -m "feat: retriever 增加 game_filter 和 days_filter 支持"
```

---

### Task C4: 新闻页 — Tab 布局 + 筛选器生效

**Files:**
- Modify: `src/ui/_pages/news.py`

- [ ] **Step 1: 重写为 Tab 布局，筛选器传入 search_news**

完整替换 `news.py`：

```python
"""游戏新闻页"""

import streamlit as st
from src.ui.session_state import run_async_safe

st.title("游戏新闻")

tab1, tab2 = st.tabs(["新闻搜索", "最新资讯"])

with tab1:
    st.subheader("搜索新闻")

    col1, col2, col3 = st.columns(3)
    with col1:
        game_filter = st.selectbox("游戏筛选", ["全部", "原神", "鸣潮", "Steam", "独立游戏"])
    with col2:
        source_filter = st.selectbox("来源筛选", ["全部", "HoYoLAB", "Steam", "游民星空", "3DM", "机核", "IGN", "PC Gamer"])
    with col3:
        days_filter = st.selectbox("时间范围", ["全部", "最近 3 天", "最近 7 天", "最近 30 天"], index=2)

    news_query = st.text_input("搜索关键词", placeholder="输入关键词或自然语言查询...")

    if news_query and st.button("搜索新闻", type="primary"):
        with st.spinner("检索中..."):
            try:
                from src.rag.retriever import search_news

                gf = None if game_filter == "全部" else game_filter
                sf = None if source_filter == "全部" else source_filter
                df_map = {"全部": None, "最近 3 天": 3, "最近 7 天": 7, "最近 30 天": 30}
                df = df_map.get(days_filter)

                docs = run_async_safe(search_news(news_query, k=10, source_filter=sf, game_filter=gf, days_filter=df))

                if docs:
                    st.subheader(f"找到 {len(docs)} 条相关新闻")
                    for doc in docs:
                        meta = doc.metadata
                        with st.container(border=True):
                            st.markdown(f"#### {meta.get('title', '无标题')}")
                            st.caption(
                                f"来源: {meta.get('source_name', '未知')} | "
                                f"日期: {meta.get('published_date', '未知')} | "
                                f"语言: {meta.get('language', '未知')}"
                            )
                            st.markdown(doc.page_content[:300] + ("..." if len(doc.page_content) > 300 else ""))
                            if meta.get("source_url"):
                                st.link_button("阅读原文", meta["source_url"])
                else:
                    st.info("未找到相关新闻，尝试修改搜索条件")
            except Exception as e:
                st.error(f"检索失败: {e}")
    elif not news_query:
        st.info("输入关键词后点击搜索")

with tab2:
    st.subheader("最新资讯")

    @st.cache_data(ttl=1800, show_spinner=False)
    def load_rss():
        try:
            from src.tools.rss_feed import RSSFetchAllTool
            tool = RSSFetchAllTool()
            return run_async_safe(tool._arun())
        except Exception:
            return None

    if st.button("刷新新闻"):
        st.cache_data.clear()
        st.rerun()

    articles = load_rss()
    if articles is None:
        st.info("RSS 新闻源暂不可用，请稍后重试")
    elif articles:
        for article in articles[:15]:
            with st.container(border=True):
                st.markdown(f"**{article.get('title', '无标题')}**")
                st.caption(
                    f"来源: {article.get('source_name', article.get('source', '未知'))} | "
                    f"{article.get('published', '未知')}"
                )
                if article.get("summary"):
                    st.markdown(article["summary"][:200])
                if article.get("link"):
                    st.link_button("阅读原文", article["link"])
    else:
        st.info("暂无最新资讯")
```

- [ ] **Step 2: 运行验证**

Tab1 搜索「原神」来源「HoYoLAB」时间「最近 7 天」。Tab2 RSS 正常加载或降级提示。

- [ ] **Step 3: 提交**

```bash
git add src/ui/_pages/news.py
git commit -m "feat: 新闻页改为 Tab 布局，筛选器实际生效，RSS 故障降级"
```

---

### Task D1: 对话页 — 侧边栏历史对话列表

**Files:**
- Modify: `src/ui/_pages/chat.py`
- Modify: `src/ui/session_state.py`
- Modify: `src/ui/app.py`

- [ ] **Step 1: 在 session_state 中增加历史管理支持**

在 `src/ui/session_state.py` 末尾添加：

```python
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
    st.session_state["chat_sessions"][sid] = {"title": "新对话", "messages": []}
    st.session_state["active_session_id"] = sid
    return sid


def get_active_messages() -> list[dict]:
    """获取当前活跃会话的消息列表"""
    init_chat_sessions()
    sid = st.session_state.get("active_session_id")
    if sid and sid in st.session_state["chat_sessions"]:
        return st.session_state["chat_sessions"][sid]["messages"]
    return []


def add_chat_message(role: str, content: str):
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

同时保留旧的 `init_session_state`, `run_async_safe`, `get_chat_history` 函数不变。

- [ ] **Step 2: 重写 chat.py 使用新的多会话系统**

完整替换 `src/ui/_pages/chat.py`：

```python
"""AI 对话页 —— 自然语言交互"""

import streamlit as st
from src.ui.session_state import (
    init_chat_sessions, create_chat_session, get_active_messages,
    add_chat_message, switch_session, run_async_safe
)

st.title("AI 对话")

st.caption("支持快捷指令: `/price 游戏名` `/recommend 游戏名` `/news 关键词` `/search 游戏名`")

init_chat_sessions()

# 确保至少有一个活跃会话
if not st.session_state.get("active_session_id") or not st.session_state["chat_sessions"]:
    create_chat_session()

history = get_active_messages()

# 显示当前会话历史消息
for msg in history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("输入你的问题..."):
    add_chat_message("user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)

    placeholder = st.empty()
    placeholder.info(":hourglass: 思考中，请稍候...")

    try:
        from src.agents.graph import chat
        response = run_async_safe(chat(prompt, history[:-1] if len(history) > 1 else None))
    except Exception as e:
        response = f"出错了: {str(e)}"

    placeholder.empty()
    with st.chat_message("assistant"):
        st.markdown(response)
    add_chat_message("assistant", response)

# ---------- 侧边栏：对话历史 ----------

with st.sidebar:
    st.subheader("对话历史")

    if st.button("+ 新对话", use_container_width=True):
        create_chat_session()
        st.rerun()

    st.divider()

    sessions = st.session_state.get("chat_sessions", {})
    active = st.session_state.get("active_session_id")

    for sid in list(sessions.keys()):
        session = sessions[sid]
        is_active = sid == active
        prefix = "▸ " if is_active else "  "
        title = session.get("title", "未命名对话")
        msg_count = len(session.get("messages", []))

        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(
                f"{prefix}{title} ({msg_count // 2}轮)",
                key=f"sess_{sid}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                switch_session(sid)
                st.rerun()
        with col2:
            if not is_active and st.button("🗑", key=f"del_{sid}", help="删除此对话"):
                del sessions[sid]
                if sid == active:
                    st.session_state["active_session_id"] = next(iter(sessions)) if sessions else None
                st.rerun()
```

- [ ] **Step 3: 更新 app.py**

在 `src/ui/app.py` 中：

```python
from src.ui.session_state import init_session_state, init_chat_sessions

init_session_state()
init_chat_sessions()
```

- [ ] **Step 4: 运行验证**

侧边栏显示「+ 新对话」和历史会话列表。新建多个对话、切换、删除均正常。

- [ ] **Step 5: 提交**

```bash
git add src/ui/_pages/chat.py src/ui/session_state.py src/ui/app.py
git commit -m "feat: 对话页支持多轮会话管理，侧边栏历史列表"
```

---

### Task D2: 创建统一 Loading 组件

**Files:**
- Create: `src/ui/components/_loading.py`

- [ ] **Step 1: 创建组件**

```python
"""统一 Loading 状态组件"""

import streamlit as st
from contextlib import contextmanager


@contextmanager
def show_loading(message: str = "加载中..."):
    """统一加载状态上下文管理器

    用法:
        with show_loading("搜索中..."):
            results = run_async_safe(search())
    """
    with st.spinner(message):
        yield
```

- [ ] **Step 2: 提交**

```bash
git add src/ui/components/_loading.py
git commit -m "feat: 添加统一 loading 状态组件"
```

---

### Task D3: 创建统一 Error 组件

**Files:**
- Create: `src/ui/components/_error.py`

- [ ] **Step 1: 创建组件**

```python
"""统一错误展示组件"""

import streamlit as st
from contextlib import contextmanager


@contextmanager
def show_error(fallback_message: str = "操作失败，请稍后重试"):
    """统一错误处理上下文管理器

    用法:
        with show_error("搜索失败"):
            results = fragile_operation()
    """
    try:
        yield
    except Exception as e:
        st.error(f"{fallback_message}: {e}")
```

- [ ] **Step 2: 提交**

```bash
git add src/ui/components/_error.py
git commit -m "feat: 添加统一错误展示组件"
```

---

### Task D4: 全局应用统一组件

**Files:**
- Modify: `src/ui/_pages/search.py`
- Modify: `src/ui/_pages/recommend.py`
- Modify: `src/ui/_pages/news.py`

- [ ] **Step 1: 各页应用 show_loading 和 show_error**

**search.py** — 搜索按钮包裹：
```python
from src.ui.components._loading import show_loading
from src.ui.components._error import show_error

if query and st.button("搜索", type="primary"):
    with show_error("搜索失败"):
        with show_loading("搜索中..."):
            # 原有搜索逻辑（plat_param / genre_param / tool._arun...）
            # 移除内层 try/except，保留 if results / else warning
```

**recommend.py** — 推荐按钮包裹：
```python
from src.ui.components._loading import show_loading
from src.ui.components._error import show_error

if st.button("推荐游戏", type="primary", disabled=not game_input):
    with show_error("推荐失败"):
        with show_loading("搜索推荐中..."):
            # 原有推荐逻辑
            # 移除内层 try/except
```

**news.py** — Tab1 搜索按钮包裹：
```python
from src.ui.components._loading import show_loading
from src.ui.components._error import show_error

if news_query and st.button("搜索新闻", type="primary"):
    with show_error("检索失败"):
        with show_loading("检索中..."):
            # 原有搜索逻辑
            # 移除内层 try/except
```

- [ ] **Step 2: 运行验证**

各页面正常操作，loading 状态和错误提示与之前一致。

- [ ] **Step 3: 提交**

```bash
git add src/ui/_pages/search.py src/ui/_pages/recommend.py src/ui/_pages/news.py
git commit -m "refactor: 全局应用统一 loading 和 error 组件"
```

---

## 验证清单

| # | 页面 | 验证项 | 预期 |
|---|------|--------|------|
| A1 | 首页 | 活跃监控数字 | 显示 DB watchlist 活跃计数 |
| A2 | 首页 | 待读告警数字 | 显示 DB price_alerts 未读计数 |
| A3 | 首页 | 新闻库数字 | 显示 ChromaDB 文档总数 |
| A4 | 首页 | 最低折扣 | 显示折扣百分比 + 游戏名 |
| A5 | 首页 | 热门游戏 | 显示 Steam 实时在线人数 |
| B1 | 搜索 | 筛选 PC+RPG | 结果只含 PC 平台 RPG |
| B2 | 搜索 | 查看详情 | 卡片内展开描述 + 评分 + 开发商 |
| B3 | 推荐 | 偏好 开放世界 | 匹配度高排前带 ⭐ |
| B4 | 推荐 | 展开详情 | 卡片内展开描述和标签 |
| C1 | 价格 | 三次刷新 | 无 WebSocket/AsyncIO 错误 |
| C2 | 价格 | 删除监控 | 弹出确认对话框 |
| C3 | 新闻 | 来源 HoYoLAB | 只返回 HoYoLAB 新闻 |
| C4 | 新闻 | 时间 最近 3 天 | 只返回 3 天内新闻 |
| C5 | 新闻 | RSS 故障 | 降级提示不报错 |
| D1 | 对话 | 多会话切换 | 侧边栏列表可切换 |
| D2 | 对话 | 删除非活跃 | 消失，活跃不受影响 |
| D3 | 全局 | loading spinner | 耗时操作显示 |
| D4 | 全局 | 搜索失败 | 统一 st.error 样式 |
