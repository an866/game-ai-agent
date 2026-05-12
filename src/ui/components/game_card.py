"""游戏卡片组件"""

import streamlit as st


def render_game_card(game: dict):
    """渲染单张游戏卡片"""
    with st.container(border=True):
        col1, col2 = st.columns([1, 2])
        with col1:
            if game.get("background_image"):
                st.image(game["background_image"], use_container_width=True)
            elif game.get("thumb"):
                st.image(game["thumb"], use_container_width=True)
        with col2:
            st.markdown(f"### {game.get('name', game.get('title', '未知游戏'))}")
            if game.get("rating"):
                stars = "★" * int(float(game["rating"]))
                st.markdown(f"评分: {stars} {game['rating']}")
            if game.get("released"):
                st.caption(f"发售: {game['released']}")
            if game.get("genres"):
                st.caption(f"类型: {', '.join(game['genres'])}")
            if game.get("sale_price"):
                st.markdown(
                    f"~~¥{game.get('normal_price', 0)}~~ → **¥{game['sale_price']}** "
                    f"(-{game.get('discount_percent', 0)}%)"
                )


def render_game_card_grid(games: list[dict], columns: int = 3):
    """渲染游戏卡片网格"""
    cols = st.columns(columns)
    for i, game in enumerate(games):
        with cols[i % columns]:
            render_game_card(game)
