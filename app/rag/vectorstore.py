"""向量数据库：基于 Chroma 的本地持久化存储与检索（支持按文件夹分区）。"""

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


def _chunk_id(folder: str, source: str, index: int, text: str) -> str:
    h = hashlib.md5(f"{folder}-{source}-{index}-{text}".encode("utf-8")).hexdigest()
    return f"{folder}::{source}::{index}::{h[:8]}"


def _folder_where(folder: str | None):
    return {"folder": folder} if folder else None


def add_chunks(
    source: str, doc_type: str, chunks: list[str], folder: str = "默认"
) -> int:
    """把某个文档的所有文本块写入向量库。返回写入数量。"""
    if not chunks:
        return 0
    collection = _get_collection()
    embeddings = embed_documents(chunks)
    ids = [_chunk_id(folder, source, i, c) for i, c in enumerate(chunks)]
    metadatas = [
        {"source": source, "doc_type": doc_type, "chunk_index": i, "folder": folder}
        for i in range(len(chunks))
    ]
    collection.upsert(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    return len(chunks)


def search(query: str, top_k: int | None = None, folder: str | None = None) -> list[dict]:
    """检索与问题最相关的文本块；folder 不为空时只在该文件夹内检索。"""
    top_k = top_k or settings.top_k
    collection = _get_collection()
    if collection.count() == 0:
        return []

    query_vec = embed_query(query)
    result = collection.query(
        query_embeddings=[query_vec],
        n_results=min(top_k, collection.count()),
        where=_folder_where(folder),
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    ids = result["ids"][0]
    docs = result["documents"][0]
    metas = result["metadatas"][0]
    dists = result["distances"][0]
    for cid, doc, meta, dist in zip(ids, docs, metas, dists):
        hits.append(
            {
                "id": cid,
                "text": doc,
                "source": meta.get("source", "未知"),
                "doc_type": meta.get("doc_type", ""),
                "folder": meta.get("folder", "默认"),
                "chunk_index": meta.get("chunk_index", -1),
                "score": round(1 - dist, 4),  # cosine 距离转相似度
            }
        )
    return hits


def get_all(folder: str | None = None) -> list[dict]:
    """取出（某文件夹的）全部文本块，供 BM25 关键词检索构建索引。"""
    collection = _get_collection()
    if collection.count() == 0:
        return []
    data = collection.get(where=_folder_where(folder), include=["documents", "metadatas"])
    out = []
    for cid, doc, meta in zip(data["ids"], data["documents"], data["metadatas"]):
        out.append(
            {
                "id": cid,
                "text": doc,
                "source": meta.get("source", "未知"),
                "doc_type": meta.get("doc_type", ""),
                "folder": meta.get("folder", "默认"),
                "chunk_index": meta.get("chunk_index", -1),
            }
        )
    return out


def list_documents() -> list[dict]:
    """列出已入库的文档（按 文件夹+文件名 聚合）及其块数。"""
    collection = _get_collection()
    if collection.count() == 0:
        return []
    data = collection.get(include=["metadatas"])
    stats: dict[tuple, dict] = {}
    for meta in data["metadatas"]:
        folder = meta.get("folder", "默认")
        src = meta.get("source", "未知")
        key = (folder, src)
        if key not in stats:
            stats[key] = {
                "source": src,
                "folder": folder,
                "doc_type": meta.get("doc_type", ""),
                "chunks": 0,
            }
        stats[key]["chunks"] += 1
    return sorted(stats.values(), key=lambda x: (x["folder"], x["source"]))


def existing_folders() -> list[str]:
    """库中实际出现过的文件夹名。"""
    collection = _get_collection()
    if collection.count() == 0:
        return []
    data = collection.get(include=["metadatas"])
    return sorted({m.get("folder", "默认") for m in data["metadatas"]})


def delete_document(source: str, folder: str | None = None) -> int:
    """删除某文档（可限定文件夹）对应的所有向量块。"""
    collection = _get_collection()
    where = {"source": source}
    if folder:
        where = {"$and": [{"source": source}, {"folder": folder}]}
    existing = collection.get(where=where)
    ids = existing["ids"]
    if ids:
        collection.delete(ids=ids)
    return len(ids)


def delete_folder_docs(folder: str) -> int:
    """删除某文件夹下的所有文档块。"""
    collection = _get_collection()
    existing = collection.get(where={"folder": folder})
    ids = existing["ids"]
    if ids:
        collection.delete(ids=ids)
    return len(ids)


def count() -> int:
    return _get_collection().count()
