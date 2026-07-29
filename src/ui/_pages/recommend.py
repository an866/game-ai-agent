"""游戏推荐页"""

import streamlit as st
from src.ui.session_state import run_async_safe
from src.ui.components._loading import show_loading
from src.ui.components._error import show_error

st.title("游戏推荐")

st.markdown("输入你喜欢的游戏，AI 为你推荐相似的游戏")

# ── 加载用户画像 ──
sid = st.session_state.get("active_session_id")
user_profile = None
if sid:
    from src.agents.memory import ConversationMemory
    mem = ConversationMemory()
    user_profile = run_async_safe(mem.load_profile(sid))

game_input = st.text_input("游戏名称", placeholder="例如: 巫师3, 原神, 空洞骑士...")

col1, col2 = st.columns([1, 1])
with col1:
    genre_pref = st.multiselect("偏好类型（可选）", ["动作", "冒险", "RPG", "策略", "模拟", "独立", "开放世界", "魂系"])
with col2:
    platform_pref = st.selectbox("偏好平台（可选）", ["不限", "PC", "PlayStation", "Xbox", "Nintendo Switch"])

if st.button("推荐游戏", type="primary", disabled=not game_input):
    with show_error("推荐失败"):
        with show_loading("搜索推荐中..."):
            from src.tools.rawg import RAWGGameSearchTool, RAWGGameRecommendationsTool, RAWGGameDetailTool

            async def _run():
                # ── 注入用户画像 ──
                search_query = game_input
                if user_profile:
                    parts = []
                    if user_profile.get("favorite_genres"): parts.append(f"偏好类型: {user_profile['favorite_genres']}")
                    if user_profile.get("favorite_games"): parts.append(f"喜欢的游戏: {user_profile['favorite_games']}")
                    if user_profile.get("budget_range"): parts.append(f"预算: {user_profile['budget_range']}")
                    if parts:
                        search_query = "用户画像: " + "；".join(parts) + "。\n" + game_input

                search_tool = RAWGGameSearchTool()
                results = await search_tool._arun(search_query)
                recs = []
                game_name = None
                if results:
                    game_id = results[0]["id"]
                    game_name = results[0]["name"]
                    rec_tool = RAWGGameRecommendationsTool()
                    recs = await rec_tool._arun(game_id)

                    # 偏好匹配度排序
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
                st.success(f"基于 **{game_name}** 的推荐:")

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
