"""新闻聚合 Agent —— RAG 混合检索 + 多源聚合"""

import yaml
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from config.settings import get_settings
from src.tools.steam_api import SteamNewsTool, SteamSearchTool
from src.tools.hoyolab import GenshinNewsTool, GenshinEventsTool
from src.tools.rss_feed import RSSFetchAllTool
from src.rag.retriever import _format_docs

settings = get_settings()

config_path = Path(__file__).parent.parent.parent / "config" / "agents.yaml"
with open(config_path, encoding="utf-8") as f:
    prompts = yaml.safe_load(f)


def get_news_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=0.3,
    )


async def run_news(state: dict) -> dict:
    """新闻聚合 —— 多源检索 + LLM 摘要"""
    from src.rag.store import get_retriever

    messages = state.get("messages", [])
    user_input = messages[-1].content if messages else ""
    game_name = state.get("game_name", "")

    # 1. 向量检索
    retriever = get_retriever(k=5)
    if game_name:
        rag_docs = await retriever.ainvoke(f"{game_name} {user_input}")
    else:
        rag_docs = await retriever.ainvoke(user_input)

    # 2. 特定数据源查询（并行）
    results = {}
    try:
        if game_name:
            steam_search = SteamSearchTool()
            steam_results = await steam_search._arun(game_name)
            if steam_results:
                appid = steam_results[0]["appid"]
                news_tool = SteamNewsTool()
                results["steam_news"] = await news_tool._arun(appid)
    except Exception:
        results["steam_news"] = []

    try:
        if "原神" in (game_name + user_input):
            genshin_tool = GenshinNewsTool()
            results["genshin_news"] = await genshin_tool._arun(5)
            events_tool = GenshinEventsTool()
            results["genshin_events"] = await events_tool._arun()
    except Exception:
        results["genshin_news"] = []

    try:
        rss_tool = RSSFetchAllTool()
        results["rss_news"] = await rss_tool._arun()
    except Exception:
        results["rss_news"] = []

    # 3. LLM 生成最终回复
    llm = get_news_llm()
    system_prompt = prompts["news"]["system_prompt"]

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt + "\n\nRAG 检索结果:\n{rag_context}\n\nAPI 直查结果:\n{api_results}"),
        ("human", "{question}"),
    ])

    chain = prompt | llm | StrOutputParser()

    response = await chain.ainvoke({
        "rag_context": _format_docs(rag_docs),
        "api_results": str(results),
        "question": user_input,
    })

    return {
        "news_result": {"rag_docs": rag_docs, "api_results": results},
        "final_response": response,
    }
