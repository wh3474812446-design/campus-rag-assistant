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


def _title_ranked(query: str, n: int, folder: str | None) -> list[dict]:
    """第三路召回：问题词命中文档名（source），就召回该文档的文本块。

    向量/BM25 都看的是正文，对"问题正好是某份文件的主题"不够敏感；
    标题路按文件名命中补一刀，让主题对口的文档更容易被选中。
    """
    _, docs = _get_bm25(folder)  # 复用缓存里的全量块
    if not docs:
        return []
    q_tokens = [t for t in _tokenize(query) if len(t) >= 2]
    if not q_tokens:
        return []
    scored = []
    for d in docs:
        src = d.get("source", "")
        hit = sum(1 for t in q_tokens if t in src)
        if hit > 0:
            scored.append((hit, d))
    scored.sort(key=lambda x: (-x[0], x[1].get("chunk_index", 0)))
    return [d for _, d in scored[:n]]


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
    title_hits = _title_ranked(query, candidates, folder) if settings.use_title_route else []

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
    _add(title_hits, "title")

    ranked = sorted(fused.values(), key=lambda x: x["rrf"], reverse=True)

    # 融合后先取一批候选（开启重排时多取一些供精排）
    pool_size = settings.rerank_candidates if settings.use_rerank else top_k
    _LABEL = {"vector": "向量", "keyword": "关键词", "title": "标题"}
    pool = []
    for item in ranked[:pool_size]:
        hit = dict(item["hit"])
        methods = item["methods"]
        hit["method"] = "+".join(
            _LABEL[m] for m in ("vector", "keyword", "title") if m in methods
        ) or "向量"
        hit.setdefault("score", 0.0)
        pool.append(hit)

    # 交叉编码器重排（失败则回退融合顺序，保证可用）
    if settings.use_rerank and pool:
        try:
            from app.rag.reranker import rerank

            return rerank(query, pool, top_k)
        except Exception:  # noqa: BLE001
            return pool[:top_k]
    return pool[:top_k]
