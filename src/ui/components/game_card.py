"""游戏卡片组件 —— 搜索结果与推荐列表共用

注意：Streamlit 的 st.markdown 会把 HTML 里的 `|` 当表格分隔符，
复杂嵌套 HTML 也常被降级成代码块。卡片改用原生 columns/caption 拼装。
"""

import html as _html

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


def _price_badge_text(game: dict) -> str:
    discount = game.get("discount_percent")
    sale = game.get("sale_price")
    if discount:
        return f"-{discount:.0f}%"
    if sale:
        return f"¥{sale}"
    return ""


def render_game_card(
    game: dict,
    *,
    show_detail: bool = True,
    rank: int | None = None,
    match_badge: str = "",
) -> None:
    """游戏卡片：封面 + 标题/元信息（原生 Streamlit，避免 HTML 被当代码）"""
    name = _html.escape(str(game.get("name") or "未知游戏"))
    title = f"{rank}. {name}" if rank else name
    source = game.get("source") or "rawg"
    badge = _price_badge_text(game)
    rating = game.get("rating")
    metacritic = game.get("metacritic")
    released = game.get("released") or "-"
    genres = game.get("genres") or []
    platforms = game.get("platforms") or []
    snippet = game.get("snippet") or ""
    image = game.get("background_image")

    # border=True 在 Streamlit ≥1.29 可用；失败则退化为无边框容器
    try:
        card = st.container(border=True)
    except TypeError:
        card = st.container()

    with card:
        col_img, col_info = st.columns([1, 3], gap="medium")
        with col_img:
            if image:
                st.image(image, use_container_width=True)
        with col_info:
            head = title
            if match_badge:
                head += f" {match_badge}"
            if badge:
                head += f" · {badge}"
            if source != "rawg":
                head += f" · via {source}"
            st.markdown(f"**{head}**")
            meta_parts = []
            if rating is not None:
                meta_parts.append(f"评分 {float(rating):.1f}/5")
            if metacritic:
                meta_parts.append(f"Metacritic {metacritic}")
            if meta_parts:
                st.caption(" · ".join(meta_parts))
            # 空字段不占行（web 轻量结果尤其）
            if released and released != "-":
                st.caption(f"发售日 {released}")
            if genres:
                st.caption(f"类型 {', '.join(genres)}")
            if platforms:
                st.caption(f"平台 {', '.join(platforms[:5])}")
            if snippet:
                st.caption(snippet)

        can_detail = (
            show_detail
            and source == "rawg"
            and game.get("id") not in (None, "")
        )
        if can_detail:
            with st.expander(f"查看 {game.get('name', '')} 详情"):
                render_game_detail(game)
