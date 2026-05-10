"""用户表"""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, Index, text
from sqlalchemy.dialects.postgresql import UUID

from ..core.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_username", "username"),
        Index("idx_users_email", "email"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    username = Column(String(50), nullable=False, unique=True, comment="用户名")
    email = Column(String(255), nullable=False, unique=True, comment="邮箱")
    password = Column(String(255), nullable=False, comment="密码哈希")
    role = Column(String(20), nullable=False, default="doctor", comment="角色: doctor / admin")
    hospital = Column(String(100), comment="所属医院")
    department = Column(String(100), comment="所属科室")
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
