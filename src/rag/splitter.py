"""文本分割策略"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


def get_text_splitter(
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> RecursiveCharacterTextSplitter:
    """获取中文友好的文本分割器"""
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "！", "？", "，", " ", ""],
        keep_separator=True,
    )


def split_documents(docs: list[Document]) -> list[Document]:
    """将文档列表分割成块"""
    splitter = get_text_splitter()
    chunks = splitter.split_documents(docs)
    return chunks
