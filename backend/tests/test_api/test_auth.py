"""认证接口测试"""
import pytest


async def _get_token(client):
    """辅助：注册并登录，返回 token"""
    await client.post("/api/v1/auth/register", json={
        "username": "tester",
        "password": "test123456",
        "email": "t@t.com",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "username": "tester", "password": "test123456",
    })
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_login_success(client):
    resp = await client.post("/api/v1/auth/login", json={
        "username": "tester", "password": "test123456",
    })
    # 可能用户还没注册（先注册）
    if resp.status_code == 401:
        token = await _get_token(client)
        assert token
    else:
        assert resp.status_code == 200
        assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_fail(client):
    resp = await client.post("/api/v1/auth/login", json={
        "username": "nobody", "password": "wrong",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route(client):
    """没 token 不能访问"""
    resp = await client.get("/api/v1/conversations")
    assert resp.status_code != 200


@pytest.mark.asyncio
async def test_register_then_access(client):
    """注册 → 登录 → 访问受保护接口"""
    token = await _get_token(client)
    client.headers["Authorization"] = f"Bearer {token}"
    resp = await client.get("/api/v1/conversations")
    assert resp.status_code == 200
