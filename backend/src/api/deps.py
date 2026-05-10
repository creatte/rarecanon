"""FastAPI 依赖注入：获取当前用户"""
from fastapi import Header, HTTPException, status
from sqlalchemy import select

from ..core.database import async_session
from ..core.security import decode_token
from ..models import User


async def get_current_user(authorization: str = Header(..., alias="Authorization")) -> User:
    """从请求头 Authorization: Bearer <token> 中解析并验证用户

    用法：在路由函数签名中添加 `user: User = Depends(get_current_user)`
    """
    # 检查 Bearer 前缀
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization 头格式错误，应为 'Bearer <token>'",
        )
    token = authorization[7:]  # 去掉 "Bearer "

    # 解码验证
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token 无效或已过期",
        )
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要 access_token，请使用 /login 获取",
        )

    # 查数据库确认用户仍存在
    user_id = payload.get("sub")
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被删除",
        )

    return user
