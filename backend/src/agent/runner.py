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

    async def run(self, user_id: str, conv_id: str, user_message: str) -> dict:
        """
        执行一次 Agent 推理。

        Returns:
            {"final_response": str, "intent": str, "verified": bool}
        """
        # 1. 确保会话存在（新会话自动创建）
        await self._session.ensure_exists(user_id, conv_id)

        # 2. 加载对话历史（短期记忆）
        history = await self._session.get_history(conv_id)

        # 3. 召回长期记忆
        memories = await self._session._ltm.recall(user_id, user_message)

        # 4. 拼接消息列表（旧在前，当前用户消息在最后）
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

        # 5. 保存用户消息
        await self._session.add_message(conv_id, "user", user_message)

        # 6. 运行 Agent
        state = {"messages": messages, "iteration": 0}
        result = await graph.ainvoke(state)

        # 7. 保存 AI 回复
        final = result.get("final_response", "")
        if final:
            await self._session.add_message(conv_id, "assistant", final)

        logger.info("Agent 推理完成: intent=%s verified=%s", result.get("intent"), result.get("verified"))
        return {
            "final_response": final,
            "intent": result.get("intent", "inquiry"),
            "verified": result.get("verified", False),
        }
