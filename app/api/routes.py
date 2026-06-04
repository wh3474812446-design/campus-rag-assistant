"""HTTP 接口：上传文档、问答、文档管理。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.config import settings, update_env_file
from app.rag import folders as folder_mgr
from app.rag import vectorstore
from app.rag.chain import answer as rag_answer
from app.rag.chain import answer_stream, set_credentials, test_connection
from app.rag.indexer import ingest_file
from app.rag.loader import SUPPORTED_EXTENSIONS
from app.rag.tracer import trace as trace_sentences
from app.schemas import (
    ChatRequest,
    ChatResponse,
    ConfigInfo,
    ConfigUpdate,
    DeleteResult,
    DocumentItem,
    DocumentList,
    FolderCreate,
    FolderList,
    FolderResult,
    TestResult,
    TraceItem,
    TraceRequest,
    TraceResponse,
    UploadResult,
)

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "chunks_in_db": vectorstore.count()}


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 12:
        return "****"
    return f"{key[:6]}…{key[-4:]}"


@router.get("/config", response_model=ConfigInfo)
def get_config() -> ConfigInfo:
    return ConfigInfo(
        configured=bool(settings.deepseek_api_key),
        api_key_masked=_mask_key(settings.deepseek_api_key),
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
    )


@router.post("/config", response_model=ConfigInfo)
def set_config(req: ConfigUpdate) -> ConfigInfo:
    """更新 API 配置：内存即时生效 + 写回 .env 持久化。"""
    set_credentials(api_key=req.api_key, base_url=req.base_url, model=req.model)

    persist: dict[str, str] = {}
    if req.api_key:
        persist["DEEPSEEK_API_KEY"] = req.api_key
    if req.base_url:
        persist["DEEPSEEK_BASE_URL"] = req.base_url
    if req.model:
        persist["DEEPSEEK_MODEL"] = req.model
    if persist:
        update_env_file(persist)

    return get_config()


@router.post("/config/test", response_model=TestResult)
def test_config() -> TestResult:
    ok, msg = test_connection()
    return TestResult(ok=ok, message=msg)


@router.post("/upload", response_model=UploadResult)
async def upload(
    file: UploadFile = File(...),
    folder: str = Form("默认"),
) -> UploadResult:
    """上传一个文件到指定文件夹并自动构建知识库。"""
    filename = file.filename or "未命名"
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型 {ext}，支持：{', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    folder = (folder or "默认").strip() or "默认"
    # 同名文件按 文件夹 分目录存放，避免覆盖
    save_dir = settings.upload_path / folder
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / filename
    with save_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        result = ingest_file(save_path, folder=folder)
    except ValueError as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(e))

    # 确保该文件夹出现在文件夹列表里
    folder_mgr.create_folder(folder)
    return UploadResult(**result)


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """基于知识库原文回答问题。"""
    try:
        result = rag_answer(req.question, top_k=req.top_k, mode=req.mode, folder=req.folder)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return ChatResponse(**result)


@router.post("/chat/stream")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    """流式问答（SSE）：先发 sources 事件，再逐段发 token 事件。"""

    def event_gen():
        try:
            for kind, payload in answer_stream(
                req.question, top_k=req.top_k, mode=req.mode, folder=req.folder
            ):
                key = "sources" if kind == "sources" else "token"
                yield "data: " + json.dumps({key: payload}, ensure_ascii=False) + "\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:  # noqa: BLE001
            yield "data: " + json.dumps({"error": str(e)}, ensure_ascii=False) + "\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.post("/trace", response_model=TraceResponse)
def trace(req: TraceRequest) -> TraceResponse:
    """逐句溯源：为答案的每句话找到原文依据句。"""
    items = trace_sentences(req.answer)
    return TraceResponse(items=[TraceItem(**it) for it in items])


@router.get("/documents", response_model=DocumentList)
def documents() -> DocumentList:
    docs = vectorstore.list_documents()
    return DocumentList(
        total_documents=len(docs),
        total_chunks=sum(d["chunks"] for d in docs),
        documents=[DocumentItem(**d) for d in docs],
    )


@router.delete("/documents/{source}", response_model=DeleteResult)
def delete_document(source: str, folder: str | None = None) -> DeleteResult:
    deleted = vectorstore.delete_document(source, folder=folder)
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"未找到文档：{source}")
    # 同时删掉本地文件
    if folder:
        (settings.upload_path / folder / source).unlink(missing_ok=True)
    (settings.upload_path / source).unlink(missing_ok=True)
    return DeleteResult(source=source, deleted_chunks=deleted)


# ---------- 文件夹（知识库分区）管理 ----------
@router.get("/folders", response_model=FolderList)
def list_folders() -> FolderList:
    return FolderList(folders=folder_mgr.list_folders(extra=vectorstore.existing_folders()))


@router.post("/folders", response_model=FolderResult)
def create_folder(req: FolderCreate) -> FolderResult:
    ok = folder_mgr.create_folder(req.name)
    folders = folder_mgr.list_folders(extra=vectorstore.existing_folders())
    if not ok:
        raise HTTPException(status_code=400, detail="文件夹已存在或名称非法")
    return FolderResult(ok=True, folders=folders)


@router.delete("/folders/{name}", response_model=FolderResult)
def delete_folder(name: str) -> FolderResult:
    if name == folder_mgr.DEFAULT_FOLDER:
        raise HTTPException(status_code=400, detail="默认文件夹不可删除")
    deleted = vectorstore.delete_folder_docs(name)
    folder_mgr.delete_folder(name)
    # 删掉该文件夹的本地上传目录
    import shutil as _shutil

    _shutil.rmtree(settings.upload_path / name, ignore_errors=True)
    folders = folder_mgr.list_folders(extra=vectorstore.existing_folders())
    return FolderResult(ok=True, folders=folders, deleted_chunks=deleted)
