"""新闻抓取定时任务"""

from loguru import logger
from src.tools.rss_feed import fetch_all_rss_as_documents
from src.rag.splitter import split_documents
from src.rag.retriever import insert_documents


async def fetch_and_index_news():
    """拉取 RSS 新闻 → 分块 → 写入 ChromaDB"""
    try:
        docs = await fetch_all_rss_as_documents()
        if not docs:
            logger.info("新闻抓取: 无新文章")
            return

        logger.info(f"新闻抓取: 原始 {len(docs)} 篇文章")

        chunks = split_documents(docs)
        logger.info(f"新闻分块: {len(chunks)} 个块")

        inserted = insert_documents(chunks)
        logger.info(f"新闻入库: {inserted} 个新块 (去重后)")
    except Exception as e:
        logger.error(f"新闻抓取失败: {e}")
