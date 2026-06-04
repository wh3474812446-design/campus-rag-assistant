"""问答链：支持三种模式。

- kb       知识库严格模式：只依据检索到的原文回答，绝不编造（默认）
- hybrid   知识库 + AI 补充：优先用原文，文档没有的用 DeepSeek 通用知识补充并标注
- general  通用助手：不检索，直接用 DeepSeek 回答任何问题
"""

from __future__ import annotations

from openai import OpenAI

from app.config import settings
from app.rag.vectorstore import search

_client: OpenAI | None = None

# 合法模式
VALID_MODES = {"kb", "hybrid", "general"}

# 知识库严格模式
SYSTEM_PROMPT_KB = """你是一名严谨的校园政策问答助手，服务对象是大学生。
请严格遵守以下规则：
1. 只能依据【参考资料】中的内容回答，不要编造或臆测。
2. 如果参考资料中没有相关信息，明确告知"根据已上传的资料，暂时找不到相关规定"，并建议用户咨询对应部门。
3. 回答要条理清晰、口语化，必要时分点说明。
4. 在回答末尾标注依据来自哪个文件（如：依据《学生手册》）。
"""

# 知识库 + AI 补充模式
SYSTEM_PROMPT_HYBRID = """你是一名校园政策问答助手，服务对象是大学生。
回答规则：
1. 优先依据【参考资料】中的内容回答，这是最权威的官方依据。
2. 如果参考资料不足以完整回答，你可以用自己的通用知识进行补充，但必须明确区分：
   - 来自上传文件的内容，标注"📄 依据学校文件：……"
   - 你自己补充的通用知识，标注"💡 AI 补充（仅供参考，请以学校最新规定为准）：……"
3. 回答要条理清晰、口语化，必要时分点说明。
"""

# 通用助手模式
SYSTEM_PROMPT_GENERAL = """你是一个乐于助人的 AI 助手，可以回答各类问题、写作、翻译、解释概念、协助写代码等。
请用清晰、友好的中文回答。"""


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
        blocks.append(f"【资料{i}｜来源：{h['source']}】\n{h['text']}")
    return "\n\n".join(blocks)


def _dedup_sources(hits: list[dict]) -> list[dict]:
    seen = set()
    sources = []
    for h in hits:
        if h["source"] not in seen:
            seen.add(h["source"])
            sources.append({"source": h["source"], "score": h["score"]})
    return sources


def _call_llm(system_prompt: str, user_prompt: str, temperature: float) -> str:
    client = _get_client()
    resp = client.chat.completions.create(
        model=settings.deepseek_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        stream=False,
    )
    return resp.choices[0].message.content


def answer(question: str, top_k: int | None = None, mode: str = "kb") -> dict:
    """对外主入口：返回 {answer, sources}。mode ∈ {kb, hybrid, general}。"""
    if mode not in VALID_MODES:
        mode = "kb"

    # 通用助手：不检索，直接回答
    if mode == "general":
        reply = _call_llm(SYSTEM_PROMPT_GENERAL, question, temperature=0.7)
        return {"answer": reply, "sources": []}

    # 知识库 / 混合：先检索
    hits = search(question, top_k=top_k)

    if not hits:
        if mode == "hybrid":
            # 文档没东西，退化为通用回答但提示用户
            reply = _call_llm(
                SYSTEM_PROMPT_GENERAL,
                question,
                temperature=0.7,
            )
            note = "（⚠️ 知识库中暂无相关文件，以下为 AI 通用回答，请以学校最新规定为准）\n\n"
            return {"answer": note + reply, "sources": []}
        return {
            "answer": "知识库还是空的，请先上传学生手册、教务通知等文件再提问。",
            "sources": [],
        }

    context = _build_context(hits)
    user_prompt = f"参考资料如下：\n\n{context}\n\n请根据以上资料回答问题：{question}"

    if mode == "hybrid":
        reply = _call_llm(SYSTEM_PROMPT_HYBRID, user_prompt, temperature=0.4)
    else:  # kb
        reply = _call_llm(SYSTEM_PROMPT_KB, user_prompt, temperature=0.2)

    return {"answer": reply, "sources": _dedup_sources(hits)}
