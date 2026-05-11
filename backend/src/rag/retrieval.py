"""混合检索：dense向量 + sparse词权重，RRF融合"""
import numpy as np
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models import DocumentChunk
from ..schemas import SearchResult
from .embedding import embedding_service


async def hybrid_search(
    session: AsyncSession,
    query: str,
    top_k: int | None = None,
    threshold: float | None = None,
) -> list[SearchResult]:
    """混合检索：dense + sparse → RRF 融合"""
    if top_k is None:
        top_k = settings.RAG_TOP_K
    if threshold is None:
        threshold = settings.RAG_SIMILARITY_THRESHOLD

    # 1. 查询向量化
    query_dense = embedding_service.encode_dense([query])[0]
    query_sparse = embedding_service.encode_sparse([query])[0]
    sparse_weight = settings.EMBEDDING_SPARSE_WEIGHT

    # 2. Dense 检索：pgvector 余弦相似度
    dense_results = await _dense_search(session, query_dense, top_k * 2, threshold)

    # 3. 如果 sparse 有效，做混合打分
    if query_sparse:
        results = _hybrid_score(dense_results, query_sparse, sparse_weight, top_k)
    else:
        results = dense_results[:top_k]

    # 4. 返回纯文本结果
    return [
        {"content": r["content"], "title": r["title"], "score": round(r["score"], 4)}
        for r in results
    ]


async def _dense_search(
    session: AsyncSession, query_vec: np.ndarray, top_k: int, threshold: float
) -> list[dict]:
    """pgvector 余弦相似度检索"""
    stmt = (
        select(DocumentChunk)
        .filter(DocumentChunk.embedding.isnot(None))
        .order_by(DocumentChunk.embedding.cosine_distance(query_vec.tolist()))
        .limit(top_k)
    )
    result = await session.execute(stmt)
    chunks = result.scalars().all()

    items = []
    for c in chunks:
        emb = np.asarray(c.embedding, dtype=np.float64)
        # 向量已 L2 归一化，余弦相似度 = 点积，余弦距离 = 1 - 点积
        cos_dist = 1.0 - float(np.dot(emb, query_vec))
        similarity = 1.0 - cos_dist
        if float(similarity) >= threshold:
            items.append({
                "content": c.content,
                "title": c.chunk_title or "",
                "score": float(similarity),
            })
    return items


def _hybrid_score(
    dense_items: list[dict],
    query_sparse: dict[str, float],
    sparse_weight: float,
    top_k: int,
) -> list[dict]:
    """RRF 融合 dense 和 sparse 分数"""
    # 计算每个文档的 sparse 分数（词重叠）
    for item in dense_items:
        content_lower = item["content"].lower()
        sparse_score = 0.0
        for token, weight in query_sparse.items():
            if token.lower() in content_lower:
                sparse_score += float(weight)
        # 归一化 sparse 分数
        if query_sparse:
            sparse_score = sparse_score / sum(abs(float(w)) for w in query_sparse.values())
        # 加权融合，确保结果为 Python float，避免 numpy 类型泄漏到 JSON 序列化
        item["score"] = float((1 - sparse_weight) * item["score"] + sparse_weight * sparse_score)

    dense_items.sort(key=lambda x: x["score"], reverse=True)
    return dense_items[:top_k]
