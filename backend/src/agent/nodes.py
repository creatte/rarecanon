"""Agent 节点函数"""
import logging
from langchain_core.messages import AIMessage
from ..core.database import async_session
from .state import DiagnosticState
from .tools import get_llm, get_user_message, debug_log, parse_json_response, INQUIRY_KEYWORDS, DIAGNOSE_KEYWORDS
from .prompt import USER_INTENT, QUERY_REWRITE, DIFFERENTIAL_DIAGNOSIS, VERIFY_DIAGNOSIS, FINAL_RESPONSE, INQUIRY_RESPONSE, VERIFY_INQUIRY
from ..rag.retrieval import hybrid_search

logger = logging.getLogger("agent")

def classify_intent(state: DiagnosticState) -> dict:
    """入口节点：判断用户意图 → inquiry 还是 diagnose"""
    userMsg = get_user_message(state)
    if not userMsg:
        return {"intent": "inquiry"}

    # 1. 关键词匹配（仅第一轮，回退轮直接走 LLM）
    if state["iteration"] == 0:
        for kw in DIAGNOSE_KEYWORDS:
            if kw in userMsg:
                debug_log("意图分类", f"diagnose（关键词命中: {kw}）")
                return {"intent": "diagnose"}
        for kw in INQUIRY_KEYWORDS:
            if kw in userMsg:
                debug_log("意图分类", f"inquiry（关键词命中: {kw}）")
                return {"intent": "inquiry"}

    # 2. LLM fallback
    llm = get_llm()
    result = llm.invoke(USER_INTENT.format(user_message=userMsg), max_tokens=256).content.strip().lower()
    intent = "diagnose" if "diagnose" in result else "inquiry"
    debug_log("意图分类", f"{intent}（LLM 判断: {result}）")
    return {"intent": intent}


def rewrite_query(state: DiagnosticState) -> dict:
    """查询改写节点：去噪 + 同义扩展，产出检索 query"""
    userMsg = get_user_message(state)
    llm = get_llm()
    result = llm.invoke(QUERY_REWRITE.format(user_message=userMsg), max_tokens=256).content.strip()
    debug_log("查询改写", result)
    return {"symptoms": result}


async def retrieve(state: DiagnosticState) -> dict:
    """RAG 检索节点：用改写后的 query 检索知识库"""
    query = state["symptoms"]
    async with async_session() as session:
        results = await hybrid_search(session, query)
    docs = [r["content"] for r in results]
    summary = f"召回 {len(docs)} 条文档\n" + "\n---\n".join(docs[:3])
    if len(docs) > 3:
        summary += "\n..."
    debug_log("检索结果", summary)
    return {"retrieved_docs": docs}


def diagnose(state: DiagnosticState) -> dict:
    """鉴别诊断节点：原始症状 + 知识库证据 → 候选疾病列表"""
    userMsg = get_user_message(state)
    docs = "\n---\n".join(state["retrieved_docs"]) if state["retrieved_docs"] else "无相关资料"
    llm = get_llm()
    result = llm.invoke(
        DIFFERENTIAL_DIAGNOSIS.format(user_message=userMsg, retrieved_docs=docs),
        max_tokens=2048,
    ).content
    debug_log("鉴别诊断", result)
    return {"diagnosis": result}


def verify(state: DiagnosticState) -> dict:
    """验证节点：审查诊断结论，失败则指出回退位置"""
    userMsg = get_user_message(state)
    docs = "\n---\n".join(state["retrieved_docs"]) if state["retrieved_docs"] else "无"
    llm = get_llm()
    result = llm.invoke(
        VERIFY_DIAGNOSIS.format(
            user_message=userMsg,
            intent=state["intent"],
            retrieved_docs=docs,
            diagnosis=state["diagnosis"],
        ),
        max_tokens=256,
        response_format={"type": "json_object"},
    ).content

    data = parse_json_response(result, {"verified": True, "intent_correct": True, "feedback": "解析失败，默认通过"})
    verified = data.get("verified", False)
    intentCorrect = data.get("intent_correct", True)
    feedback = data.get("feedback", "")

    # intent 不对 → need_more_info=false，回到入口重判意图
    # 证据不足 → need_more_info=true，回到 rewrite_query 重查
    needMore = not intentCorrect

    debug_log("验证结果", f"verified={verified} intent_correct={intentCorrect} feedback={feedback}")
    return {
        "verified": verified,
        "need_more_info": needMore,
        "feedback": feedback,
        "iteration": state["iteration"] + 1 if not verified else state["iteration"],
    }


def generate_final(state: DiagnosticState) -> dict:
    """最终回复节点：诊断结论 → 用户可读回复"""
    userMsg = get_user_message(state)
    llm = get_llm()
    result = llm.invoke(
        FINAL_RESPONSE.format(user_message=userMsg, diagnosis=state["diagnosis"]),
        max_tokens=1024,
    ).content
    debug_log("最终回复", result)
    return {
        "final_response": result,
        "messages": [AIMessage(content=result)],
    }


def reply_inquiry(state: DiagnosticState) -> dict:
    """知识咨询回复节点：检索结果 → 直接回答"""
    userMsg = get_user_message(state)
    docs = "\n---\n".join(state["retrieved_docs"]) if state["retrieved_docs"] else "无相关资料"
    llm = get_llm()
    result = llm.invoke(
        INQUIRY_RESPONSE.format(user_message=userMsg, retrieved_docs=docs),
        max_tokens=1024,
    ).content
    debug_log("知识咨询回复", result)
    return {"final_response": result}


def verify_inquiry(state: DiagnosticState) -> dict:
    """咨询验证节点：检查回复是否基于资料、是否答对问题"""
    userMsg = get_user_message(state)
    docs = "\n---\n".join(state["retrieved_docs"]) if state["retrieved_docs"] else "无"
    llm = get_llm()
    result = llm.invoke(
        VERIFY_INQUIRY.format(
            user_message=userMsg,
            retrieved_docs=docs,
            final_response=state["final_response"],
        ),
        max_tokens=256,
        response_format={"type": "json_object"},
    ).content

    data = parse_json_response(result, {"verified": True, "feedback": "解析失败，默认通过"})
    verified = data.get("verified", False)
    feedback = data.get("feedback", "")
    debug_log("咨询验证", f"verified={verified} feedback={feedback}")
    return {
        "verified": verified,
        "feedback": feedback,
        "messages": [AIMessage(content=state["final_response"])] if verified else [],
        "iteration": state["iteration"] + 1 if not verified else state["iteration"],
    }
