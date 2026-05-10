"""会话 + 消息相关 Pydantic 模型"""
from datetime import datetime
from uuid import UUID
from typing import Optional

from pydantic import BaseModel, Field


# ── 会话 ──
class ConversationCreate(BaseModel):
    title: str = Field(default="新建会话", max_length=200, description="会话标题")


class ConversationUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    status: Optional[str] = Field(default=None, pattern=r"^(active|archived|deleted)$")


class ConversationResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    total: int


# ── 消息 ──
class MessageCreate(BaseModel):
    conv_id: UUID = Field(..., description="所属会话 ID")
    role: str = Field(..., pattern=r"^(user|assistant|system)$", description="角色")
    content: str = Field(..., min_length=1, description="消息内容")
    sources: Optional[list[dict]] = Field(default=None, description="引用来源列表")


class MessageResponse(BaseModel):
    id: UUID
    conv_id: UUID
    role: str
    content: str
    sources: Optional[list[dict]] = None
    feedback: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageListResponse(BaseModel):
    items: list[MessageResponse]
    total: int
