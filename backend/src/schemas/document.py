"""文档相关 Pydantic 模型"""
from datetime import datetime
from uuid import UUID
from typing import Optional

from pydantic import BaseModel


# ── 文档 ──
class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    title: Optional[str] = None
    status: str
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int


# ── 分块 ──
class ChunkResponse(BaseModel):
    """文档分块响应（不含 embedding，向量太长不适合放 JSON 响应）"""
    id: UUID
    doc_id: UUID
    chunk_index: int
    chunk_title: Optional[str] = None
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChunkListResponse(BaseModel):
    items: list[ChunkResponse]
    total: int
