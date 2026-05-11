"""条件边：根据 state 决定图流转方向"""
from .state import DiagnosticState


def route_by_intent(state: DiagnosticState) -> str:
    """classify_intent 之后的分叉：inquiry → 咨询链路，diagnose → 诊断链路"""
    return state["intent"]  # "inquiry" 或 "diagnose"


def route_after_verify_inquiry(state: DiagnosticState) -> str:
    """verify_inquiry 之后：通过 → 结束，不通过 → 回到 rewrite_query 重查"""
    if state["verified"] or state["iteration"] >= 2:
        return "end"
    return "rewrite_query"


def route_after_retrieve(state: DiagnosticState) -> str:
    """retrieve 之后：按 intent 分发到对应链路"""
    return state["intent"]  # "inquiry" → reply_inquiry, "diagnose" → diagnose


def route_after_verify(state: DiagnosticState) -> str:
    """verify 之后的三向路由：
    - 通过 → generate_final
    - intent 错了 → classify_intent（重判意图）
    - 证据不足 → rewrite_query（重新检索）
    """
    if state["verified"] or state["iteration"] >= 2:
        return "generate_final"
    # need_more_info=true 表示 intent 不对
    if state["need_more_info"]:
        return "classify_intent"
    return "rewrite_query"
