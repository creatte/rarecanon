"""数据库连接与文档表定义"""
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from pgvector.sqlalchemy import Vector
from datetime import datetime, timezone

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
    """文档块表：存文本 + dense向量"""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(256), nullable=False, comment="来源文件")
    chunk_index = Column(Integer, nullable=False, comment="块序号")
    title = Column(String(512), comment="所属章节标题")
    content = Column(Text, nullable=False, comment="文本内容")
    embedding = Column(Vector(settings.EMBEDDING_DIM), comment="dense向量")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


async def init_db():
    """创建 pgvector 扩展和表"""
    async with engine.begin() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.run_sync(Base.metadata.create_all)
