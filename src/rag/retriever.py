"""新闻检索器 —— 支持语义搜索和混合检索"""

from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda
from src.rag.store import get_retriever, get_vector_store


def _parse_rss_date(date_str: str) -> str:
    """将 RSS 日期字符串转为 ISO 格式，用于 ChromaDB 元数据过滤。
    解析失败时返回原始字符串。"""
    if not date_str:
        return ""
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.isoformat()
    except (ValueError, TypeError):
        return date_str


async def search_news(
    query: str,
    k: int = 5,
    source_filter: str | None = None,
    game_filter: str | None = None,
    days_filter: int | None = None,
) -> list[Document]:
    """搜索新闻 —— MMR 语义检索 + 可选来源/游戏/时间过滤"""
    from src.rag.store import get_retriever, get_vector_store
    from datetime import datetime, timedelta

    filter_conditions: list[dict] = []

    if source_filter:
        filter_conditions.append({"source_name": source_filter})
    if game_filter:
        filter_conditions.append({"game_name": game_filter})
    if days_filter:
        cutoff = (datetime.now() - timedelta(days=days_filter)).isoformat()
        filter_conditions.append({"published_iso": {"$gte": cutoff}})

    if filter_conditions:
        chroma_filter = (
            filter_conditions[0]
            if len(filter_conditions) == 1
            else {"$and": filter_conditions}
        )
        retriever = get_vector_store().as_retriever(
            search_type="mmr",
            search_kwargs={"k": k, "fetch_k": 20, "filter": chroma_filter},
        )
    else:
        retriever = get_retriever(k=k, fetch_k=20)

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
    """向向量库批量插入文档（按 source_url 去重）"""
    store = get_vector_store()
    urls = [doc.metadata.get("source_url", "") for doc in docs if doc.metadata.get("source_url")]
    existing_urls = _get_existing_urls(urls)
    new_docs = [
        doc for doc in docs
        if doc.metadata.get("source_url") not in existing_urls
    ]
    if new_docs:
        store.add_documents(new_docs)
        return len(new_docs)
    return 0


def _get_existing_urls(candidate_urls: list[str]) -> set:
    """查询向量库中已存在的 URL（使用元数据过滤，避免全量加载）"""
    if not candidate_urls:
        return set()
    store = get_vector_store()
    try:
        result = store.get(where={"source_url": {"$in": candidate_urls}})
        return {
            meta.get("source_url", "")
            for meta in (result.get("metadatas") or [])
            if meta
        }
    except Exception:
        return set()


def delete_old_documents(days: int = 90):
    """清理超过指定天数的旧文档。
    使用 ISO 格式的 published_iso 元数据字段进行过滤。"""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    store = get_vector_store()
    try:
        # 先用 metadata filter 找出到期文档（需要 published_iso 字段支持）
        try:
            result = store.get(where={"published_iso": {"$lt": cutoff}})
        except Exception:
            # ChromaDB 的 $lt 在某些版本对字符串比较不稳定，回退到全量获取
            result = store.get()

        ids_to_delete = []
        for doc_id, meta in zip(result.get("ids", []), result.get("metadatas", [])):
            if not meta:
                continue
            iso_date = meta.get("published_iso", "")
            if iso_date and iso_date < cutoff:
                ids_to_delete.append(doc_id)
            elif not iso_date:
                # 没有 ISO 日期，尝试解析原始日期
                raw_date = meta.get("published_date", "")
                iso = _parse_rss_date(raw_date)
                if iso and iso < cutoff:
                    ids_to_delete.append(doc_id)

        if ids_to_delete:
            store.delete(ids=ids_to_delete)
            return len(ids_to_delete)
    except Exception:
        pass
    return 0
