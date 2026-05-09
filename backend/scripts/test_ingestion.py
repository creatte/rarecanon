"""
测试摄入管线：建表 → 切分 → 向量化 → 写入 → 查询
跑完这个没问题再跑全量 ingestion，避免跑半天才发现 bug
"""
import sys
import os
import asyncio
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.core.config import settings
from src.core.database import async_session, Document, DocumentChunk, init_db, engine
from src.rag.ingestion import chunk_markdown
from src.rag.embedding import embedding_service


TEST_MD = """\
# 1. 测试疾病A

## 概述
这是测试疾病A的概述，用于验证摄入管线是否正常工作。

## 病因
测试疾病A的病因是测试基因突变导致的。

## 治疗
治疗方法包括测试药物和测试疗法。

# 2. 测试疾病B

## 概述
测试疾病B是另一种用于验证的疾病，确保多疾病切换正常。

## 诊断
通过测试指标进行诊断，需要结合临床表现。
"""


async def test_ingestion():
    print(f"配置检查:")
    print(f"  DB: {settings.DATABASE_URL}")
    print(f"  Model: {settings.EMBEDDING_LOCAL_MODEL} ({settings.EMBEDDING_DEVICE})")
    print(f"  Dim: {settings.EMBEDDING_DIM}")
    print(f"  Chunk: {settings.RAG_CHUNK_SIZE} / overlap: {settings.RAG_CHUNK_OVERLAP}")
    print()

    # ── 1. 建表 ──
    print("[1/5] 初始化数据库...")
    await init_db()
    print("  ✅ 表已就绪")
    print()

    # ── 2. 删除旧测试数据 ──
    print("[2/5] 清理旧测试数据...")
    async with async_session() as s:
        from sqlalchemy import text
        await s.execute(text("DELETE FROM document_chunks WHERE doc_id IN (SELECT id FROM documents WHERE filename LIKE 'test_%')"))
        await s.execute(text("DELETE FROM documents WHERE filename LIKE 'test_%'"))
        await s.commit()
    print("  ✅ 已清理")
    print()
    assert 1==2

    # ── 3. 切分 ──
    print("[3/5] 切分测试文本...")
    chunks = chunk_markdown(TEST_MD, "test_sample.md")
    print(f"  ✅ 切分完成: {len(chunks)} 个 chunk")
    for c in chunks:
        print(f"     [{c['chunk_index']:02d}] {c['title'][:60]}")
    print()

    # ── 4. 向量化 + 写入 ──
    print("[4/5] 向量化并写入...")
    contents = [c["content"] for c in chunks]
    print(f"  🔄 编码 {len(contents)} 条...")
    vecs = embedding_service.encode_dense(contents)
    print(f"  ✅ 编码完成, shape={vecs.shape}")

    async with async_session() as s:
        doc = Document(filename="test_sample.md", title="测试样本", status="completed")
        s.add(doc)
        await s.flush()

        for chunk, vec in zip(chunks, vecs):
            s.add(DocumentChunk(
                doc_id=doc.id,
                chunk_index=chunk["chunk_index"],
                chunk_title=chunk["title"],
                content=chunk["content"],
                embedding=vec.tolist(),
            ))
        await s.commit()
    print(f"  ✅ 写入完成: 1 document + {len(chunks)} chunks")
    print()

    # ── 5. 查询验证 ──
    print("[5/5] 查询验证...")
    async with async_session() as s:
        from sqlalchemy import select, func
        # 查文档
        doc_count = (await s.execute(select(func.count()).select_from(Document))).scalar()
        chunk_count = (await s.execute(select(func.count()).select_from(DocumentChunk))).scalar()
        print(f"  documents: {doc_count} 条, document_chunks: {chunk_count} 条")

        # 查测试数据
        test_docs = (await s.execute(
            select(Document).filter(Document.filename == "test_sample.md")
        )).scalars().all()
        for d in test_docs:
            chunks_for_doc = (await s.execute(
                select(DocumentChunk).filter(DocumentChunk.doc_id == d.id).order_by(DocumentChunk.chunk_index)
            )).scalars().all()
            print(f"  📄 {d.filename} (id={d.id}): {len(chunks_for_doc)} chunks")
            for c in chunks_for_doc:
                has_emb = c.embedding is not None
                emb_dim = len(c.embedding) if has_emb else 0
                print(f"     [{c.chunk_index:02d}] {c.chunk_title[:50]:50s}  emb={emb_dim}d  content={len(c.content)}chars")

        # 向量检索功能验证
        query_vec = embedding_service.encode_dense(["测试疾病A 治疗"])[0]
        stmt = (
            select(DocumentChunk)
            .filter(DocumentChunk.embedding.isnot(None))
            .order_by(DocumentChunk.embedding.cosine_distance(query_vec.tolist()))
            .limit(3)
        )
        results = (await s.execute(stmt)).scalars().all()
        print(f"\n  🔍 检索测试: '测试疾病A 治疗' → top 3:")
        for r in results:
            # 数据库返回的是 np.ndarray，需手动算余弦相似度（已 L2 归一化，直接用点积）
            emb = np.array(r.embedding)
            sim = float(np.dot(emb, query_vec))
            print(f"     [{r.chunk_index}] {r.chunk_title[:40]:40s}  sim={sim:.4f}")

    print()
    print("🎉 所有测试通过！可以放心跑全量 ingestion")


if __name__ == "__main__":
    asyncio.run(test_ingestion())
