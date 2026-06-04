"""入库流水线：文件 -> 解析 -> 切分 -> 向量化 -> 写库。"""

from __future__ import annotations

from pathlib import Path

from app.rag.loader import load_document
from app.rag.splitter import split_text
from app.rag.vectorstore import add_chunks

# 文件名关键词 -> 文档类型（用于标注来源类别）
_TYPE_KEYWORDS = {
    "学生手册": "学生手册",
    "教务": "教务通知",
    "奖学金": "奖学金评定办法",
    "实习": "实习管理规定",
    "毕业论文": "毕业论文规范",
    "论文": "毕业论文规范",
}


def guess_doc_type(filename: str) -> str:
    for kw, label in _TYPE_KEYWORDS.items():
        if kw in filename:
            return label
    return "其他文件"


def ingest_file(path: str | Path) -> dict:
    """处理单个文件，返回入库结果。"""
    path = Path(path)
    source = path.name
    doc_type = guess_doc_type(source)

    text = load_document(path)
    chunks = split_text(text)
    written = add_chunks(source=source, doc_type=doc_type, chunks=chunks)

    return {
        "source": source,
        "doc_type": doc_type,
        "chars": len(text),
        "chunks": written,
    }
