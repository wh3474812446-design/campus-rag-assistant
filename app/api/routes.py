"""HTTP 接口：上传文档、问答、文档管理。"""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.rag import vectorstore
from app.rag.chain import answer as rag_answer
from app.rag.indexer import ingest_file
from app.rag.loader import SUPPORTED_EXTENSIONS
from app.schemas import (
    ChatRequest,
    ChatResponse,
    DeleteResult,
    DocumentItem,
    DocumentList,
    UploadResult,
)

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "chunks_in_db": vectorstore.count()}


@router.post("/upload", response_model=UploadResult)
async def upload(file: UploadFile = File(...)) -> UploadResult:
    """上传一个文件并自动构建知识库。"""
    filename = file.filename or "未命名"
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型 {ext}，支持：{', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    save_path = settings.upload_path / filename
    with save_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        result = ingest_file(save_path)
    except ValueError as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(e))

    return UploadResult(**result)


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """基于知识库原文回答问题。"""
    try:
        result = rag_answer(req.question, top_k=req.top_k)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return ChatResponse(**result)


@router.get("/documents", response_model=DocumentList)
def documents() -> DocumentList:
    docs = vectorstore.list_documents()
    return DocumentList(
        total_documents=len(docs),
        total_chunks=sum(d["chunks"] for d in docs),
        documents=[DocumentItem(**d) for d in docs],
    )


@router.delete("/documents/{source}", response_model=DeleteResult)
def delete_document(source: str) -> DeleteResult:
    deleted = vectorstore.delete_document(source)
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"未找到文档：{source}")
    # 同时删掉本地文件
    (settings.upload_path / source).unlink(missing_ok=True)
    return DeleteResult(source=source, deleted_chunks=deleted)
