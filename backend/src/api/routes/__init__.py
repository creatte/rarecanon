"""路由汇总，按模块拆分"""
from fastapi import APIRouter

from .auth import router as auth_router
from .rag import router as rag_router
from .chat import router as chat_router
from .conversation import router as conv_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
api_router.include_router(rag_router, prefix="/rag", tags=["RAG检索"])
api_router.include_router(chat_router, prefix="/chat", tags=["对话"])
api_router.include_router(conv_router, prefix="/conversations", tags=["会话"])

# TODO(5.3): 全局认证中间件
#   - 白名单放行 /auth/*，其余路由统一校验 JWT
#   - 作为 Depends(get_current_user) 的兜底，防止新路由遗漏认证
#   - 开发期非必须，部署前补上
