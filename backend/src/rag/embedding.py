"""
BGE-M3 嵌入服务，基于 FlagEmbedding（官方推理库）

BGE-M3 同时产出两种表示：
  1. Dense（稠密向量）：1024 维，用于 pgvector 余弦相似度检索
  2. Sparse（稀疏词权重）：{词: 权重} 字典，用于精确术语匹配重排
"""
import numpy as np
from FlagEmbedding import BGEM3FlagModel
from modelscope import snapshot_download
from ..core.config import settings


class EmbeddingService:
    """BGE-M3 嵌入服务（单例模式）"""

    _instance: "EmbeddingService | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def _load(self):
        """延迟加载模型"""
        if self._loaded:
            return

        model_dir = snapshot_download(settings.EMBEDDING_LOCAL_MODEL)
        print(f"[OK] Model downloaded to: {model_dir}")
        self.model = BGEM3FlagModel(
            model_dir,
            use_fp16=False,
            device=settings.EMBEDDING_DEVICE,
        )
        self._loaded = True
        print("[OK] Model loaded successfully")

    @property
    def dim(self) -> int:
        return settings.EMBEDDING_DIM

    def encode_dense(self, texts: list[str]) -> np.ndarray:
        """Dense 稠密向量，已 L2 归一化，shape (n, 1024)"""
        self._load()
        output = self.model.encode(
            texts,
            return_dense=True,
            return_sparse=False,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
        )
        return output["dense_vecs"]

    def encode_sparse(self, texts: list[str]) -> list[dict[str, float]]:
        """Sparse 稀疏词权重，每个元素为 {词: 权重}"""
        self._load()
        output = self.model.encode(
            texts,
            return_dense=False,
            return_sparse=True,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
        )
        weights = output["lexical_weights"]
        if isinstance(weights, dict):
            return [weights]
        return weights

    def encode_both(self, texts: list[str]) -> tuple[np.ndarray, list[dict[str, float]]]:
        """一次性返回 dense + sparse，只做一次前向传播"""
        self._load()
        output = self.model.encode(
            texts,
            return_dense=True,
            return_sparse=True,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
        )
        weights = output["lexical_weights"]
        if isinstance(weights, dict):
            weights = [weights]
        return output["dense_vecs"], weights


embedding_service = EmbeddingService()
