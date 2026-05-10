"""文档表 + 文档分块表（pgvector）"""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from ..core.database import Base
from ..core.config import settings


class Document(Base):
    """文档元数据表"""
    __tablename__ = "documents"
    __table_args__ = (
        Index("idx_doc_status", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    filename = Column(String(500), nullable=False, comment="来源文件名")
    title = Column(String(500), comment="文档标题")
    status = Column(String(20), nullable=False, default="pending", comment="处理状态")
    version = Column(Integer, nullable=False, default=1)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="上传者")
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))

    # 反向关联：一个文档有多个分块
    chunks = relationship("DocumentChunk", back_populates="document", lazy="raise")


class DocumentChunk(Base):
    """文档分块表：存文本 + dense向量"""
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("doc_id", "chunk_index"),
        Index("idx_chunk_doc_id", "doc_id"),
        # HNSW 索引 idx_chunk_embedding 在 init_db.sql 中单独创建（ORM 不支持 USING hnsw 语法）
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    doc_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False, comment="块序号")
    chunk_title = Column(String(512), comment="所属章节标题")
    content = Column(Text, nullable=False, comment="文本内容")
    embedding = Column(Vector(settings.EMBEDDING_DIM), comment="dense向量")
    metadata_ = Column("metadata", JSONB, default=dict, comment="元数据")
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))

    # 反向关联
    document = relationship("Document", back_populates="chunks", lazy="raise")
