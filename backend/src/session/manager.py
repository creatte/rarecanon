"""会话管理器 —— 编排 Redis 短期记忆 + PG 持久存储"""
import logging
from sqlalchemy import select, update, func
from ..core.database import async_session
from ..models import Conversation, Message
from ..memory import ShortTermMemory, LongTermMemoryManager

logger = logging.getLogger("agent")


class SessionManager:

    def __init__(self):
        self._mem = ShortTermMemory()
        self._ltm = LongTermMemoryManager()

    # ── 会话 CRUD ──

    async def create(self, user_id: str, title: str = "新建会话") -> Conversation:
        """创建新会话"""
        async with async_session() as s:
            conv = Conversation(user_id=user_id, title=title)
            s.add(conv)
            await s.commit()
            await s.refresh(conv)
            logger.debug("会话已创建: %s", conv.id)
            return conv

    async def list_by_user(self, user_id: str) -> list[Conversation]:
        """列出用户的所有活跃会话（最近更新优先）"""
        async with async_session() as s:
            result = await s.execute(
                select(Conversation)
                .where(Conversation.user_id == user_id, Conversation.status == "active")
                .order_by(Conversation.updated_at.desc())
            )
            return list(result.scalars().all())

    async def archive(self, conv_id: str) -> None:
        """归档会话 + 生成长期记忆"""
        async with async_session() as s:
            # 查 user_id
            result = await s.execute(
                select(Conversation.user_id).where(Conversation.id == conv_id)
            )
            row = result.first()
            user_id = row[0] if row else None
            # 标记归档
            await s.execute(
                update(Conversation)
                .where(Conversation.id == conv_id)
                .values(status="archived")
            )
            await s.commit()

        # 清 Redis
        await self._mem.clear(conv_id)

        # 生成长期记忆摘要
        if user_id:
            history = await self.get_history(conv_id)
            if history:
                await self._ltm.summarize_and_store(str(user_id), str(conv_id), history)

    async def update_title(self, conv_id: str, title: str) -> None:
        """更新会话标题"""
        async with async_session() as s:
            await s.execute(
                update(Conversation)
                .where(Conversation.id == conv_id)
                .values(title=title)
            )
            await s.commit()

    # ── 消息 ──

    async def add_message(self, conv_id: str, role: str, content: str) -> None:
        """保存消息到 Redis + PG，更新会话时间"""
        # Redis（热缓存）
        await self._mem.add_message(conv_id, role, content)
        # PG（持久）
        async with async_session() as s:
            msg = Message(conv_id=conv_id, role=role, content=content)
            s.add(msg)
            await s.execute(
                update(Conversation)
                .where(Conversation.id == conv_id)
                .values(updated_at=func.now())
            )
            await s.commit()

    async def get_history(self, conv_id: str) -> list[dict]:
        """加载对话历史：Redis 有直接返回，无则从 PG 重建"""
        # 1. 先查 Redis
        redis_history = await self._mem.get_history(conv_id)
        if redis_history:
            return redis_history

        # 2. Redis 过期了，从 PG 恢复最近 20 轮
        async with async_session() as s:
            result = await s.execute(
                select(Message)
                .where(Message.conv_id == conv_id)
                .order_by(Message.created_at.desc())
                .limit(40)
            )
            pg_msgs = list(result.scalars().all())

        if not pg_msgs:
            return []

        # 重建 Redis 缓存（一次性批量写入）
        await self._mem.rebuild(conv_id, [{"role": m.role, "content": m.content} for m in reversed(pg_msgs)])

        return [{"role": m.role, "content": m.content} for m in reversed(pg_msgs)]
