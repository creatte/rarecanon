# Agent 诊断推理引擎

基于 LangGraph 的罕见病辅助诊断 Agent，两条链路：知识咨询（inquiry）和诊断推理（diagnose）。

## 架构概览

```
agent/
├── __init__.py   # 模块入口，自动初始化日志
├── state.py      # 状态定义（共享数据总线）
├── prompt.py     # 所有 LLM 提示词模板
├── tools.py      # 共享工具（日志、JSON解析、LLM客户端、关键词）
├── nodes.py      # 节点函数（每个节点是一个推理步骤）
├── edges.py      # 条件边（控制图流转方向）
├── graph.py      # 图组装 + 编译入口
├── run.py        # 本地测试入口
├── README.md     # 本文档
└── logs/         # 调试日志文件（.gitignore）
```

## 两条链路

### inquiry（知识咨询）

医生已知疾病名称，询问症状、病因、治疗等信息。

```
classify_intent → rewrite_query → retrieve → reply_inquiry → verify_inquiry → END
                        ↑                                                    │
                        └────────── 验证失败，回退重查（最多2轮）─────────────┘
```

| 节点 | 职责 | 输入 | 输出 |
|------|------|------|------|
| classify_intent | 判断意图 | messages | intent |
| rewrite_query | 去噪 + 同义扩展 | messages | symptoms |
| retrieve | RAG 检索知识库 | symptoms | retrieved_docs |
| reply_inquiry | 基于资料回答问题 | messages + retrieved_docs | final_response |
| verify_inquiry | 审核回复是否基于资料 | messages + retrieved_docs + final_response | verified + feedback |

### diagnose（诊断推理）

医生描述症状/体征/检查结果，系统给出鉴别诊断。

```
classify_intent → rewrite_query → retrieve → diagnose → verify → generate_final → END
      ↑              ↑                        ↑           │
      │              └──────── 证据不足 ───────┤           │
      └────── intent 错了 ────────────────────│           │
                                              └── 通过 ──→ generate_final
```

| 节点 | 职责 | 输入 | 输出 |
|------|------|------|------|
| classify_intent | 判断意图（第一轮关键词+LLM，回退轮纯LLM） | messages | intent |
| rewrite_query | 医生描述 → 检索查询词 | messages | symptoms |
| retrieve | 异步 RAG 检索 | symptoms | retrieved_docs |
| diagnose | 原始症状 + 资料 → 鉴别诊断 | messages + retrieved_docs | diagnosis |
| verify | 审查诊断：意图是否正确？证据是否充分？ | messages + intent + retrieved_docs + diagnosis | verified + need_more_info + feedback |
| generate_final | 诊断结论 → 专业可读回复 | messages + diagnosis | final_response + messages |

## State 字段说明

| 字段 | 类型 | 用途 |
|------|------|------|
| intent | `"inquiry" \| "diagnose"` | 当前链路 |
| messages | `list[BaseMessage]` | 对话历史（add_messages reducer） |
| symptoms | `str` | 改写后的检索查询词 |
| retrieved_docs | `list[str]` | RAG 召回文档内容 |
| diagnosis | `str` | 鉴别诊断结果（仅 diagnose） |
| verified | `bool` | 验证是否通过 |
| need_more_info | `bool` | false=证据不足, true=intent错了 |
| feedback | `str` | 验证失败的反馈信息 |
| final_response | `str` | 最终给用户的回复 |
| iteration | `int` | 当前回退轮次（上限2） |

## 条件边逻辑

```
classify_intent 后 ── intent=inquiry → rewrite_query
                   ── intent=diagnose → rewrite_query

retrieve 后      ── intent=inquiry → reply_inquiry
                   ── intent=diagnose → diagnose

verify_inquiry后 ── verified=true  → END
                   ── iteration>=2  → END
                   ── verified=false → rewrite_query（重查）

verify 后        ── verified=true  → generate_final
                   ── iteration>=2  → generate_final（强制结束）
                   ── need_more_info=true  → classify_intent（intent 错了）
                   ── need_more_info=false → rewrite_query（证据不足）
```

## 调试开关

`.env` 中 `DEBUG=true` 时，每个节点的输入/输出通过 `logger.debug` 输出到控制台和 `logs/agent.log` 文件，不消耗 token。

## 相关配置

| 环境变量 | 默认值 | 用途 |
|----------|--------|------|
| LLM_MODEL | deepseek-chat | LLM 模型名 |
| LLM_BASE_URL | https://api.deepseek.com | LLM API 地址（兼容 OpenAI 格式） |
| LLM_API_KEY | — | API 密钥 |
| DEBUG | false | 是否输出节点调试日志 |

## 使用方式

```python
from agent.graph import graph
from langchain_core.messages import HumanMessage

# 初始状态
state = {
    "messages": [HumanMessage(content="患者男12岁，进行性肌无力2年...")],
    "iteration": 0,
    # 其余字段有默认值，可不传
}

# 运行图
result = await graph.ainvoke(state)
print(result["final_response"])
```
