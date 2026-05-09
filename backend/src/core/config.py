"""应用配置，从 .env 读取"""
from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv
load_dotenv("../.env")

class Settings(BaseSettings):
    # ── 应用 ──
    APP_NAME: str = os.getenv("APP_NAME", "RareCanon")
    APP_VERSION: str = os.getenv("APP_VERSION", "0.1.0")
    DEBUG: bool = os.getenv("DEBUG", False)
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ── 数据库 ──
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = os.getenv("POSTGRES_PORT", 5432)
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "rarecanon")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "rarecanon")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    DB_POOL_SIZE: int = os.getenv("DB_POOL_SIZE", 10)
    DB_MAX_OVERFLOW: int = os.getenv("DB_MAX_OVERFLOW", 20)

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Embedding ──
    EMBEDDING_MODE: str = os.getenv("EMBEDDING_MODE", "local")
    EMBEDDING_LOCAL_MODEL: str = os.getenv("EMBEDDING_LOCAL_MODEL", "BAAI/bge-m3")
    EMBEDDING_DEVICE: str = os.getenv("EMBEDDING_DEVICE", "cpu")
    EMBEDDING_DIM: int = os.getenv("EMBEDDING_DIM", 1024)
    EMBEDDING_SPARSE_WEIGHT: float = os.getenv("EMBEDDING_SPARSE_WEIGHT", 0.3)
    EMBEDDING_BATCH_SIZE: int = os.getenv("EMBEDDING_BATCH_SIZE", 32)

    # ── LLM ──
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek-chat")
    LLM_TEMPERATURE: float = os.getenv("LLM_TEMPERATURE", 0.1)
    LLM_MAX_TOKENS: int = os.getenv("LLM_MAX_TOKENS", 4096)

    # ── RAG ──
    RAG_TOP_K: int = os.getenv("RAG_TOP_K", 8)
    RAG_SIMILARITY_THRESHOLD: float = os.getenv("RAG_SIMILARITY_THRESHOLD", 0.7)
    RAG_CHUNK_SIZE: int = os.getenv("RAG_CHUNK_SIZE", 800)
    RAG_CHUNK_OVERLAP: int = os.getenv("RAG_CHUNK_OVERLAP", 100)

    # ── 路径 ──
    DATA_PROCESSED_DIR: str = os.getenv("DATA_PROCESSED_DIR", "backend/data/processed")

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
