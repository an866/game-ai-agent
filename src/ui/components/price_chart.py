"""价格走势图组件"""

import streamlit as st
import pandas as pd


def render_price_chart(price_history: list[dict], game_name: str = ""):
    """渲染价格走势折线图"""
    if not price_history:
        st.info("暂无历史价格数据")
        return

    st.subheader(f"价格走势 - {game_name}" if game_name else "价格走势")

    # 准备数据
    rows = []
    for entry in price_history:
        rows.append({
            "shop": entry.get("shop", entry.get("store_name", "未知商店")),
            "price": float(entry.get("price_new", entry.get("price", 0))),
            "date": entry.get("date", entry.get("timestamp", "")),
        })

    df = pd.DataFrame(rows)

    if df.empty:
        st.info("暂无数据")
        return

    # 用 Altair 画图（如果数据中有日期）
    try:
        import altair as alt
        df["date"] = pd.to_datetime(df["date"])

        chart = (
            alt.Chart(df)
            .mark_line(point=True)
            .encode(
                x=alt.X("date:T", title="日期"),
                y=alt.Y("price:Q", title="价格 (¥)"),
                color=alt.Color("shop:N", title="商店"),
                tooltip=["shop", "price", "date"],
            )
            .properties(height=300)
        )
        st.altair_chart(chart, use_container_width=True)
    except Exception:
        # 降级：用 st.line_chart
        st.line_chart(df.set_index("shop")["price"])


def render_price_table(prices: list[dict]):
    """渲染价格对比表"""
    if not prices:
        st.info("暂无价格数据")
        return

    rows = []
    for p in prices:
        rows.append({
            "商店": p.get("shop", p.get("store_name", "未知商店")),
            "当前价": f"¥{float(p.get('price_new', p.get('sale_price', 0))):.2f}",
            "原价": f"¥{float(p.get('price_old', p.get('normal_price', 0))):.2f}",
            "折扣": f"{float(p.get('price_cut', p.get('discount_percent', 0)))}%",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
