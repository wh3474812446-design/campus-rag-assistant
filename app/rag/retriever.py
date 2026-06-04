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

# BM25 索引缓存（库内容变化时重建）
_bm25: BM25Okapi | None = None
_bm25_docs: list[dict] = []
_bm25_count: int = -1

# RRF 常数，越大越"温和"，业界常用 60
_RRF_K = 60


def _tokenize(text: str) -> list[str]:
    return [t for t in jieba.lcut(text) if t.strip()]


def _ensure_bm25() -> None:
    """库里块数变化时，重建 BM25 索引。"""
    global _bm25, _bm25_docs, _bm25_count
    count = vectorstore.count()
    if _bm25 is not None and count == _bm25_count:
        return
    _bm25_docs = vectorstore.get_all()
    _bm25_count = count
    if _bm25_docs:
        corpus = [_tokenize(d["text"]) for d in _bm25_docs]
        _bm25 = BM25Okapi(corpus)
    else:
        _bm25 = None


def _bm25_ranked(query: str, n: int) -> list[dict]:
    _ensure_bm25()
    if _bm25 is None:
        return []
    scores = _bm25.get_scores(_tokenize(query))
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return [_bm25_docs[i] for i in order[:n] if scores[i] > 0]


def hybrid_search(query: str, top_k: int | None = None) -> list[dict]:
    """返回融合后的 top_k 文本块，每个带 method 标注命中来源。"""
    top_k = top_k or settings.top_k
    candidates = max(top_k * 3, settings.retrieval_candidates)

    vec_hits = vectorstore.search(query, top_k=candidates)
    bm_hits = _bm25_ranked(query, candidates)

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
