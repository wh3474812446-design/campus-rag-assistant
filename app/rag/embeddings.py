"""本地中文向量化：基于 sentence-transformers 的 BGE 模型。

BGE 系列检索时，query 端需要加指令前缀以提升效果；文档端不加。
"""

from __future__ import annotations

from sentence_transformers import SentenceTransformer

from app.config import settings

# bge 中文模型推荐的检索指令前缀
_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """懒加载单例，避免每次请求都重新载入模型。"""
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model_name)
    return _model


def embed_documents(texts: list[str]) -> list[list[float]]:
    model = get_model()
    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return vectors.tolist()


def embed_query(text: str) -> list[float]:
    model = get_model()
    vector = model.encode(
        _QUERY_INSTRUCTION + text,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return vector.tolist()
