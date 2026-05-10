"""长期记忆相关 Pydantic 模型"""
from datetime import datetime
from uuid import UUID
from typing import Optional

from pydantic import BaseModel


class MemoryResponse(BaseModel):
    id: UUID
    user_id: UUID
    memory_type: str
    content: str
    metadata_: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MemoryListResponse(BaseModel):
    items: list[MemoryResponse]
    total: int
