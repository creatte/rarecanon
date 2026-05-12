"""Agent 共享工具函数"""
import json
import logging
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from ..core.config import settings
from .state import DiagnosticState

logger = logging.getLogger("agent")

# ── 日志配置 ──

def setup_logger() -> None:
    """配置 agent 日志：DEBUG 时输出到控制台 + agent/logs/agent.log"""
    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    if logger.handlers:
        return

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    fh = logging.FileHandler(os.path.join(log_dir, "agent.log"), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)


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


def get_llm() -> ChatOpenAI:
    """全局单例，共享底层连接池"""
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            temperature=0.1,
        )
    return _llm


def get_user_message(state: DiagnosticState) -> str:
    """从消息历史中取最后一条用户消息"""
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage):
            return m.content
    return ""


def debug_log(label: str, content: str) -> None:
    """DEBUG=true 时输出日志到控制台，不影响 token 消耗"""
    if not settings.DEBUG:
        return
    logger.debug("\n【%s】\n%s", label, content)


# ── JSON 解析 ──

def parse_json_response(raw: str, defaults: dict | None = None) -> dict:
    """解析 LLM 返回的 JSON 字符串，自动处理 markdown 代码块包裹

    Args:
        raw: LLM 原始返回文本
        defaults: 解析失败时的默认值

    Returns:
        解析后的 dict
    """
    if defaults is None:
        defaults = {"verified": True, "feedback": "解析失败，默认通过"}

    try:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            last_fence = text.rfind("\n```")
            if last_fence != -1:
                text = text[:last_fence]
        return json.loads(text)
    except (json.JSONDecodeError, IndexError, AttributeError):
        logger.warning("JSON 解析失败: %.200s", raw)
        return defaults
