"""新闻文档加载器 —— RSS 拉取 + 网页全文提取"""

from langchain_core.documents import Document
from langchain_community.document_loaders import RSSFeedLoader, WebBaseLoader
from loguru import logger


def load_from_rss(urls: list[str]) -> list[Document]:
    """从 RSS URL 列表加载文章标题和摘要"""
    loader = RSSFeedLoader(urls=urls)
    docs = loader.load()
    logger.info(f"RSS 加载: {len(docs)} 篇文章")
    return docs


def load_full_text(url: str) -> Document | None:
    """抓取单篇文章全文"""
    try:
        loader = WebBaseLoader(url)
        docs = loader.load()
        return docs[0] if docs else None
    except Exception as e:
        logger.warning(f"全文抓取失败 [{url}]: {e}")
        return None
