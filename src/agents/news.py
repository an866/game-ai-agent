"""新闻聚合 Agent —— RAG 混合检索 + 多源聚合 + 联网兜底"""

import asyncio

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

# 单源检索硬超时（秒）——任一源拖死都会让用户以为「一直不回答」
RAG_TIMEOUT = 8.0
STEAM_TIMEOUT = 12.0
RSS_TIMEOUT = 20.0
WEB_TIMEOUT = 12.0


def get_news_llm() -> ChatOpenAI:
    return get_llm("news")


async def run_news(state: dict) -> dict:
    """新闻聚合 —— 多源检索并行 + 超时降级 + 联网兜底"""

    messages = state.get("messages", [])
    user_input = messages[-1].content if messages else ""
    game_name = state.get("game_name", "")

    async def _fetch_rag():
        try:
            docs = await asyncio.wait_for(
                search_news(f"{game_name} {user_input}" if game_name else user_input, k=5),
                timeout=RAG_TIMEOUT,
            )
            return docs
        except Exception as exc:
            logger.warning(f"RAG 检索超时/失败，跳过: {exc}")
            return []

    async def _fetch_steam():
        if not game_name:
            return None
        try:
            # 中文名搜不到时补英文名（鸣潮 → Wuthering Waves）
            names = [game_name]
            if game_name == "鸣潮":
                names.append("Wuthering Waves")
            elif game_name == "原神":
                names.append("Genshin Impact")
            appid = None
            for name in names:
                steam_results = await asyncio.wait_for(
                    SteamSearchTool()._arun(name), timeout=STEAM_TIMEOUT
                )
                if steam_results:
                    appid = steam_results[0]["appid"]
                    break
            if appid:
                return await asyncio.wait_for(
                    SteamNewsTool()._arun(appid), timeout=STEAM_TIMEOUT
                )
        except Exception as exc:
            logger.warning(f"Steam 新闻获取失败: {exc}")
        return []

    async def _fetch_genshin():
        if "原神" not in (game_name + user_input):
            return None
        try:
            news = await GenshinNewsTool()._arun(5)
            events = await GenshinEventsTool()._arun()
            return {"news": news, "events": events}
        except Exception as exc:
            logger.warning(f"原神新闻获取失败: {exc}")
            return {"news": [], "events": []}

    async def _fetch_rss():
        try:
            return await asyncio.wait_for(RSSFetchAllTool()._arun(), timeout=RSS_TIMEOUT)
        except Exception as exc:
            logger.warning(f"RSS 新闻获取失败: {exc}")
            return []

    async def _fetch_web():
        """内置源没有该游戏时用联网搜索兜底（鸣潮/独立游戏等）"""
        q = f"{game_name} {user_input} 最新活动 公告".strip() if game_name else f"{user_input} 最新"
        try:
            from src.tools.web_search import search_web
            return await asyncio.wait_for(search_web(q, max_results=5), timeout=WEB_TIMEOUT)
        except Exception as exc:
            logger.warning(f"新闻联网兜底失败: {exc}")
            return []

    rag_docs, steam_news, genshin_pack, rss_news, web_hits = await asyncio.gather(
        _fetch_rag(), _fetch_steam(), _fetch_genshin(), _fetch_rss(), _fetch_web()
    )

    results: dict = {"rss_news": rss_news, "web_search": web_hits}
    if steam_news is not None:
        results["steam_news"] = steam_news
    if genshin_pack is not None:
        results["genshin_news"] = genshin_pack["news"]
        results["genshin_events"] = genshin_pack["events"]

    # 3. LLM 生成最终回复
    llm = get_news_llm()
    system_prompt = prompts["news"]["system_prompt"]

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt + "\n\nRAG 检索结果:\n{rag_context}\n\nAPI 直查结果:\n{api_results}"),
        ("human", "{question}"),
    ])

    chain = prompt | llm | StrOutputParser()

    try:
        response = await chain.ainvoke({
            "rag_context": _format_docs(rag_docs),
            "api_results": str(results),
            "question": user_input,
        })
    except Exception as exc:
        logger.exception("新闻 LLM 摘要失败")
        response = f"新闻服务暂时不可用（{type(exc).__name__}），请稍后再试。"

    return {
        "news_result": {"rag_docs": rag_docs, "api_results": results},
        "final_response": response,
    }
