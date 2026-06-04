"""API 请求/响应数据模型。"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="用户的问题")
    top_k: int | None = Field(None, description="检索条数，默认用配置值")


class SourceItem(BaseModel):
    source: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceItem]


class UploadResult(BaseModel):
    source: str
    doc_type: str
    chars: int
    chunks: int


class DocumentItem(BaseModel):
    source: str
    doc_type: str
    chunks: int


class DocumentList(BaseModel):
    total_documents: int
    total_chunks: int
    documents: list[DocumentItem]


class DeleteResult(BaseModel):
    source: str
    deleted_chunks: int
