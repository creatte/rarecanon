"""Agent 节点函数"""
import json
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage
from ..core.config import settings
from ..core.database import async_session
from .state import DiagnosticState
from .prompt import USER_INTENT, QUERY_REWRITE, DIFFERENTIAL_DIAGNOSIS, VERIFY_DIAGNOSIS, FINAL_RESPONSE, INQUIRY_RESPONSE
from ..rag.retrieval import hybrid_search

logger = logging.getLogger("agent")

# ── 关键词规则 ──
INQUIRY_KEYWORDS = [
    "有什么症状", "什么症状", "症状是什么", "症状有哪些",
    "怎么治疗", "如何治疗", "治疗方案", "能治好吗",
    "病因", "是什么原因", "为什么会得",
    "诊断标准", "如何诊断", "怎么确诊",
    "什么是", "是什么病", "是什么",
]

DIAGNOSE_KEYWORDS = [
    "什么病", "得了什么", "是什么毛病",
    "可能是什么", "会不会是",
    "帮忙看看", "帮我判断", "帮我诊断", "看看是什么",
    "怎么回事", "什么原因", "这是什么情况",
    "不舒服", "难受", "帮我分析",
]

# ── LLM 客户端 ──
_llm: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    """全局单例，共享底层连接池"""
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            temperature=0,
        )
    return _llm


def _get_user_message(state: DiagnosticState) -> str:
    """从消息历史中取最后一条用户消息"""
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage):
            return m.content
    return ""


def _debug_log(label: str, content: str) -> None:
    """AGENT_DEBUG=true 时输出 DEBUG 日志到控制台，不影响 token 消耗"""
    if not settings.AGENT_DEBUG:
        return
    logger.debug("\n【%s】\n%s", label, content)


# ── 节点 ──

def classify_intent(state: DiagnosticState) -> dict:
    """入口节点：判断用户意图 → inquiry 还是 diagnose"""
    userMsg = _get_user_message(state)
    if not userMsg:
        return {"intent": "inquiry"}

    # 1. 关键词匹配（仅第一轮，回退轮直接走 LLM）
    if state["iteration"] == 0:
        for kw in DIAGNOSE_KEYWORDS:
            if kw in userMsg:
                _debug_log("意图分类", f"diagnose（关键词命中: {kw}）")
                return {"intent": "diagnose"}
        for kw in INQUIRY_KEYWORDS:
            if kw in userMsg:
                _debug_log("意图分类", f"inquiry（关键词命中: {kw}）")
                return {"intent": "inquiry"}

    # 2. LLM fallback
    llm = _get_llm()
    result = llm.invoke(USER_INTENT.format(user_message=userMsg), max_tokens=32).content.strip().lower()
    intent = "diagnose" if "diagnose" in result else "inquiry"
    _debug_log("意图分类", f"{intent}（LLM 判断: {result}）")
    return {"intent": intent}


def rewrite_query(state: DiagnosticState) -> dict:
    """查询改写节点：去噪 + 同义扩展，产出检索 query"""
    userMsg = _get_user_message(state)
    llm = _get_llm()
    result = llm.invoke(QUERY_REWRITE.format(user_message=userMsg), max_tokens=128).content.strip()
    _debug_log("查询改写", result)
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
    _debug_log("检索结果", summary)
    return {"retrieved_docs": docs}


def diagnose(state: DiagnosticState) -> dict:
    """鉴别诊断节点：原始症状 + 知识库证据 → 候选疾病列表"""
    userMsg = _get_user_message(state)
    docs = "\n---\n".join(state["retrieved_docs"]) if state["retrieved_docs"] else "无相关资料"
    llm = _get_llm()
    result = llm.invoke(
        DIFFERENTIAL_DIAGNOSIS.format(user_message=userMsg, retrieved_docs=docs),
        max_tokens=2048,
    ).content
    _debug_log("鉴别诊断", result)
    return {"diagnosis": result}


def verify(state: DiagnosticState) -> dict:
    """验证节点：审查诊断结论，失败则指出回退位置"""
    userMsg = _get_user_message(state)
    docs = "\n---\n".join(state["retrieved_docs"]) if state["retrieved_docs"] else "无"
    llm = _get_llm()
    result = llm.invoke(
        VERIFY_DIAGNOSIS.format(
            user_message=userMsg,
            intent=state["intent"],
            retrieved_docs=docs,
            diagnosis=state["diagnosis"],
        ),
        max_tokens=256,
    ).content

    # 解析 JSON，处理 LLM 可能包裹的 markdown 代码块
    try:
        raw = result.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("\n```", 1)[0]
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("验证节点 JSON 解析失败，默认放行: %s", result[:200])
        return {"verified": True, "feedback": "解析失败，默认通过"}

    verified = data.get("verified", False)
    intentCorrect = data.get("intent_correct", True)
    feedback = data.get("feedback", "")

    # intent 不对 → need_more_info=false，回到入口重判意图
    # 证据不足 → need_more_info=true，回到 rewrite_query 重查
    needMore = not intentCorrect

    _debug_log("验证结果", f"verified={verified} intent_correct={intentCorrect} feedback={feedback}")
    return {
        "verified": verified,
        "need_more_info": needMore,
        "feedback": feedback,
    }


def generate_final(state: DiagnosticState) -> dict:
    """最终回复节点：诊断结论 → 用户可读回复"""
    userMsg = _get_user_message(state)
    llm = _get_llm()
    result = llm.invoke(
        FINAL_RESPONSE.format(user_message=userMsg, diagnosis=state["diagnosis"]),
        max_tokens=1024,
    ).content
    _debug_log("最终回复", result)
    return {
        "final_response": result,
        "messages": [AIMessage(content=result)],
    }


def reply_inquiry(state: DiagnosticState) -> dict:
    """知识咨询回复节点：检索结果 → 直接回答"""
    userMsg = _get_user_message(state)
    docs = "\n---\n".join(state["retrieved_docs"]) if state["retrieved_docs"] else "无相关资料"
    llm = _get_llm()
    result = llm.invoke(
        INQUIRY_RESPONSE.format(user_message=userMsg, retrieved_docs=docs),
        max_tokens=1024,
    ).content
    _debug_log("知识咨询回复", result)
    return {
        "final_response": result,
        "messages": [AIMessage(content=result)],
    }
