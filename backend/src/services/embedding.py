"""BGE-M3 嵌入服务：dense向量 + sparse词权重"""
import numpy as np
from sentence_transformers import SentenceTransformer

from ..core.config import settings


class EmbeddingService:
    """单例，首次加载模型后常驻内存"""

    _instance: "EmbeddingService | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def _load(self):
        if self._loaded:
            return
        self.model = SentenceTransformer(
            settings.EMBEDDING_LOCAL_MODEL,
            device=settings.EMBEDDING_DEVICE,
        )
        self._loaded = True

    @property
    def dim(self) -> int:
        return settings.EMBEDDING_DIM

    def encode_dense(self, texts: list[str]) -> np.ndarray:
        """返回 dense 向量，shape (n, 1024)"""
        self._load()
        return self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
        )

    def encode_sparse(self, texts: list[str]) -> list[dict[str, float]]:
        """返回 sparse 词权重，每个 dict 形如 {词: 权重}"""
        self._load()
        results = self.model.encode(
            texts,
            return_sparse_embedding=True,
            show_progress_bar=False,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
        )
        if isinstance(results, dict):
            return [results]  # 单条
        return results

    def encode_both(self, texts: list[str]) -> tuple[np.ndarray, list[dict[str, float]]]:
        """一次性返回 dense + sparse"""
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


embedding_service = EmbeddingService()
