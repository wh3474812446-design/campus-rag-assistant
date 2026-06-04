"""FastAPI 应用入口。

启动：uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

app = FastAPI(
    title="校园知识库问答助手 API",
    description="面向大学生的校园政策 RAG 问答：上传文件自动建库，基于原文回答教务、实习、奖学金、转专业等问题。",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {
        "name": "校园知识库问答助手",
        "docs": "/docs",
        "endpoints": ["/api/upload", "/api/chat", "/api/documents", "/api/health"],
    }
