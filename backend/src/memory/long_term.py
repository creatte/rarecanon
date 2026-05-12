"""长期记忆 —— PostgreSQL + pgvector

会话归档 → LLM 生成摘要 → 向量化 → 存入 long_term_memories 表
新会话开始时用当前 query 做向量检索，召回历史相关记忆
"""
import logging
from langchain_openai import ChatOpenAI
from sqlalchemy import select
from ..core.database import async_session
from ..core.config import settings
from ..models import LongTermMemory
from ..rag.embedding import embedding_service

logger = logging.getLogger("agent")

SUMMARY_PROMPT = """请用 1-2 句话总结以下对话的核心医学内容，只提取诊断相关的关键信息：

{messages}

总结："""


class LongTermMemoryManager:

    async def store(self, user_id: str, content: str, metadata: dict | None = None) -> None:
        """存入一条长期记忆（自动向量化）"""
        vec = embedding_service.encode_dense([content])[0]
        async with async_session() as s:
            mem = LongTermMemory(
                user_id=user_id,
                content=content,
                embedding=vec.tolist(),
                metadata_=metadata or {},
            )
            s.add(mem)
            await s.commit()
        logger.debug("长期记忆已存储: %.100s", content)

    async def summarize_and_store(self, user_id: str, conv_id: str, messages: list[dict]) -> str:
        """从对话历史生成摘要并存储"""
        text = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in messages[-20:])
        llm = ChatOpenAI(
            model=settings.LLM_MODEL, api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL, temperature=0,
        )
        summary = llm.invoke(SUMMARY_PROMPT.format(messages=text), max_tokens=256).content.strip()
        await self.store(user_id, summary, {"conv_id": conv_id})
        return summary

    async def recall(self, user_id: str, query: str, top_k: int = 5) -> list[str]:
        """向量检索最相关的历史记忆"""
        query_vec = embedding_service.encode_dense([query])[0]
        async with async_session() as s:
            result = await s.execute(
                select(LongTermMemory.content)
                .where(LongTermMemory.user_id == user_id)
                .order_by(LongTermMemory.embedding.cosine_distance(query_vec.tolist()))
                .limit(top_k)
            )
            memories = [row[0] for row in result.all()]
        logger.debug("召回 %d 条长期记忆", len(memories))
        return memories
