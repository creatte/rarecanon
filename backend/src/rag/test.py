"""
测试 chunk_markdown 切割结果，验证二级标题切分时一级标题是否正确归属。

问题：按 ## 切分时，下一个疾病的一级标题会残留在上一个二级标题的内容末尾，
导致后续 chunk 仍然使用旧疾病名。
"""
import re
import sys
import os

# 确保能导入项目模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from src.core.config import settings
from src.rag.ingestion import chunk_markdown


def write_chunk_report(input_path: str, output_path: str):
    """读取 md 文件，切割后写入报告文件"""
    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()

    source = os.path.basename(input_path)
    chunks = chunk_markdown(text, source)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"源文件: {input_path}\n")
        f.write(f"总 chunk 数: {len(chunks)}\n")
        f.write(f"chunk_size 设置: {settings.RAG_CHUNK_SIZE}\n")
        f.write("=" * 80 + "\n\n")

        for i, c in enumerate(chunks):
            f.write(f"{'─' * 60}\n")
            f.write(f"【Chunk {c['chunk_index']}】\n")
            f.write(f"  标题 (title): {c['title']}\n")
            f.write(f"  来源 (source): {c['source']}\n")
            f.write(f"  内容长度: {len(c['content'])} 字符\n")
            f.write(f"{'─' * 60}\n")
            f.write(c["content"])
            f.write(f"\n{'─' * 60}\n\n")

    # 同时输出到控制台摘要
    print(f"已写入 {len(chunks)} 个 chunk → {output_path}")
    print()
    for c in chunks[:30]:
        print(f"  [{c['chunk_index']:03d}] title={c['title']:<50s}  len={len(c['content'])}")


if __name__ == "__main__":
    import glob
    # 优先用 fixed 版本，其次用 final 版本
    processed_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed")
    candidates = sorted(glob.glob(os.path.join(processed_dir, "*.md")))
    if not candidates:
        candidates = sorted(glob.glob(os.path.join(processed_dir, "*_final.md")))
    if not candidates:
        print(f"在 {processed_dir} 中未找到数据文件")
        sys.exit(1)

    for input_file in candidates:
        output_file = os.path.join(
            os.path.dirname(__file__), "..", "..", "data",
            os.path.basename(input_file).replace(".md", "_chunk_report.txt")
        )
        write_chunk_report(input_file, output_file)
        print()
