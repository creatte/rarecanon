"""会话接口：创建 / 列表 / 详情 / 归档 / 删除"""
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update

from ...core.database import async_session
from ...models import Conversation, Message, User
from ...schemas import ConversationCreate, ConversationUpdate, ConversationResponse, ConversationListResponse
from ...session.manager import SessionManager
from ..deps import get_current_user

router = APIRouter()


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conv(body: ConversationCreate, user: User = Depends(get_current_user)):
    """创建新会话"""
    async with async_session() as s:
        conv = Conversation(id=uuid4(), user_id=user.id, title=body.title or "新建会话")
        s.add(conv)
        await s.commit()
        await s.refresh(conv)
        return conv


@router.get("", response_model=ConversationListResponse)
async def list_convs(user: User = Depends(get_current_user)):
    """获取当前用户的所有活跃会话"""
    async with async_session() as s:
        result = await s.execute(
            select(Conversation)
            .where(Conversation.user_id == user.id, Conversation.status == "active")
            .order_by(Conversation.updated_at.desc())
        )
        items = list(result.scalars().all())
        return {"items": items, "total": len(items)}


@router.get("/{conv_id}", response_model=ConversationResponse)
async def get_conv(conv_id: str, user: User = Depends(get_current_user)):
    """获取会话详情"""
    async with async_session() as s:
        result = await s.execute(
            select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user.id)
        )
        conv = result.scalars().first()
        if conv is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        return conv


@router.patch("/{conv_id}", response_model=ConversationResponse)
async def update_conv(conv_id: str, body: ConversationUpdate, user: User = Depends(get_current_user)):
    """更新会话标题或状态"""
    async with async_session() as s:
        result = await s.execute(
            select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user.id)
        )
        conv = result.scalars().first()
        if conv is None:
            raise HTTPException(status_code=404, detail="会话不存在")

        if body.title is not None:
            conv.title = body.title
        if body.status is not None:
            conv.status = body.status
        await s.commit()
        await s.refresh(conv)
        return conv


@router.delete("/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conv(conv_id: str, user: User = Depends(get_current_user)):
    """软删除会话（标记为 deleted）"""
    async with async_session() as s:
        result = await s.execute(
            update(Conversation)
            .where(Conversation.id == conv_id, Conversation.user_id == user.id)
            .values(status="deleted")
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="会话不存在")
        await s.commit()


@router.get("/{conv_id}/messages")
async def get_messages(conv_id: str, user: User = Depends(get_current_user)):
    """获取会话的消息历史"""
    sm = SessionManager()
    print(conv_id)
    print(user.id)
    async with async_session() as s:
        result = await s.execute(
            select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user.id)
        )
        if result.scalars().first() is None:
            raise HTTPException(status_code=404, detail="会话不存在")
    return await sm.get_history(conv_id)
