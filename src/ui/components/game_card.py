"""游戏卡片组件 —— 搜索结果与推荐列表共用"""

import streamlit as st
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
    except Exception:
        st.info("详情加载失败")


def render_game_card(
    game: dict,
    *,
    show_detail: bool = True,
    rank: int | None = None,
    match_badge: str = "",
) -> None:
    """游戏卡片：左图右信息 + 可选详情展开。

    match_badge: 偏好匹配徽标文本（如 " 🎯匹配度: ⭐⭐"）
    """
    with st.container(border=True):
        game_col1, game_col2 = st.columns([1, 3])
        with game_col1:
            if game.get("background_image"):
                st.image(game["background_image"], use_container_width=True)
        with game_col2:
            title = f"{rank}. {game['name']}" if rank else game["name"]
            title += match_badge
            st.markdown(f"### {title}")
            if game.get("rating"):
                st.markdown(f"评分: **{game['rating']}/5** | Metacritic: {game.get('metacritic', '暂无')}")
            if game.get("released"):
                st.markdown(f"发售日: {game['released']}")
            if game.get("genres"):
                st.markdown(f"类型: {', '.join(game['genres'])}")
            if game.get("platforms"):
                st.markdown(f"平台: {', '.join(game['platforms'][:5])}")
        if show_detail:
            with st.expander(f"查看 {game['name']} 详情"):
                render_game_detail(game)