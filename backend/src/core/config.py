"""应用配置，从 .env 读取"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── 应用 ──
    APP_NAME: str = "RareCanon"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── 数据库 ──
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "rarecannon"
    POSTGRES_USER: str = "rarecannon"
    POSTGRES_PASSWORD: str = ""
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Embedding ──
    EMBEDDING_MODE: str = "local"
    EMBEDDING_LOCAL_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DEVICE: str = "cpu"
    EMBEDDING_DIM: int = 1024
    EMBEDDING_SPARSE_WEIGHT: float = 0.3
    EMBEDDING_BATCH_SIZE: int = 32

    # ── LLM ──
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 4096

    # ── RAG ──
    RAG_TOP_K: int = 8
    RAG_SIMILARITY_THRESHOLD: float = 0.7
    RAG_CHUNK_SIZE: int = 800
    RAG_CHUNK_OVERLAP: int = 100

    # ── 路径 ──
    DATA_PROCESSED_DIR: str = "backend/data/processed"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
