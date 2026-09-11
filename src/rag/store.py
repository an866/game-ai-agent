"""ChromaDB 向量库管理 —— 进程级单例经 src.deps 持有"""

import os
from pathlib import Path

from chromadb.config import Settings as ChromaSettings
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings
from config.settings import get_settings

settings = get_settings()

_collection_name = "game_news"
_embedding_fn = None


def _local_model_cached(model_name: str) -> bool:
    """HF hub 本地是否已有该模型（有则可离线加载，跳过网络 HEAD）"""
    short = model_name.split("/")[-1]
    cache_root = Path.home() / ".cache" / "huggingface" / "hub"
    if not cache_root.exists():
        return False
    return any(cache_root.glob(f"*{short}*"))


def get_embedding_function():
    """获取 Embedding 函数 —— 本地模型 或 OpenAI 兼容 API（进程内缓存）

    本地模型已缓存时设置 HF_HUB_OFFLINE=1：否则 sentence-transformers
    每次启动都会连 huggingface.co 做版本检查，网络差时拖 30s+，
    新闻链路看起来像「一直不回答」。
    """
    global _embedding_fn
    if _embedding_fn is not None:
        return _embedding_fn

    if settings.embedding_model == "local":
        model_name = "shibing624/text2vec-base-chinese"
        if _local_model_cached(model_name):
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        _embedding_fn = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        return _embedding_fn

    _embedding_fn = OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )
    return _embedding_fn


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
    """当前索引的文档总数。

    用 chromadb PersistentClient 直连 collection.count()，
    **不要**走 get_vector_store()——那会实例化 HuggingFaceEmbeddings，
    首次加载可拖慢概览面板数十秒。
    """
    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings
        client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False, is_persistent=True),
        )
        col = client.get_or_create_collection(_collection_name)
        return int(col.count())
    except Exception:
        try:
            # 退化：已初始化的向量库单例
            return int(get_vector_store()._collection.count())
        except Exception:
            return 0


def clear_embedding_cache() -> None:
    """测试 / settings 变更后清空 embedding 单例"""
    global _embedding_fn
    _embedding_fn = None
