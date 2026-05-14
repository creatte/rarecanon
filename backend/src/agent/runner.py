"""Agent 运行器 —— 编排记忆 + 会话 + 推理

职责：
  请求前：加载对话历史（短期）+ 召回长期记忆 → 拼入 Agent 上下文
  请求后：双写用户消息和 AI 回复到 Redis + PG
"""
import logging
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from .graph import graph
from ..session.manager import SessionManager

logger = logging.getLogger("agent")


class AgentRunner:
    """Agent 入口，封装记忆加载和消息持久化"""

    def __init__(self):
        self._session = SessionManager()

    async def _build_state(self, user_id: str, conv_id: str, user_message: str) -> dict:
        """构建 Agent 输入状态（steps 1-5）"""
        await self._session.ensure_exists(user_id, conv_id)
        history = await self._session.get_history(conv_id)
        memories = await self._session._ltm.recall(user_id, user_message)

        messages = []
        if memories:
            context = "【历史相关病例记忆】\n" + "\n".join(f"- {m}" for m in memories)
            messages.append(SystemMessage(content=context))
        for h in history:
            if h["role"] == "user":
                messages.append(HumanMessage(content=h["content"]))
            else:
                messages.append(AIMessage(content=h["content"]))
        messages.append(HumanMessage(content=user_message))

        await self._session.add_message(conv_id, "user", user_message)
        return {"messages": messages, "iteration": 0}

    async def run(self, user_id: str, conv_id: str, user_message: str) -> dict:
        """非流式推理（兼容旧调用）"""
        state = await self._build_state(user_id, conv_id, user_message)
        result = await graph.ainvoke(state)

        final = result.get("final_response", "")
        if final:
            await self._session.add_message(conv_id, "assistant", final)

        logger.info("Agent 推理完成: intent=%s verified=%s", result.get("intent"), result.get("verified"))
        return {
            "final_response": final,
            "intent": result.get("intent", "inquiry"),
            "verified": result.get("verified", False),
        }

    async def run_stream(self, user_id: str, conv_id: str, user_message: str):
        """流式推理：边生成边 yield token"""
        state = await self._build_state(user_id, conv_id, user_message)

        final_text = ""
        meta = {"intent": "inquiry", "verified": False}
        streaming = False  # 只跟踪最终生成节点的 LLM 流

        async for event in graph.astream_events(state, version="v2"):
            kind = event["event"]
            name = event.get("name", "")

            # 进入最终生成节点 → 开始捕获 token
            if kind == "on_chain_start" and name in ("generate_final", "reply_inquiry"):
                streaming = True

            # 离开最终生成节点 → 停止捕获
            if kind == "on_chain_end" and name in ("generate_final", "reply_inquiry"):
                streaming = False
                output = event["data"].get("output", {})
                if isinstance(output, dict):
                    meta["verified"] = output.get("verified", meta["verified"])
                    if output.get("final_response"):
                        final_text = output["final_response"]

            # LLM token 流（只在最终生成节点时才推送）
            if kind == "on_chat_model_stream" and streaming:
                chunk = event["data"]["chunk"]
                if chunk.content:
                    final_text += chunk.content
                    yield {"type": "token", "content": chunk.content}

        # 保存到数据库
        if final_text:
            await self._session.add_message(conv_id, "assistant", final_text)

        # 从最终状态拿 intent
        try:
            final_state = await graph.aget_state()
            if final_state.values:
                meta["intent"] = final_state.values.get("intent", meta["intent"])
        except Exception:
            pass

        yield {"type": "done", "intent": meta["intent"], "verified": meta["verified"]}
