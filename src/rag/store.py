"""ChromaDB 向量库管理 —— 进程级单例经 src.deps 持有"""

from chromadb.config import Settings as ChromaSettings
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings
from config.settings import get_settings

settings = get_settings()

_collection_name = "game_news"


def get_embedding_function():
    """获取 Embedding 函数 —— 本地模型 或 OpenAI 兼容 API"""
    if settings.embedding_model == "local":
        return HuggingFaceEmbeddings(
            model_name="shibing624/text2vec-base-chinese",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )


def _create_store() -> Chroma:
    """构造持久化 Chroma 向量库（deps 注册为单例工厂）"""
    return Chroma(
        persist_directory=settings.chroma_persist_dir,
        embedding_function=get_embedding_function(),
        collection_name=_collection_name,
        client_settings=ChromaSettings(
            anonymized_telemetry=False,
            is_persistent=True,
        ),
    )


def get_vector_store() -> Chroma:
    """获取持久化的 Chroma 向量库实例（单例由 deps 持有）"""
    from src.deps import get_vector_store as deps_get
    return deps_get()


def get_retriever(k: int = 5, fetch_k: int = 20):
    """获取 MMR 混合检索器"""
    store = get_vector_store()
    return store.as_retriever(
        search_type="mmr",
        search_kwargs={"k": k, "fetch_k": fetch_k},
    )


def get_doc_count() -> int:
    """当前索引的文档总数（公共 API，替代直接访问内部 _collection）"""
    try:
        return get_vector_store()._collection.count()
    except Exception:
        return 0