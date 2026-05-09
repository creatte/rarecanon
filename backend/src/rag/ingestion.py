"""文档入库：切分 → 向量化 → 写入 pgvector"""
import re
import os
from pathlib import Path

from ..core.config import settings
from ..core.database import async_session, Document, DocumentChunk, init_db
from ..schemas import Chunk
from .embedding import embedding_service


def chunk_markdown(text: str, source: str) -> list[Chunk]:
    """先按一级标题 # N. 拆成疾病块，每个块内再按 ## 切分章节"""
    chunks = []
    chunk_index = 0

    # 第一步：按 # N. 拆成疾病块（文本前补一个 \n，确保首个标题也能被切出来）
    # '\n(?=# \d+\.)': ‘\n' '(' '?=#' '\d+' '\.' ')'
    disease_blocks = re.split(r'\n(?=# \d+\.)', '\n' + text)
    for block in disease_blocks:
        block = block.strip()
        if not block:
            continue

        # 提取一级标题（必须位于块首）
        # '^# \d+\.\s*(.+)' 匹配 # N. 后面的内容, 并且#必须是开头 \s* 表示可选的空格，\s+表示一个或多个空格 （.* 表示任意字符，包括空格）
        h1_match = re.match(r'^# \d+\.\s*(.+)', block)
        if not h1_match:
            raise ValueError(f"文档 {source} 中发现没有一级标题的段落，内容: {block[:80]}...")
        h1 = h1_match.group(1).strip()
        # 去掉一级标题行，得到疾病正文
        # block.find("\n") 找到第一个换行符的位置，+1 表示跳过换行符，得到疾病正文, 如果找不到换行符，则返回空字符串
        body = block[block.find("\n") + 1:] if "\n" in block else ""

        # 第二步：按 ## 切分章节
        h2 = ""
        for section in re.split(r'\n(?=## )', body):
            section = section.strip()
            if not section:
                continue

            h2_match = re.match(r'## (.+)', section)
            if h2_match:
                h2 = h2_match.group(1).strip()
            # 否则沿用上一个二级标题

            title = f"{h1} - {h2}" if h2 else h1
            content = f"# {h1}\n{section}"

            # 长段落再切
            if len(content) > settings.RAG_CHUNK_SIZE:
                sub_chunks = _split_long_section(content, settings.RAG_CHUNK_SIZE, settings.RAG_CHUNK_OVERLAP)
            else:
                sub_chunks = [content]

            for sc in sub_chunks:
                chunks.append({
                    "source": source,
                    "chunk_index": chunk_index,
                    "title": title,
                    "content": sc.strip(),
                })
                chunk_index += 1

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
            cut = -1
            # 中间作为结束，防止切割的快太过于小了
            search_start = start + chunk_size // 2
            # 逐级降级：句末 → 从句 → 空格 → 硬切
            for seps in ("。！？\n", "，,；;：:", " 　"):
                for sep in seps:
                    pos = text.rfind(sep, search_start, end)
                    if pos > cut:
                        cut = pos
                if cut > 0:
                    end = cut + 1
                    break
        result.append(text[start:end])
        start = end - overlap if end < len(text) else end
    return result


async def ingest_file(file_path: str) -> int:
    """入库单个 markdown 文件，返回 chunk 数量"""
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
    source = Path(file_path).name
    print(f"    读取: {len(text):,} 字符")

    chunks = chunk_markdown(text, source)
    print(f"    切分: {len(chunks)} 个 chunk")
    if not chunks:
        return 0

    contents = [c["content"] for c in chunks]
    print(f"    🔄 向量化中 ({len(contents)} 条)...")
    dense_vecs = embedding_service.encode_dense(contents)
    print(f"    ✅ 向量化完成 ({len(dense_vecs)} 条)")

    print(f"    💾 写入数据库...")
    async with async_session() as session:
        # 1. 创建文档元数据
        doc = Document(filename=source, title=source, status="completed")
        session.add(doc)
        await session.flush()  # 获取 doc.id

        # 2. 批量插入分块
        for chunk, vec in zip(chunks, dense_vecs):
            dc = DocumentChunk(
                doc_id=doc.id,
                chunk_index=chunk["chunk_index"],
                chunk_title=chunk["title"],
                content=chunk["content"],
                embedding=vec.tolist(),
            )
            session.add(dc)
        await session.commit()
    return len(chunks)


async def ingest_directory(dir_path: str) -> int:
    """遍历目录，入库所有 .md 文件"""
    # 只取当前目录下的 md 文件，不递归
    md_files = sorted(
        os.path.join(dir_path, f) for f in os.listdir(dir_path)
        if f.endswith(".md")
    )

    print(f"\n{'='*50}")
    print(f"📂 找到 {len(md_files)} 个 md 文件")
    for f in md_files:
        print(f"   - {f}")
    print(f"{'='*50}\n")

    await init_db()
    total = 0
    for i, path in enumerate(md_files, 1):
        fname = os.path.basename(path)
        print(f"[{i}/{len(md_files)}] 📄 处理: {fname}")
        n = await ingest_file(path)
        total += n
        print(f"  ✅ {fname}: {n} chunks (累计: {total})\n")

    print(f"{'='*50}")
    print(f"🎉 入库完成! 共 {len(md_files)} 文件, {total} chunks")
    print(f"{'='*50}")
    return total
