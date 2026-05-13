"""对话接口：发送消息 → Agent 推理 → 返回结果"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ...agent.runner import AgentRunner
from ...models import User
from ..deps import get_current_user

router = APIRouter()
_runner = AgentRunner()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000, description="用户消息")


class ChatResponse(BaseModel):
    conv_id: str
    intent: str
    verified: bool
    final_response: str


@router.post("/{conv_id}", response_model=ChatResponse)
async def chat(conv_id: str, body: ChatRequest, user: User = Depends(get_current_user)):
    """发送消息，Agent 推理并返回结果"""
    result = await _runner.run(str(user.id), conv_id, body.message)
    if not result["final_response"]:
        raise HTTPException(status_code=500, detail="Agent 未返回有效结果")
    return ChatResponse(
        conv_id=conv_id,
        intent=result["intent"],
        verified=result["verified"],
        final_response=result["final_response"],
    )
