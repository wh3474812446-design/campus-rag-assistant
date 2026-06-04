"""向量数据库：基于 Chroma 的本地持久化存储与检索。"""

from __future__ import annotations

import hashlib

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings
from app.rag.embeddings import embed_documents, embed_query

_client: chromadb.ClientAPI | None = None


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=str(settings.chroma_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def _get_collection():
    return _get_client().get_or_create_collection(
        name=settings.collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def _chunk_id(source: str, index: int, text: str) -> str:
    h = hashlib.md5(f"{source}-{index}-{text}".encode("utf-8")).hexdigest()
    return f"{source}::{index}::{h[:8]}"


def add_chunks(source: str, doc_type: str, chunks: list[str]) -> int:
    """把某个文档的所有文本块写入向量库。返回写入数量。"""
    if not chunks:
        return 0
    collection = _get_collection()
    embeddings = embed_documents(chunks)
    ids = [_chunk_id(source, i, c) for i, c in enumerate(chunks)]
    metadatas = [
        {"source": source, "doc_type": doc_type, "chunk_index": i}
        for i in range(len(chunks))
    ]
    collection.upsert(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    return len(chunks)


def search(query: str, top_k: int | None = None) -> list[dict]:
    """检索与问题最相关的文本块。"""
    top_k = top_k or settings.top_k
    collection = _get_collection()
    if collection.count() == 0:
        return []

    query_vec = embed_query(query)
    result = collection.query(
        query_embeddings=[query_vec],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    docs = result["documents"][0]
    metas = result["metadatas"][0]
    dists = result["distances"][0]
    for doc, meta, dist in zip(docs, metas, dists):
        hits.append(
            {
                "text": doc,
                "source": meta.get("source", "未知"),
                "doc_type": meta.get("doc_type", ""),
                "chunk_index": meta.get("chunk_index", -1),
                "score": round(1 - dist, 4),  # cosine 距离转相似度
            }
        )
    return hits


def list_documents() -> list[dict]:
    """列出已入库的文档及其块数。"""
    collection = _get_collection()
    if collection.count() == 0:
        return []
    data = collection.get(include=["metadatas"])
    stats: dict[str, dict] = {}
    for meta in data["metadatas"]:
        src = meta.get("source", "未知")
        if src not in stats:
            stats[src] = {"source": src, "doc_type": meta.get("doc_type", ""), "chunks": 0}
        stats[src]["chunks"] += 1
    return sorted(stats.values(), key=lambda x: x["source"])


def delete_document(source: str) -> int:
    """删除某个文档对应的所有向量块。"""
    collection = _get_collection()
    existing = collection.get(where={"source": source})
    ids = existing["ids"]
    if ids:
        collection.delete(ids=ids)
    return len(ids)


def count() -> int:
    return _get_collection().count()
