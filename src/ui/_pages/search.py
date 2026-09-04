"""游戏搜索页"""

import streamlit as st
from src.ui.session_state import run_async_safe
from src.ui.components._loading import show_loading
from src.ui.components._error import show_error
from src.ui.components.game_card import render_game_card

st.title("游戏搜索")

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

query = st.text_input("输入游戏名称", placeholder="例如: 艾尔登法环, 原神, 黑神话悟空...")

col1, col2 = st.columns([1, 3])

with col1:
    platform_filter = st.multiselect("平台", ["PC", "PlayStation", "Xbox", "Nintendo Switch", "iOS", "Android"])
    genre_filter = st.multiselect("类型", ["动作", "冒险", "RPG", "策略", "模拟", "体育", "独立", "大型多人在线"])

with col2:
    if query and st.button("搜索", type="primary"):
        with show_error("搜索失败"):
            with show_loading("搜索中..."):
                plat_param = ",".join(PLATFORM_MAP[p] for p in platform_filter) if platform_filter else None
                genre_param = ",".join(GENRE_MAP[g] for g in genre_filter) if genre_filter else None

                from src.tools.rawg import RAWGGameSearchTool
                tool = RAWGGameSearchTool()
                results = run_async_safe(tool._arun(
                    query,
                    platforms=plat_param,
                    genres=genre_param,
                ))

                if results:
                    st.session_state["search_results"] = results
                else:
                    st.warning("未找到匹配的游戏，尝试缩短关键词或减少筛选条件")

    results = st.session_state.get("search_results")
    if results:
        st.subheader(f"找到 {len(results)} 个结果")
        for game in results:
            render_game_card(game)
    elif not query:
        st.info("输入游戏名称开始搜索")
