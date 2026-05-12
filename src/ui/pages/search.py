"""游戏搜索页"""

import asyncio
import streamlit as st

st.title("游戏搜索")

query = st.text_input("输入游戏名称", placeholder="例如: 艾尔登法环, 原神, 黑神话悟空...")

col1, col2 = st.columns([1, 3])

with col1:
    platform_filter = st.multiselect("平台", ["PC", "PlayStation", "Xbox", "Nintendo Switch", "iOS", "Android"])
    genre_filter = st.multiselect("类型", ["动作", "冒险", "RPG", "策略", "模拟", "体育", "独立", "大型多人在线"])

with col2:
    if query and st.button("搜索", type="primary"):
        with st.spinner("搜索中..."):
            try:
                from src.tools.rawg import RAWGGameSearchTool
                tool = RAWGGameSearchTool()
                results = asyncio.run(tool._arun(query))

                if results:
                    st.session_state["search_results"] = results
                else:
                    st.warning("未找到匹配的游戏")
            except Exception as e:
                st.error(f"搜索失败: {e}")

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
                    if st.button("查看详情", key=f"detail_{game['id']}"):
                        st.switch_page("src/ui/pages/search.py")
    elif not query:
        st.info("输入游戏名称开始搜索")
