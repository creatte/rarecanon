"""对话接口：SSE 流式返回 —— 真正的边生成边推送"""
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ...agent.runner import AgentRunner
from ...models import User
from ..deps import get_current_user

router = APIRouter()
_runner = AgentRunner()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000, description="用户消息")


async def _stream(conv_id: str, message: str, user_id: str):
    """SSE 生成器：Agent 边推理边推送 token"""
    try:
        async for event in _runner.run_stream(user_id, conv_id, message):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"


@router.post("/{conv_id}")
async def chat(conv_id: str, body: ChatRequest, user: User = Depends(get_current_user)):
    """SSE 流式对话接口"""
    return StreamingResponse(
        _stream(conv_id, body.message, str(user.id)),
        media_type="text/event-stream",
    )
