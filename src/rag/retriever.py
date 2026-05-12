"""新闻检索器 —— 支持语义搜索和混合检索"""

from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda
from src.rag.store import get_retriever, get_vector_store


async def search_news(
    query: str,
    k: int = 5,
    game_filter: str | None = None,
    source_filter: str | None = None,
) -> list[Document]:
    """搜索新闻 —— 语义检索 + 可选过滤"""
    retriever = get_retriever(k=k, fetch_k=20)

    search_kwargs = {"k": k, "fetch_k": 20}

    filters = {}
    if game_filter:
        filters["game_tags"] = game_filter
    if source_filter:
        filters["source_name"] = source_filter
    if filters:
        search_kwargs["filter"] = filters

    docs = await retriever.ainvoke(query)
    return docs


def build_rag_chain(llm):
    """构建 RAG 链：检索 → 上下文注入 → LLM 生成"""
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnablePassthrough
    from langchain_core.output_parsers import StrOutputParser

    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一个游戏资讯专家。根据以下检索到的新闻内容回答用户问题。
如果新闻内容不足以回答，请如实说明。
按时间倒序排列，标注每条新闻的来源和日期。

检索到的新闻:
{context}

用户问题: {question}"""),
    ])

    retriever = get_retriever(k=5)

    chain = (
        {"context": retriever | _format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    return chain


def _format_docs(docs: list[Document]) -> str:
    """格式化检索到的文档为上下文字符串"""
    formatted = []
    for doc in docs:
        meta = doc.metadata
        source = meta.get("source_name", meta.get("source", "Unknown"))
        date = meta.get("published_date", "Unknown")
        title = meta.get("title", "")
        formatted.append(
            f"---\n"
            f"标题: {title}\n"
            f"来源: {source} | 日期: {date}\n"
            f"内容: {doc.page_content[:500]}\n"
        )
    return "\n".join(formatted)


def insert_documents(docs: list[Document]):
    """向向量库批量插入文档（带去重）"""
    store = get_vector_store()
    existing_urls = _get_existing_urls()
    new_docs = [
        doc for doc in docs
        if doc.metadata.get("source_url") not in existing_urls
    ]
    if new_docs:
        store.add_documents(new_docs)
        return len(new_docs)
    return 0


def _get_existing_urls() -> set:
    """获取向量库中已有的 URL（用于去重）"""
    store = get_vector_store()
    try:
        results = store.get()
        urls = {
            meta.get("source_url", "")
            for meta in results.get("metadatas", [])
            if meta
        }
        return urls
    except Exception:
        return set()


def delete_old_documents(days: int = 90):
    """清理超过指定天数的旧文档"""
    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    store = get_vector_store()
    try:
        results = store.get()
        ids_to_delete = []
        for doc_id, meta in zip(results.get("ids", []), results.get("metadatas", [])):
            if meta and meta.get("published_date", "") < cutoff:
                ids_to_delete.append(doc_id)
        if ids_to_delete:
            store.delete(ids=ids_to_delete)
            return len(ids_to_delete)
    except Exception:
        pass
    return 0
