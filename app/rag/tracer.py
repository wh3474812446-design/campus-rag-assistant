"""逐句溯源：把答案拆成句子，为每句在原文里找到最匹配的那一句并定位所在段落。

用本地 BGE 做句子级语义比对，不调用大模型、不额外联网。
"""

from __future__ import annotations

import re

import numpy as np

from app.rag import vectorstore
from app.rag.embeddings import embed_documents

# 按中文/英文句末标点或换行切句
_SENT_PATTERN = re.compile(r"(?<=[。！？!?\n])")


def split_sentences(text: str) -> list[str]:
    parts = _SENT_PATTERN.split(text)
    return [p.strip() for p in parts if p and p.strip()]


def trace(
    answer: str,
    min_len: int = 6,
    sim_threshold: float = 0.5,
) -> list[dict]:
    """返回答案每句话与其原文依据句的对应关系。"""
    ans_sents = [s for s in split_sentences(answer) if len(s) >= min_len]
    items: list[dict] = []

    for sent in ans_sents:
        # 先用向量检索定位最相关的原文块
        hits = vectorstore.search(sent, top_k=1)
        if not hits:
            continue
        chunk = hits[0]
        chunk_sents = [s for s in split_sentences(chunk["text"]) if len(s) >= 2]
        if not chunk_sents:
            continue

        # 在该块内逐句比对，找最像的一句
        embs = embed_documents([sent] + chunk_sents)
        query_vec = np.array(embs[0])
        cand = np.array(embs[1:])
        scores = cand @ query_vec  # 向量已归一化，点积即余弦相似度
        best_i = int(scores.argmax())
        best_score = float(scores[best_i])
        if best_score < sim_threshold:
            continue

        items.append(
            {
                "answer_sentence": sent,
                "source_sentence": chunk_sents[best_i],
                "source": chunk["source"],
                "chunk_text": chunk["text"],
                "score": round(best_score, 3),
            }
        )
    return items
