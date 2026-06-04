"""RAG 问答链：检索原文 -> 拼 prompt -> 调 DeepSeek 生成基于原文的回答。"""

from __future__ import annotations

from openai import OpenAI

from app.config import settings
from app.rag.vectorstore import search

_client: OpenAI | None = None

SYSTEM_PROMPT = """你是一名严谨的校园政策问答助手，服务对象是大学生。
请严格遵守以下规则：
1. 只能依据【参考资料】中的内容回答，不要编造或臆测。
2. 如果参考资料中没有相关信息，明确告知"根据已上传的资料，暂时找不到相关规定"，并建议用户咨询对应部门。
3. 回答要条理清晰、口语化，必要时分点说明。
4. 在回答末尾标注依据来自哪个文件（如：依据《学生手册》）。
"""


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not settings.deepseek_api_key:
            raise RuntimeError("未配置 DEEPSEEK_API_KEY，请在 .env 中填写。")
        _client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
    return _client


def _build_context(hits: list[dict]) -> str:
    blocks = []
    for i, h in enumerate(hits, 1):
        src = h["source"]
        blocks.append(f"【资料{i}｜来源：{src}】\n{h['text']}")
    return "\n\n".join(blocks)


def answer(question: str, top_k: int | None = None) -> dict:
    """对外的主入口：返回 {answer, sources}。"""
    hits = search(question, top_k=top_k)

    if not hits:
        return {
            "answer": "知识库还是空的，请先上传学生手册、教务通知等文件再提问。",
            "sources": [],
        }

    context = _build_context(hits)
    user_prompt = (
        f"参考资料如下：\n\n{context}\n\n"
        f"请根据以上资料回答问题：{question}"
    )

    client = _get_client()
    resp = client.chat.completions.create(
        model=settings.deepseek_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        stream=False,
    )
    reply = resp.choices[0].message.content

    # 去重来源，按相似度展示
    seen = set()
    sources = []
    for h in hits:
        key = h["source"]
        if key not in seen:
            seen.add(key)
            sources.append({"source": h["source"], "score": h["score"]})

    return {"answer": reply, "sources": sources}
