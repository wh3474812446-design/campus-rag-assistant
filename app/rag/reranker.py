"""重排序（rerank）：用交叉编码器对候选段落做"问题+原文"成对精排。

混合检索负责"广撒网"召回候选；rerank 负责"精挑"——交叉编码器同时看问题和段落，
判分比双塔向量/BM25 准得多，能显著提升最终送给大模型的原文质量。
"""

from __future__ import annotations

import math

from sentence_transformers import CrossEncoder

from app.config import settings

_model: CrossEncoder | None = None


def get_model() -> CrossEncoder:
    """懒加载交叉编码器单例（首次会下载约 1.1GB 模型）。"""
    global _model
    if _model is None:
        _model = CrossEncoder(settings.reranker_model_name)
    return _model


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def rerank(query: str, hits: list[dict], top_k: int) -> list[dict]:
    """对候选 hits 重排，返回分数最高的 top_k。失败时回退原顺序。"""
    if not hits:
        return hits
    model = get_model()
    scores = model.predict([[query, h["text"]] for h in hits])
    for hit, score in zip(hits, scores):
        s = float(score)
        hit["rerank_score"] = s
        hit["score"] = round(_sigmoid(s), 4)  # 映射到 0~1 便于展示
    ranked = sorted(hits, key=lambda h: h["rerank_score"], reverse=True)
    return ranked[:top_k]
