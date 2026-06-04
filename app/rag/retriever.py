"""混合检索：BM25 关键词 + 向量语义，用 RRF（倒数排名融合）合并。

- 向量检索擅长"意思相近"，但对精确词/编号/专有名词不敏感；
- BM25 关键词检索擅长"词面命中"，正好互补；
- RRF 不依赖两者分数量纲，只看各自排名，融合稳健。
"""

from __future__ import annotations

import jieba

from rank_bm25 import BM25Okapi

from app.config import settings
from app.rag import vectorstore

# BM25 索引缓存（按文件夹分别缓存；库内容变化时重建）
# key: 文件夹名或 "__all__"  ->  (BM25, docs, count)
_bm25_cache: dict[str, tuple] = {}

# RRF 常数，越大越"温和"，业界常用 60
_RRF_K = 60


def _tokenize(text: str) -> list[str]:
    return [t for t in jieba.lcut(text) if t.strip()]


def _get_bm25(folder: str | None):
    """取（某文件夹范围的）BM25 索引；块数变化时重建。"""
    key = folder or "__all__"
    docs = vectorstore.get_all(folder)
    count = len(docs)
    cached = _bm25_cache.get(key)
    if cached and cached[2] == count:
        return cached[0], cached[1]
    bm25 = BM25Okapi([_tokenize(d["text"]) for d in docs]) if docs else None
    _bm25_cache[key] = (bm25, docs, count)
    return bm25, docs


def _bm25_ranked(query: str, n: int, folder: str | None) -> list[dict]:
    bm25, docs = _get_bm25(folder)
    if bm25 is None:
        return []
    scores = bm25.get_scores(_tokenize(query))
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return [docs[i] for i in order[:n] if scores[i] > 0]


def hybrid_search(
    query: str, top_k: int | None = None, folder: str | None = None
) -> list[dict]:
    """返回融合后的 top_k 文本块，每个带 method 标注命中来源。

    folder 不为空时，只在该文件夹（知识库分区）内检索。
    """
    top_k = top_k or settings.top_k
    candidates = max(top_k * 3, settings.retrieval_candidates)

    vec_hits = vectorstore.search(query, top_k=candidates, folder=folder)
    bm_hits = _bm25_ranked(query, candidates, folder)

    # RRF 融合：按各自排名累加 1/(K+rank)
    fused: dict[str, dict] = {}

    def _add(hits: list[dict], method: str) -> None:
        for rank, h in enumerate(hits):
            cid = h["id"]
            if cid not in fused:
                fused[cid] = {"hit": h, "rrf": 0.0, "methods": set()}
            fused[cid]["rrf"] += 1.0 / (_RRF_K + rank + 1)
            fused[cid]["methods"].add(method)
            # 保留向量相似度用于展示
            if "score" in h:
                fused[cid]["hit"]["score"] = h["score"]

    _add(vec_hits, "vector")
    _add(bm_hits, "keyword")

    ranked = sorted(fused.values(), key=lambda x: x["rrf"], reverse=True)[:top_k]

    results = []
    for item in ranked:
        hit = dict(item["hit"])
        methods = item["methods"]
        if methods == {"vector", "keyword"}:
            hit["method"] = "向量+关键词"
        elif methods == {"keyword"}:
            hit["method"] = "关键词"
        else:
            hit["method"] = "向量"
        hit.setdefault("score", 0.0)
        results.append(hit)
    return results
