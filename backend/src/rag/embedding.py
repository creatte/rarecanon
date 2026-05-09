"""
BGE-M3 嵌入服务

BGE-M3 是一个多功能 Embedding 模型，能同时产出两种表示：
  1. Dense（稠密向量）：1024 维浮点数组，用于 pgvector 余弦相似度检索，负责语义泛化
  2. Sparse（稀疏词权重）：{词: 权重} 字典，用于精确术语匹配，替代传统 BM25

两种表示配合使用：先用 dense 在 pgvector 中粗召回 top-N，再用 sparse 对候选做精细重排。
"""
import numpy as np
from sentence_transformers import SentenceTransformer
from modelscope import snapshot_download
from ..core.config import settings


class EmbeddingService:
    """
    BGE-M3 嵌入服务（单例模式）

    模型首次调用时加载，之后常驻内存，避免重复加载的开销。
    通过 __new__ 实现单例，全局只维护一个模型实例。
    """

    _instance: "EmbeddingService | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def _load(self):
        """延迟加载模型，首次调用 encode 时触发"""
        if self._loaded:
            return

        model_dir = snapshot_download(settings.EMBEDDING_LOCAL_MODEL)
        print(f"✅️模型已下载至: {model_dir}")
        self.model = SentenceTransformer(
            model_dir,
            # settings.EMBEDDING_LOCAL_MODEL,  # 默认 BAAI/bge-m3
            device=settings.EMBEDDING_DEVICE,  # 默认 cpu
            )
        self._loaded = True
        print("✅️模型加载成功")

    @property
    def dim(self) -> int:
        """返回 dense 向量维度，默认 1024"""
        return settings.EMBEDDING_DIM

    def encode_dense(self, texts: list[str]) -> np.ndarray:
        """
        将文本编码为 dense 稠密向量

        用途：存入 pgvector 做余弦相似度检索，或查询时计算距离
        参数：
            texts: 待编码的文本列表
        返回：
            np.ndarray，shape (n, 1024)，已做 L2 归一化
        """
        self._load()
        return self.model.encode(
            texts,
            normalize_embeddings=True,  # L2 归一化，方便直接算余弦相似度
            show_progress_bar=True,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
        )

    def encode_sparse(self, texts: list[str]) -> list[dict[str, float]]:
        """
        将文本编码为 sparse 稀疏词权重

        用途：查询时对 dense 粗召回的候选做精确术语匹配重排
        原理：模型自动识别文本中的关键术语并赋予权重，
              比如 "21-羟化酶缺乏症" 会作为整体获得高权重，而非像 jieba 切碎
        参数：
            texts: 待编码的文本列表
        返回：
            list[dict]，每个 dict 形如 {"21-羟化酶缺乏症": 0.85, "诊断": 0.52, ...}
        """
        self._load()
        results = self.model.encode(
            texts,
            return_sparse_embedding=True,  # 启用 sparse 输出头
            show_progress_bar=False,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
        )
        # 单条输入时返回的是 dict 而不是 list，统一包装为 list
        if isinstance(results, dict):
            return [results]
        return results

    def encode_both(self, texts: list[str]) -> tuple[np.ndarray, list[dict[str, float]]]:
        """
        一次性编码为 dense + sparse，避免重复前向传播

        适用于文档入库时同时需要两种表示的场景（虽然本项目 sparse 不入库，
        但保留此接口方便后续扩展，比如入库时预计算 sparse 做离线分析）
        参数：
            texts: 待编码的文本列表
        返回：
            (dense_vecs, sparse_weights) 元组
            - dense_vecs: np.ndarray，shape (n, 1024)
            - sparse_weights: list[dict]，每个 dict 为 {词: 权重}
        """
        self._load()
        dense = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
        )
        sparse = self.model.encode(
            texts,
            return_sparse_embedding=True,
            show_progress_bar=False,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
        )
        if isinstance(sparse, dict):
            sparse = [sparse]
        return dense, sparse


# 全局单例，直接 import 即用：from .embedding import embedding_service
embedding_service = EmbeddingService()
