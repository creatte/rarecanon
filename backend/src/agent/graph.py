"""
LangGraph 诊断图组装

两条链路：
  inquiry:  classify_intent → rewrite_query → retrieve → reply_inquiry → verify_inquiry → END
  diagnose: classify_intent → rewrite_query → retrieve → diagnose → verify → generate_final → END
"""
from langgraph.graph import StateGraph, START, END
from .state import DiagnosticState
from .nodes import (
    classify_intent, rewrite_query, retrieve,
    reply_inquiry, verify_inquiry,
    diagnose, verify, generate_final,
)
from .edges import route_by_intent, route_after_verify_inquiry, route_after_verify, route_after_retrieve


builder = StateGraph(DiagnosticState)

# ── 节点注册 ──
builder.add_node("classify_intent", classify_intent)
builder.add_node("rewrite_query", rewrite_query)
builder.add_node("retrieve", retrieve)
# inquiry 链路
builder.add_node("reply_inquiry", reply_inquiry)
builder.add_node("verify_inquiry", verify_inquiry)
# diagnose 链路
builder.add_node("diagnose", diagnose)
builder.add_node("verify", verify)
builder.add_node("generate_final", generate_final)

# ── 入口 ──
builder.add_edge(START, "classify_intent")

# ── 意图分支 ──
builder.add_conditional_edges("classify_intent", route_by_intent, {
    "inquiry": "rewrite_query",
    "diagnose": "rewrite_query",  # 两条链路共用 rewrite_query + retrieve
})

# ── 检索（共用） → 按 intent 分发 ──
builder.add_edge("rewrite_query", "retrieve")
builder.add_conditional_edges("retrieve", route_after_retrieve, {
    "inquiry": "reply_inquiry",
    "diagnose": "diagnose",
})

# ── inquiry 链路 ──
builder.add_edge("reply_inquiry", "verify_inquiry")
builder.add_conditional_edges("verify_inquiry", route_after_verify_inquiry, {
    "end": END,
    "rewrite_query": "rewrite_query",
})

# ── diagnose 链路 ──
builder.add_edge("diagnose", "verify")
builder.add_conditional_edges("verify", route_after_verify, {
    "generate_final": "generate_final",
    "classify_intent": "classify_intent",
    "rewrite_query": "rewrite_query",
})
builder.add_edge("generate_final", END)

graph = builder.compile()
