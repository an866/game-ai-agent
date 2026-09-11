"""游戏搜索面板（迁移自 _pages/search.py）—— 查询 + 平台/类型筛选 + 结果流

结果与筛选持久化在 ui_state panel_state["search"]：切走面板再回来不丢。
数据访问一律走 RAWGGameSearchTool._arun（缓存/重试由 GameDataTool 提供）+ run_async_safe。
"""

import streamlit as st

from src.ui import ui_state
from src.ui.session_state import run_async_safe
from src.ui.components._loading import show_loading
from src.ui.components._error import show_error
from src.ui.components.game_card import render_game_card

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


def build_filter_params(platforms: list[str], genres: list[str]) -> dict:
    """平台/类型显示名 → RAWG API 参数（逗号分隔 ID slug）"""
    params: dict = {}
    if platforms:
        params["platforms"] = ",".join(PLATFORM_MAP[p] for p in platforms)
    if genres:
        params["genres"] = ",".join(GENRE_MAP[g] for g in genres)
    return params


def build_query_from_state(state: dict) -> str:
    return state.get("query", "")


def render_search_panel() -> None:
    """搜索面板：查询框 + 筛选胶囊 + 结果卡流 + 返回对话"""
    state = ui_state.get_panel_state("search")

    st.markdown("### 游戏搜索")
    query = st.text_input("游戏名称", value=state.get("query", ""),
                          placeholder="例如: 艾尔登法环, 原神, 黑神话悟空...")

    col1, col2 = st.columns(2)
    with col1:
        platform_filter = st.multiselect("平台", list(PLATFORM_MAP.keys()),
                                         default=state.get("platforms", []))
    with col2:
        genre_filter = st.multiselect("类型", list(GENRE_MAP.keys()),
                                      default=state.get("genres", []))

    col3, col4 = st.columns([1, 4])
    with col3:
        # 空查询不触发（保持 _pages/search.py 语义：无查询不调 API）
        if st.button("🔍 搜索", type="primary", use_container_width=True) and query:
            ui_state.set_panel_state("search", {"query": query, "platforms": platform_filter,
                                                "genres": genre_filter, "result_state": "loading"})
            st.rerun()
    with col4:
        if st.button("← 返回对话", key="back_search", use_container_width=True):
            ui_state.set_tab("chat")
            st.rerun()

    if state.get("result_state") == "loading":
        with show_error("搜索失败"):
            with show_loading("搜索中..."):
                from src.services.game_lookup import search_games
                params = build_filter_params(state.get("platforms", []), state.get("genres", []))
                results = run_async_safe(search_games(
                    state.get("query", ""),
                    platforms=params.get("platforms"),
                    genres=params.get("genres"),
                ))
                ui_state.set_panel_state("search", {**state, "results": results,
                                                    "result_state": "done"})
                st.rerun()

    results = state.get("results") or []
    if results:
        st.subheader(f"找到 {len(results)} 个结果")
        for game in results:
            render_game_card(game)
    elif not query and not results:
        st.info("输入游戏名称开始搜索")
    elif state.get("result_state") == "done":
        st.info("未找到匹配的游戏，尝试调整筛选条件")