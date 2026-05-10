"""数据库连接与表定义（纯基础设施，不含业务模型）"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

from .config import settings

# ── 引擎 ──
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
)

# ── Session 工厂 ──
async_session = async_sessionmaker(engine, expire_on_commit=False)


# ── ORM 基类 ──
class Base(DeclarativeBase):
    """所有 ORM 模型继承此类，类定义时自动注册到 Base.metadata"""
    pass


async def init_db():
    """创建 pgvector 扩展和所有 ORM 表"""
    # 确保所有模型已导入（否则 Base.metadata 是空的）
    from .. import models as _  # noqa: F401

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    print("[OK] Database initialized successfully")
