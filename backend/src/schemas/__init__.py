"""请求/响应 Pydantic 模型 + 内部传递结构"""
from .chunk import Chunk, SearchResult
from .user import UserCreate, UserUpdate, UserLogin, UserResponse, TokenResponse, RefreshRequest, ChangePasswordBody, UpdateProfileBody
from .document import DocumentResponse, DocumentListResponse, ChunkResponse, ChunkListResponse
from .conversation import (
    ConversationCreate, ConversationUpdate, ConversationResponse, ConversationListResponse,
    MessageCreate, MessageResponse, MessageListResponse,
)
from .memory import MemoryResponse, MemoryListResponse
from .audit import AuditLogResponse, AuditLogListResponse

__all__ = [
    # 内部传递
    "Chunk", "SearchResult",
    # 用户
    "UserCreate", "UserUpdate", "UserLogin", "UserResponse", "TokenResponse", "RefreshRequest", "ChangePasswordBody", "UpdateProfileBody",
    # 文档
    "DocumentResponse", "DocumentListResponse", "ChunkResponse", "ChunkListResponse",
    # 会话 + 消息
    "ConversationCreate", "ConversationUpdate", "ConversationResponse", "ConversationListResponse",
    "MessageCreate", "MessageResponse", "MessageListResponse",
    # 记忆
    "MemoryResponse", "MemoryListResponse",
    # 审计
    "AuditLogResponse", "AuditLogListResponse",
]
