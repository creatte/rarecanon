"""全局认证中间件 —— Depends 的兜底，防止新路由遗漏认证"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from ..deps import decode_token  # noqa: E402 — 复用现有的 JWT 解码


# 白名单路径（不需要认证）
WHITELIST = {
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/docs",
    "/openapi.json",
    "/redoc",
}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # 白名单放行
        path = request.url.path.rstrip("/")
        if path in WHITELIST or path.startswith("/docs") or path.startswith("/redoc") or path.startswith("/openapi"):
            return await call_next(request)

        # CORS 预检放行
        if request.method == "OPTIONS":
            return await call_next(request)

        # 检查 JWT
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "未提供认证令牌"})

        token = auth[7:]
        payload = decode_token(token)
        if payload is None:
            return JSONResponse(status_code=401, content={"detail": "令牌无效或已过期"})

        # 存入 request.state，路由里可以通过 request.state.user_id 拿到
        request.state.user_id = payload.get("sub")
        return await call_next(request)
