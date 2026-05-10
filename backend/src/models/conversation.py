"""会话表 + 消息表"""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, CheckConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB

from ..core.database import Base


class Conversation(Base):
    """会话表"""
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'archived', 'deleted')",
            name="ck_conv_status",
        ),
        Index("idx_conv_user_id", "user_id"),
        Index("idx_conv_status", "status"),
        # idx_conv_updated_at 是 functional index (updated_at DESC)，在 init_db.sql 中定义
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False, default="新建会话", comment="会话标题")
    status = Column(String(20), nullable=False, default="active", comment="active / archived / deleted")
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"), onupdate=lambda: datetime.now(timezone.utc))


class Message(Base):
    """消息表"""
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant', 'system')",
            name="ck_msg_role",
        ),
        CheckConstraint(
            "feedback IS NULL OR feedback IN ('positive', 'negative')",
            name="ck_msg_feedback",
        ),
        Index("idx_msg_conv_id", "conv_id"),
        Index("idx_msg_created_at", "conv_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    conv_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False, comment="user / assistant / system")
    content = Column(Text, nullable=False, comment="消息内容")
    sources = Column(JSONB, comment="引用来源")
    feedback = Column(String(10), comment="用户反馈: positive / negative")
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
