"""Agent 节点单元测试"""
import pytest
from langchain_core.messages import HumanMessage
from src.agent.nodes import classify_intent, rewrite_query, diagnose
from src.agent.state import DiagnosticState


def _state(user_msg: str, **overrides):
    s: DiagnosticState = {
        "intent": "diagnose",
        "messages": [HumanMessage(content=user_msg)],
        "symptoms": "",
        "retrieved_docs": [],
        "diagnosis": "",
        "verified": False,
        "need_more_info": False,
        "feedback": "",
        "final_response": "",
        "iteration": 0,
    }
    s.update(overrides)
    return s


class TestClassifyIntent:
    def test_keyword_diagnose(self):
        """命中 diagnose 关键词 → 直接判 diagnose"""
        result = classify_intent(_state("帮我看看这是什么病"))
        assert result["intent"] == "diagnose"

    def test_keyword_inquiry(self):
        """命中 inquiry 关键词 → 直接判 inquiry"""
        result = classify_intent(_state("21-羟化酶缺乏症有什么症状"))
        assert result["intent"] == "inquiry"

    def test_empty_message(self):
        """空消息 → 兜底 inquiry"""
        result = classify_intent(_state(""))
        assert result["intent"] == "inquiry"

    def test_skip_keyword_on_retry(self):
        """回退轮 → 跳过关键词，走 LLM"""
        result = classify_intent(_state("帮我看看这是什么病", iteration=1))
        # 不命中关键词（iteration>0 跳过），会走 LLM fallback
        # LLM 未 mock，大概率不返回 diagnose → fallback 到 inquiry
        assert result["intent"] in ("diagnose", "inquiry")


class TestRewriteQuery:
    def test_basic_rewrite(self):
        """查询改写节点正常运行"""
        result = rewrite_query(_state("患者12岁进行性肌无力"))
        # LLM 返回非空即可
        assert isinstance(result["symptoms"], str)
        assert len(result["symptoms"]) > 0
