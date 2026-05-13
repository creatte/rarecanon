"""Pytest fixtures"""
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from src.api.main import app


@pytest_asyncio.fixture
async def client():
    """异步 HTTP 测试客户端"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
