"""对话接口测试"""
import pytest


async def _ensure_user(client):
    """注册 + 登录，设置 auth header，返回 token"""
    await client.post("/api/v1/auth/register", json={
        "username": "chatter",
        "password": "test123456",
        "email": "c@c.com",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "username": "chatter", "password": "test123456",
    })
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return token


@pytest.mark.asyncio
async def test_full_flow(client):
    """创建会话 → 发诊断消息 → 拿到结果"""
    await _ensure_user(client)

    # 创建会话
    resp = await client.post("/api/v1/conversations", json={"title": "测试诊断"})
    assert resp.status_code == 201
    conv_id = resp.json()["id"]

    # 发送消息
    resp = await client.post(
        f"/api/v1/chat/{conv_id}",
        json={"message": "患者男12岁，进行性双下肢肌无力2年，Gower征阳性，CK显著升高15000U/L"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["conv_id"] == conv_id
    assert len(data["final_response"]) > 0

    # 查看会话列表
    resp = await client.get("/api/v1/conversations")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 1
