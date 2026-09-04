"""游戏推荐页"""

import streamlit as st
from src.ui.session_state import run_async_safe
from src.ui.components._loading import show_loading
from src.ui.components._error import show_error
from src.ui.components.game_card import render_game_card
from src.services.chat_service import ChatService, build_profile_text

st.title("游戏推荐")

st.markdown("输入你喜欢的游戏，AI 为你推荐相似的游戏")

# ── 加载用户画像 ──
sid = st.session_state.get("active_session_id")
user_profile = None
if sid:
    mem = ChatService()
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
            from src.tools.rawg import RAWGGameSearchTool, RAWGGameRecommendationsTool

            async def _run():
                # ── 注入用户画像 ──
                profile_text = build_profile_text(user_profile or {})
                search_query = f"{profile_text}\n{game_input}" if profile_text else game_input

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
                        match_badge = ""
                        if rec.get("_match_score", 0) > 0:
                            match_badge = f" 🎯匹配度: {'⭐' * min(rec['_match_score'], 3)}"
                        render_game_card(rec, rank=i + 1, match_badge=match_badge)
                else:
                    st.info("暂无推荐数据，试试搜索其他游戏")
