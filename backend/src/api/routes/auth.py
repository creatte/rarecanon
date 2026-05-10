"""认证接口：注册 / 登录 / 刷新令牌 / 当前用户"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from ...core.database import async_session
from ...core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from ...models import User
from ...schemas import UserCreate, UserLogin, UserResponse, TokenResponse, RefreshRequest
from ..deps import get_current_user

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate):
    """用户注册：创建账号 → 返回 access + refresh token"""
    async with async_session() as session:
        # 检查用户名或邮箱是否已存在
        existing = await session.execute(
            select(User).where((User.username == body.username) | (User.email == body.email))
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="用户名或邮箱已被注册",
            )

        # 创建用户，密码哈希存储
        user = User(
            username=body.username,
            email=body.email,
            password=hash_password(body.password),
            role=body.role,
            hospital=body.hospital,
            department=body.department,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # 签发令牌
        payload = {"sub": str(user.id), "username": user.username, "role": user.role}
        access = create_access_token(payload)
        refresh = create_refresh_token(payload)

        return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin):
    """用户登录：验证密码 → 返回 access + refresh token"""
    async with async_session() as session:
        # 支持用户名或邮箱登录
        result = await session.execute(
            select(User).where((User.username == body.username) | (User.email == body.username))
        )
        user = result.scalars().first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
            )

        if not verify_password(body.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
            )

        # 签发令牌
        payload = {"sub": str(user.id), "username": user.username, "role": user.role}
        access = create_access_token(payload)
        refresh = create_refresh_token(payload)

        return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest):
    """刷新令牌：用 refresh_token 换新的 access_token"""
    payload = decode_token(body.refresh_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="refresh_token 无效或已过期",
        )
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="仅接受 refresh_token，请使用 /login 获取",
        )

    # 只签发新的 access_token，refresh_token 保持不变（简单策略）
    sub_payload = {"sub": payload["sub"], "username": payload["username"], "role": payload["role"]}
    new_access = create_access_token(sub_payload)

    return TokenResponse(access_token=new_access, refresh_token=body.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    """当前用户信息：需要 Authorization: Bearer <access_token>"""
    return user
