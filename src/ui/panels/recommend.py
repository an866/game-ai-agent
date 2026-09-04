"""推荐面板 —— 画像注入 + 推荐卡流（迁移自 _pages/recommend.py）

画像标签与搜索词拼接（profile_label / build_search_query）与源页一致；
结果仅在按钮触发的当次运行内渲染，不落 panel_state（源页面同样不持久化，切走即失，保持原语义）。
数据访问：ChatService.load_profile（DB 不可用自动降级 None）+ RAWG 工具 _arun（缓存/重试），均经 run_async_safe。
"""

import streamlit as st

from src.services.chat_service import ChatService, build_profile_text
from src.ui import ui_state
from src.ui.session_state import run_async_safe
from src.ui.components._loading import show_loading
from src.ui.components._error import show_error
from src.ui.components.game_card import render_game_card


def profile_label(profile: dict | None) -> str | None:
    """画像存在时返回提示文案，否则 None"""
    text = build_profile_text(profile or {})
    return text if text else None


def build_search_query(game_input: str, profile: dict | None,
                       genre_pref: list[str]) -> str:
    """画像拼接进搜索词（无画像则原样返回）"""
    text = build_profile_text(profile or {})
    return f"{text}\n{game_input}" if text else game_input


def render_recommend_panel() -> None:
    """推荐面板：返回对话 + 画像标签 + 输入/筛选 + 推荐卡流"""
    st.markdown("### 游戏推荐")
    if st.button("← 返回对话", key="back_recommend", use_container_width=True):
        ui_state.set_tab("chat")
        st.rerun()

    sid = st.session_state.get("active_session_id")
    user_profile = None
    if sid:
        try:
            user_profile = run_async_safe(ChatService().load_profile(sid))
        except Exception:
            user_profile = None
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