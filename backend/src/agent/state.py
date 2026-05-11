"""
诊断推理状态定义

State 是 LangGraph 图中所有节点共享的数据总线。
入口节点先判断 intent，再路由到不同子链路：

  intent="inquiry"  →  RAG检索 → 生成回复（知识查询，不需要推理）
  intent="diagnose" →  症状分析 → RAG检索 → 鉴别诊断 → 验证 → 生成回复
                         ↑____________← 验证失败回到检索 ___________|
"""

from typing import Annotated, Literal, TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class DiagnosticState(TypedDict):
    # ── 路由 ──
    intent: Literal["diagnose", "inquiry"]  # inquiry=知识查询, diagnose=诊断推理
    # ── 对话 ──
    messages: Annotated[list[BaseMessage], add_messages]
    # ── 输入 ──
    symptoms: str
    # ── 检索 ──
    retrieved_docs: list[str]
    # ── 推理（仅 diagnose 链路使用） ──
    diagnosis: str
    verified: bool
    need_more_info: bool
    feedback: str  # 验证失败时的反馈，用于下一轮修正
    # ── 输出 ──
    final_response: str
    # ── 控制 ──
    iteration: int
