"""API 请求/响应数据模型。"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="用户的问题")
    top_k: int | None = Field(None, description="检索条数，默认用配置值")
    mode: str = Field("kb", description="问答模式：kb=知识库严格 / hybrid=知识库+AI补充 / general=通用助手")
    folder: str | None = Field(None, description="限定在某个文件夹（知识库分区）内检索，None=全部")


class SourceItem(BaseModel):
    source: str
    score: float
    method: str = "向量"


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceItem]


class UploadResult(BaseModel):
    source: str
    doc_type: str
    folder: str
    chars: int
    chunks: int


class DocumentItem(BaseModel):
    source: str
    doc_type: str
    folder: str
    chunks: int


class DocumentList(BaseModel):
    total_documents: int
    total_chunks: int
    documents: list[DocumentItem]


class DeleteResult(BaseModel):
    source: str
    deleted_chunks: int


class FolderList(BaseModel):
    folders: list[str]


class FolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)


class FolderResult(BaseModel):
    ok: bool
    folders: list[str]
    deleted_chunks: int = 0


class ConfigInfo(BaseModel):
    configured: bool
    api_key_masked: str
    base_url: str
    model: str


class ConfigUpdate(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


class TestResult(BaseModel):
    ok: bool
    message: str


class TraceRequest(BaseModel):
    answer: str = Field(..., min_length=1)


class TraceItem(BaseModel):
    answer_sentence: str
    source_sentence: str
    source: str
    chunk_text: str
    score: float


class TraceResponse(BaseModel):
    items: list[TraceItem]
