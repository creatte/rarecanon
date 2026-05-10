"""审计日志表"""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB

from ..core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_user_id", "user_id"),
        # idx_audit_created_at 是 functional index (created_at DESC)，在 init_db.sql 中定义
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="操作人")
    action = Column(String(50), nullable=False, comment="操作类型")
    resource = Column(String(100), comment="操作资源")
    detail = Column(JSONB, comment="操作详情")
    ip_address = Column(String(45), comment="IP地址")
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
