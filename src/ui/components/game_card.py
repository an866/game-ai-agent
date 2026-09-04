"""游戏卡片组件 —— 搜索结果与推荐列表共用（V2 视觉：渐变描边 + 折扣标签）"""

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


def _discount_badge(game: dict) -> str:
    """折扣/价格标签 HTML（优先使用 cheapshark 的 discount_percent 字段）"""
    discount = game.get("discount_percent")
    sale = game.get("sale_price")
    if discount:
        return f'<span style="background: var(--ok); color: var(--bg); border-radius: 6px; padding: 2px 6px; font-size: 12px; font-weight: 700;">-{discount:.0f}%</span>'
    if sale:
        return f'<span style="color: var(--ok); font-weight: 600;">¥{sale}</span>'
    if game.get("rating"):
        return f'<span style="color: var(--text-dim);">⭐ {game["rating"]}/5</span>'
    return ""


def render_game_card(
    game: dict,
    *,
    show_detail: bool = True,
    rank: int | None = None,
    match_badge: str = "",
) -> None:
    """游戏卡片：渐变描边卡片 + 左图右信息 + 可选详情展开。"""
    border_style = (
        "border: 1px solid transparent;"
        "background: linear-gradient(var(--panel), var(--panel)) padding-box,"
        "            linear-gradient(135deg, var(--accent1), var(--accent2)) border-box;"
    )
    with st.container():
        st.markdown(
            f"""<div style="{border_style} border-radius: var(--radius); padding: 12px;">
              <div style="display:flex; gap:12px;">
                <div style="flex:1; min-width:90px; max-width:180px;">{'<img src="' + game['background_image'] + '" style="width:100%; border-radius:8px;">' if game.get('background_image') else ''}</div>
                <div style="flex:2;">
                  <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                    <span style="color:var(--text); font-size:16px; font-weight:700;">{(str(rank) + '. ' if rank else '') + game['name']}{match_badge}</span>
                    {_discount_badge(game)}
                  </div>
                  {('<div style="color:var(--text-dim); font-size:13px;">评分: <b>%.1f</b>/5 | Metacritic: %s</div>' % (game['rating'], game.get('metacritic') or '暂无')) if game.get('rating') else ''}
                  <div style="color:var(--text); font-size:13px;">发售日: {game.get('released', '-')}</div>
                  <div style="color:var(--text-dim); font-size:13px;">类型: {', '.join(game.get('genres', [])) or '-'}</div>
                  {('<div style="color:var(--text-dim); font-size:13px;">平台: ' + ', '.join(game['platforms'][:5]) + '</div>') if game.get('platforms') else ''}
                </div>
              </div>
            </div>""",
            unsafe_allow_html=True,
        )
        if show_detail:
            with st.expander(f"查看 {game['name']} 详情"):
                render_game_detail(game)