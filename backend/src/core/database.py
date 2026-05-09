"""数据库连接与表定义"""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from pgvector.sqlalchemy import Vector

from .config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Document(Base):
    """文档元数据表"""
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    filename = Column(String(500), nullable=False, comment="来源文件名")
    title = Column(String(500), comment="文档标题")
    status = Column(String(20), nullable=False, default="completed", comment="处理状态")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DocumentChunk(Base):
    """文档分块表：存文本 + dense向量"""
    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("doc_id", "chunk_index"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    doc_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False, comment="块序号")
    chunk_title = Column(String(512), comment="所属章节标题")
    content = Column(Text, nullable=False, comment="文本内容")
    embedding = Column(Vector(settings.EMBEDDING_DIM), comment="dense向量")
    metadata_ = Column("metadata", JSONB, default=dict, comment="元数据")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


async def init_db():
    """创建 pgvector 扩展和表"""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    print("✅️Database initialized successfully")
