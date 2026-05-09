"""一键入库：读取 processed 目录下所有 .md，向量化写入 pgvector"""
import asyncio
import sys
sys.path.insert(0, ".")

from src.core.database import init_db
from src.rag.ingestion import ingest_directory


async def main():
    print("初始化数据库...")
    await init_db()
    print("开始入库...")
    total = await ingest_directory("backend/data/processed")
    print(f"\n完成，共入库 {total} 个 chunk")


if __name__ == "__main__":
    asyncio.run(main())
