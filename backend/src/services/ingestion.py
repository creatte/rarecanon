"""文档入库：切分 → 向量化 → 写入 pgvector"""
import json
import re
import os
from pathlib import Path

import numpy as np
from sqlalchemy import text

from ..core.config import settings
from ..core.database import async_session, Document, init_db
from .embedding import embedding_service


def chunk_markdown(text: str, source: str) -> list[dict]:
    """按 ## 标题切分，保持段落完整性"""
    chunks = []
    # 按二级标题分割
    sections = re.split(r'\n(?=## )', text)
    current_title = ""
    for section in sections:
        section = section.strip()
        if not section:
            continue
        # 提取标题
        title_match = re.match(r'## (.+)', section)
        if title_match:
            current_title = title_match.group(1).strip()
        # 如果段落过长，按字数再切
        if len(section) > settings.RAG_CHUNK_SIZE:
            sub_chunks = _split_long_section(section, settings.RAG_CHUNK_SIZE, settings.RAG_CHUNK_OVERLAP)
        else:
            sub_chunks = [section]
        for i, sc in enumerate(sub_chunks):
            chunks.append({
                "source": source,
                "chunk_index": i,
                "title": current_title,
                "content": sc.strip(),
            })
    return chunks


def _split_long_section(text: str, chunk_size: int, overlap: int) -> list[str]:
    """长段落按字数滑动窗口切分"""
    if len(text) <= chunk_size:
        return [text]
    result = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        # 在句号处切割，避免断句
        if end < len(text):
            for sep in "。！？\n":
                last_sep = text.rfind(sep, start + chunk_size // 2, end)
                if last_sep > 0:
                    end = last_sep + 1
                    break
        result.append(text[start:end])
        start = end - overlap if end < len(text) else end
    return result


async def ingest_file(file_path: str) -> int:
    """入库单个 markdown 文件，返回 chunk 数量"""
    await init_db()
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
    source = Path(file_path).name
    chunks = chunk_markdown(text, source)
    if not chunks:
        return 0

    contents = [c["content"] for c in chunks]
    dense_vecs = embedding_service.encode_dense(contents)

    async with async_session() as session:
        for chunk, vec in zip(chunks, dense_vecs):
            doc = Document(
                source=chunk["source"],
                chunk_index=chunk["chunk_index"],
                title=chunk["title"],
                content=chunk["content"],
                embedding=vec.tolist(),
            )
            session.add(doc)
        await session.commit()
    return len(chunks)


async def ingest_directory(dir_path: str) -> int:
    """遍历目录，入库所有 .md 文件"""
    total = 0
    for root, _, files in os.walk(dir_path):
        for f in files:
            if f.endswith(".md"):
                path = os.path.join(root, f)
                n = await ingest_file(path)
                total += n
                print(f"  {f}: {n} chunks")
    return total
