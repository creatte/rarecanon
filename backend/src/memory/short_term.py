"""短期记忆 —— Redis 滑动窗口

每条会话对应一个 Redis list：
  - key: conv:{conv_id}:messages
  - 值: JSON 序列化的 {"role":"user"/"assistant","content":"..."}
  - 最大保留 20 轮（40 条消息）
  - TTL 2 小时，每次写入续期
"""
import json
from redis.asyncio import Redis
from ..core.config import settings


class ShortTermMemory:
    """Redis 对话记忆"""

    _MAX_ROUNDS = 20
    _MAX_MESSAGES = _MAX_ROUNDS * 2
    _TTL = 7200  # 2 小时

    def __init__(self, redis: Redis | None = None):
        self._redis = redis

    async def _get_client(self) -> Redis:
        if self._redis is not None:
            return self._redis
        self._redis = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True,
        )
        return self._redis

    def _key(self, conv_id: str) -> str:
        return f"conv:{conv_id}:messages"

    async def add_message(self, conv_id: str, role: str, content: str) -> None:
        """存入一条消息，自动裁旧 + 续 TTL"""
        client = await self._get_client()
        key = self._key(conv_id)
        msg = json.dumps({"role": role, "content": content}, ensure_ascii=False)
        await client.lpush(key, msg)
        await client.ltrim(key, 0, self._MAX_MESSAGES - 1)
        await client.expire(key, self._TTL)

    async def get_history(self, conv_id: str) -> list[dict]:
        """按对话顺序返回历史消息（旧在前）"""
        client = await self._get_client()
        msgs = await client.lrange(self._key(conv_id), 0, -1)
        return [json.loads(m) for m in reversed(msgs)]

    async def rebuild(self, conv_id: str, messages: list[dict]) -> None:
        """批量重建对话历史（从 PG 恢复时用），一次 LPUSH + LTRIM + EXPIRE"""
        client = await self._get_client()
        key = self._key(conv_id)
        await client.delete(key)
        if not messages:
            return
        # messages 是旧→新，LPUSH 逐个推入，最后推的（最新）在列表头
        # get_history 用 reversed 读回时就是旧→新，与 add_message 一致
        msgs = [json.dumps(m, ensure_ascii=False) for m in messages]
        await client.lpush(key, *msgs)
        await client.ltrim(key, 0, self._MAX_MESSAGES - 1)
        await client.expire(key, self._TTL)

    async def clear(self, conv_id: str) -> None:
        """清空会话记忆"""
        client = await self._get_client()
        await client.delete(self._key(conv_id))
