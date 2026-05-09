from src.rag.ingestion import ingest_directory
import argparse
import asyncio
import os

if __name__ == "__main__":
    # parser = argparse.ArgumentParser()
    # parser.add_argument("--input_dir", type=str, required=True)
    # args = parser.parse_args()
    # ingest_directory(args.input_dir)

    input_dir = r"./data/processed/"
    asyncio.run(ingest_directory(input_dir))