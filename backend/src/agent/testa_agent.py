"""本地测试入口"""
import asyncio
from .graph import graph
from langchain_core.messages import HumanMessage
from .nodes import _get_llm

async def main():
    state = {
        "messages": [HumanMessage(content="患者男12岁，进行性双下肢肌无力2年，Gower征阳性，CK显著升高15000U/L")],
        "iteration": 0,
    }
    result = await graph.ainvoke(state)
    print("=" * 50)
    print(result.get("final_response", "无输出"))
    print("=" * 50)
    print("intent:", result.get("intent"))
    print("verified:", result.get("verified"))
    print("iteration:", result.get("iteration"))


if __name__ == "__main__":
    llm = _get_llm()
    print(llm.invoke("回复: hello").content)
    asyncio.run(main())
