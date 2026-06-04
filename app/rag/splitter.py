"""文本切分：按中文标点递归切成带重叠的小块，便于检索。"""

from app.config import settings

# 优先按段落，再按句子，最后按字符切
_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]


def _split_by_separator(text: str, sep: str) -> list[str]:
    if sep == "":
        return list(text)
    # 保留分隔符，避免句子粘连时丢标点
    parts = text.split(sep)
    result = []
    for i, p in enumerate(parts):
        if i < len(parts) - 1:
            result.append(p + sep)
        elif p:
            result.append(p)
    return [r for r in result if r]


def _recursive_split(text: str, chunk_size: int, separators: list[str]) -> list[str]:
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    sep = separators[0]
    pieces = _split_by_separator(text, sep)
    chunks: list[str] = []
    buffer = ""

    for piece in pieces:
        if len(piece) > chunk_size:
            # 单块仍超长，用更细的分隔符继续切
            if buffer:
                chunks.append(buffer)
                buffer = ""
            chunks.extend(_recursive_split(piece, chunk_size, separators[1:] or [""]))
        elif len(buffer) + len(piece) <= chunk_size:
            buffer += piece
        else:
            if buffer:
                chunks.append(buffer)
            buffer = piece
    if buffer.strip():
        chunks.append(buffer)
    return chunks


def _add_overlap(chunks: list[str], overlap: int) -> list[str]:
    """给相邻块加上重叠，避免答案被切断在边界。"""
    if overlap <= 0 or len(chunks) <= 1:
        return chunks
    out = [chunks[0]]
    for prev, cur in zip(chunks, chunks[1:]):
        tail = prev[-overlap:]
        out.append(tail + cur)
    return out


def split_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[str]:
    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap if chunk_overlap is not None else settings.chunk_overlap

    raw_chunks = _recursive_split(text, chunk_size, _SEPARATORS)
    chunks = _add_overlap(raw_chunks, chunk_overlap)
    return [c.strip() for c in chunks if c.strip()]
