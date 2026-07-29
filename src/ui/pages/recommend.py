"""游戏推荐页"""

import asyncio
import streamlit as st

st.title("游戏推荐")

st.markdown("输入你喜欢的游戏，AI 为你推荐相似的游戏")

# ── 加载用户画像 ──
from src.agents.memory import ConversationMemory
from src.ui.session_state import run_async_safe
mem = ConversationMemory()
user_profile = run_async_safe(mem.load_profile("default"))

game_input = st.text_input("游戏名称", placeholder="例如: 巫师3, 原神, 空洞骑士...")

col1, col2 = st.columns([1, 1])
with col1:
    genre_pref = st.multiselect("偏好类型（可选）", ["动作", "冒险", "RPG", "策略", "模拟", "独立", "开放世界", "魂系"])
with col2:
    platform_pref = st.selectbox("偏好平台（可选）", ["不限", "PC", "PlayStation", "Xbox", "Nintendo Switch"])

if st.button("推荐游戏", type="primary", disabled=not game_input):
    with st.spinner("AI 正在为你挑选游戏..."):
        try:
            from src.tools.rawg import RAWGGameSearchTool, RAWGGameRecommendationsTool

            search_tool = RAWGGameSearchTool()
            # ── 注入用户画像 ──
            search_query = game_input
            if user_profile:
                parts = []
                if user_profile.get("favorite_genres"): parts.append(f"偏好类型: {user_profile['favorite_genres']}")
                if user_profile.get("favorite_games"): parts.append(f"喜欢的游戏: {user_profile['favorite_games']}")
                if user_profile.get("budget_range"): parts.append(f"预算: {user_profile['budget_range']}")
                if parts:
                    search_query = "用户画像: " + "；".join(parts) + "。\n" + game_input
            results = await search_tool._arun(search_query)

            if not results:
                st.warning(f"未找到 '{game_input}' 的相关信息")
            else:
                game_id = results[0]["id"]
                game_name = results[0]["name"]

                st.success(f"基于 **{game_name}** 的推荐:")

                rec_tool = RAWGGameRecommendationsTool()
                recs = await rec_tool._arun(game_id)

                if recs:
                    for i, rec in enumerate(recs):
                        with st.container(border=True):
                            r_col1, r_col2 = st.columns([1, 3])
                            with r_col1:
                                if rec.get("background_image"):
                                    st.image(rec["background_image"], use_container_width=True)
                            with r_col2:
                                st.markdown(f"### {i+1}. {rec['name']}")
                                if rec.get("rating"):
                                    st.markdown(f"评分: {rec['rating']}/5")
                                if rec.get("released"):
                                    st.markdown(f"发售日: {rec['released']}")
                                if rec.get("genres"):
                                    st.markdown(f"类型: {', '.join(rec['genres'])}")
                else:
                    st.info("暂无推荐数据")
        except Exception as e:
            st.error(f"推荐失败: {e}")
