"""Agent 诊断评测脚本

逐条跑 test_queries.json，检查输出中是否包含 expected_mention 中的疾病名。
输出表格 + 按类型/难度分组的准确率。

用法：cd backend && python ../datasets/run_eval.py
"""
import json
import asyncio
import time
import sys
sys.path.insert(0, '.')  # 当前工作在 backend 目录

from src.agent.runner import AgentRunner


async def evaluate_one(runner: AgentRunner, case: dict) -> dict:
    start = time.time()
    try:
        uid = "eb8ac80d-a3ab-4d46-bc32-297972a8ed36"
        from uuid import uuid4
        cid = str(uuid4())  # 每条测试独立会话
        result = await runner.run(uid, cid, case["user_message"])
        final = result.get("final_response", "")
        hits = [m for m in case["expected_mention"] if m.lower() in final.lower()]
        ok = len(hits) > 0
        intent_ok = result.get("intent") == case["expected_intent"]
    except Exception as e:
        ok = False
        intent_ok = False
        hits = []
        final = f"{type(e).__name__}: {e!r}"[:200]
        print(f"       ERROR: {final}")
    elapsed = time.time() - start
    return {
        "id": case["id"],
        "type": case["type"],
        "difficulty": case.get("difficulty", "?"),
        "diagnosis_pass": ok,
        "intent_pass": intent_ok,
        "hits": hits,
        "expected": case["expected_mention"],
        "time_s": round(elapsed, 1),
    }


async def main():
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(script_dir, "test_queries.json"), encoding="utf-8") as f:
        cases = json.load(f)

    print(f"共 {len(cases)} 条测试，开始评估...\n")
    runner = AgentRunner()
    results = []

    for i, c in enumerate(cases):
        r = await evaluate_one(runner, c)
        results.append(r)
        status = "OK" if r["diagnosis_pass"] else "FAIL"
        print(f"  [{i+1:02d}] {r['id']} {c['type']} {c['difficulty']} → {status} ({r['time_s']}s)")
        if not r["diagnosis_pass"]:
            print(f"       期望: {r['expected']}  命中: {r['hits'] or '无'}")

    # 汇总
    total = len(results)
    diag_ok = sum(1 for r in results if r["diagnosis_pass"])
    intent_ok = sum(1 for r in results if r["intent_pass"])

    print(f"\n{'='*50}")
    print(f"  诊断准确率: {diag_ok}/{total} ({diag_ok/total*100:.1f}%)")
    print(f"  意图准确率: {intent_ok}/{total} ({intent_ok/total*100:.1f}%)")
    avg_time = sum(r["time_s"] for r in results) / total
    print(f"  平均耗时: {avg_time:.0f}s")

    # 按类型分组
    for t in ["典型诊断", "鉴别诊断", "知识查询", "信息不足", "边界测试"]:
        group = [r for r in results if r["type"] == t]
        if not group:
            continue
        ok = sum(1 for r in group if r["diagnosis_pass"])
        print(f"  {t}: {ok}/{len(group)} ({ok/len(group)*100:.0f}%)")

    # 按难度分组
    for d in ["简单", "中等", "困难"]:
        group = [r for r in results if r["difficulty"] == d]
        if not group:
            continue
        ok = sum(1 for r in group if r["diagnosis_pass"])
        print(f"  {d}: {ok}/{len(group)} ({ok/len(group)*100:.0f}%)")

    # 保存详细结果
    with open(os.path.join(script_dir, "eval_results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果已保存至 eval_results.json")


if __name__ == "__main__":
    asyncio.run(main())
