"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FastAPI 应用入口

生命周期：启动时建表 + 加载模型 → 运行时处理请求 → 关闭时释放引擎
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..core.config import settings
from ..core.database import engine, init_db
from .middleware import AuthMiddleware
from .routes import api_router


# ── 生命周期 ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动：初始化数据库（建扩展 + 建表）；关闭：释放连接池"""
    print(f"[INIT] {settings.APP_NAME} v{settings.APP_VERSION} 启动中...")
    await init_db()
    print(f"[READY] 应用已启动，监听 http://localhost:8000")
    yield
    print("[STOP] 应用关闭，释放数据库连接...")
    await engine.dispose()


# ── 应用实例 ──
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="罕见病知识库 RAG 服务，基于 pgvector 向量检索",
    lifespan=lifespan,
)

# ── CORS 中间件 ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],             # 生产环境改为具体域名，如 ["https://rarecanon.com"]
    allow_credentials=True,
    allow_methods=["*"],             # GET / POST / PUT / DELETE / PATCH
    allow_headers=["*"],             # Authorization, Content-Type 等
)

# ── 全局认证兜底 ──
app.add_middleware(AuthMiddleware)

# ── 路由注册 ──
app.include_router(api_router, prefix="/api/v1")


# ── 健康检查 ──
@app.get("/health", tags=["系统"])
async def health_check():
    """K8s 就绪探针 / 负载均衡健康检查"""
    return {"status": "ok", "version": settings.APP_VERSION}
