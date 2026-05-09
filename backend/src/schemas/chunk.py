"""服务间传递的数据结构，与 ORM / 接口层解耦"""
from typing import TypedDict


class Chunk(TypedDict):
    """切割后的文本块"""
    source: str
    chunk_index: int
    title: str
    content: str


class SearchResult(TypedDict):
    """检索结果"""
    content: str
    title: str
    score: float
