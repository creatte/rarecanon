"""RAG 检索接口"""
from fastapi import APIRouter, Query

from ...core.database import async_session
from ...core.config import settings
from ...rag.retrieval import hybrid_search

router = APIRouter()


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, description="查询文本"),
    top_k: int = Query(default=None, ge=1, le=50, description="返回条数"),
    threshold: float = Query(default=None, ge=0.0, le=1.0, description="相似度阈值"),
):
    """语义检索：输入问题 → pgvector 余弦距离召回 → sparse 重排 → 返回 top_k"""
    if top_k is None:
        top_k = settings.RAG_TOP_K
    if threshold is None:
        threshold = settings.RAG_SIMILARITY_THRESHOLD

    async with async_session() as session:
        results = await hybrid_search(session, q, top_k=top_k, threshold=threshold)

    return {
        "query": q,
        "total": len(results),
        "results": results,
    }
