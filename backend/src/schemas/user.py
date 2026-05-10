"""用户相关 Pydantic 模型"""
from datetime import datetime
from uuid import UUID
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ── 创建 ──
class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    email: EmailStr = Field(..., max_length=255, description="邮箱")
    password: str = Field(..., min_length=6, max_length=255, description="密码（明文，后端哈希存储）")
    role: str = Field(default="doctor", pattern=r"^(doctor|admin)$", description="角色")
    hospital: Optional[str] = Field(default=None, max_length=100, description="所属医院")
    department: Optional[str] = Field(default=None, max_length=100, description="所属科室")


# ── 更新（全部可选） ──
class UserUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=2, max_length=50)
    email: Optional[EmailStr] = Field(default=None)
    password: Optional[str] = Field(default=None, min_length=6, max_length=255)
    role: Optional[str] = Field(default=None, pattern=r"^(doctor|admin)$")
    hospital: Optional[str] = Field(default=None, max_length=100)
    department: Optional[str] = Field(default=None, max_length=100)


# ── 登录 ──
class UserLogin(BaseModel):
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


# ── 响应 ──
class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    role: str
    hospital: Optional[str] = None
    department: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
    # from_attributes=True 允许直接从 ORM 对象构造，即 UserResponse.model_validate(orm_obj)


# ── Token ──
class TokenResponse(BaseModel):
    access_token: str = Field(..., description="访问令牌（30分钟有效）")
    refresh_token: str = Field(..., description="刷新令牌（7天有效）")
    token_type: str = Field(default="bearer", description="令牌类型")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="已获取的 refresh_token")
