"""长期记忆表（pgvector）"""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector

from ..core.database import Base


class LongTermMemory(Base):
    __tablename__ = "long_term_memories"
    __table_args__ = (
        Index("idx_ltm_user_id", "user_id"),
        # HNSW 索引 idx_ltm_embedding 在 init_db.sql 中单独创建
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    memory_type = Column(String(50), nullable=False, default="session_summary", comment="记忆类型")
    content = Column(Text, nullable=False, comment="记忆内容")
    embedding = Column(Vector(768), comment="dense向量（768维）")
    metadata_ = Column("metadata", JSONB, comment="元数据")
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
