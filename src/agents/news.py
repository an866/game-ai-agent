"""新闻聚合 Agent —— RAG 混合检索 + 多源聚合"""

from config.loader import get_agents_config
from loguru import logger
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from src.llm import get_llm

from config.settings import get_settings
from src.tools.steam_api import SteamNewsTool, SteamSearchTool
from src.tools.hoyolab import GenshinNewsTool, GenshinEventsTool
from src.tools.rss_feed import RSSFetchAllTool
from src.rag.retriever import _format_docs, search_news

settings = get_settings()

prompts = get_agents_config()


def get_news_llm() -> ChatOpenAI:
    return get_llm("news")


async def run_news(state: dict) -> dict:
    """新闻聚合 —— 多源检索 + LLM 摘要"""
    

    messages = state.get("messages", [])
    user_input = messages[-1].content if messages else ""
    game_name = state.get("game_name", "")

    # 1. 向量检索
    if game_name:
        rag_docs = await search_news(f"{game_name} {user_input}", k=5)
    else:
        rag_docs = await search_news(user_input, k=5)

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
    except Exception as exc:
        logger.warning(f"Steam 新闻获取失败: {exc}")
        results["steam_news"] = []

    try:
        if "原神" in (game_name + user_input):
            genshin_tool = GenshinNewsTool()
            results["genshin_news"] = await genshin_tool._arun(5)
            events_tool = GenshinEventsTool()
            results["genshin_events"] = await events_tool._arun()
    except Exception as exc:
        logger.warning(f"原神新闻获取失败: {exc}")
        results["genshin_news"] = []

    try:
        rss_tool = RSSFetchAllTool()
        results["rss_news"] = await rss_tool._arun()
    except Exception as exc:
        logger.warning(f"RSS 新闻获取失败: {exc}")
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
