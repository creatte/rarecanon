# 流式输出设计方案

> 当前状态：Agent 全部跑完才返回，用户长时间白等。
> 目标：像 ChatGPT 一样逐字显示，边生成边渲染。

---

## 核心原理：SSE（Server-Sent Events）

HTTP 单向流：服务端持续推数据，客户端用 `ReadableStream` 读取。

```
普通 HTTP:  Client ──req──→ Server ──完整响应──→ Client (等 60s)
SSE:       Client ──req──→ Server ──token1──→
                                ──token2──→
                                ──token3──→  Client (0.1s 就看到第一个字)
                                ──[DONE]──→
```

---

## 方案 A：只流最终回复（推荐起步）

改动量最小，只影响 `generate_final` 节点。用户看到"思考中"直到 LLM 开始输出回复。

### 后端改动

#### 1. chat 路由 → 改成 SSE

```python
# backend/src/api/routes/chat.py

from fastapi.responses import StreamingResponse
import json

@router.post("/{conv_id}")
async def chat_stream(conv_id: str, body: ChatRequest, user: User = Depends(get_current_user)):
    """SSE 流式对话"""
    return StreamingResponse(
        _generate(conv_id, body.message, str(user.id)),
        media_type="text/event-stream",
    )

async def _generate(conv_id: str, message: str, user_id: str):
    """生成器函数，逐 token 推送"""
    runner = AgentRunner()
    
    # 阶段1：Agent 推理（思考阶段，前端显示 loading）
    result = await runner.run(user_id, conv_id, message)
    
    # 阶段2：逐 token 流式输出最终回复
    # 用 LLM 直接 stream 回复内容
    # 注意：这里简化处理——把 final_response 逐 token 发送
    text = result["final_response"]
    for i in range(0, len(text), 5):  # 每 5 个字推一次
        chunk = text[i:i+5]
        yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.02)  # 模拟打字效果
    
    # 附带元数据
    yield f"data: {json.dumps({'type': 'done', 'intent': result['intent'], 'verified': result['verified']}, ensure_ascii=False)}\n\n"
```

**问题：** 上面是假流——Agent 全跑完才把结果切片发送。真正流式需要 `llm.stream()`：

```python
# 真正的流式：generate_final 节点内部
def generate_final_stream(state: DiagnosticState):
    llm = get_llm()
    prompt = FINAL_RESPONSE.format(
        user_message=get_user_message(state),
        diagnosis=state["diagnosis"],
    )
    # stream() 返回迭代器，每个 chunk 是一个 token
    return llm.stream(prompt, max_tokens=1024)
    # 这会返回一个生成器，在 SSE 里逐 chunk yield
```

**真正流式的完整实现：**

```python
async def _generate(conv_id: str, message: str, user_id: str):
    runner = AgentRunner()
    
    # Step 1-5: Agent 跑 graph（classify → rewrite → retrieve → diagnose → verify）
    # 直接调 runner 但不拿 final_response
    state = await runner._build_state(user_id, conv_id, message)
    state = await graph.ainvoke(state, config={"run_name": "diagnose"})
    
    # 只拿到 diagnosis（verify 已通过），不拿 final_response
    # Step 6: 流式 generate_final
    llm = get_llm()
    prompt = FINAL_RESPONSE.format(
        user_message=message,
        diagnosis=state["diagnosis"],
    )
    
    async for chunk in llm.astream(prompt, max_tokens=1024):
        if chunk.content:
            yield f"data: {json.dumps({'type': 'token', 'content': chunk.content}, ensure_ascii=False)}\n\n"
    
    # 结束信号
    yield f"data: {json.dumps({'type': 'done', 'intent': state['intent'], 'verified': state['verified']}, ensure_ascii=False)}\n\n"
```

**关键函数签名对照：**

| 方法 | 返回 | 用途 |
|------|------|------|
| `llm.invoke(prompt)` | 完整 AIMessage | 等全部生成完 |
| `llm.stream(prompt)` | 同步迭代器 `Iterator[Chunk]` | 同步逐 token |
| `llm.astream(prompt)` | 异步迭代器 `AsyncIterator[Chunk]` | 异步逐 token（FastAPI 用这个） |

### 前端改动

#### 2. 新增流式请求方法

```typescript
// ui/src/services/chat.ts

export const chatApi = {
  // ... 现有方法 ...

  /** SSE 流式发送消息 */
  streamMessage: (
    convId: string,
    message: string,
    onToken: (text: string) => void,      // 每收到一个 token
    onDone: (meta: any) => void,          // 全部完成时
    signal?: AbortSignal,
  ) => {
    const token = localStorage.getItem('token')
    
    return fetch(`/api/v1/chat/${convId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ message }),
      signal,
    }).then(async (res) => {
      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        buffer += decoder.decode(value, { stream: true })
        // SSE 格式: "data: {...}\n\n"
        const lines = buffer.split('\n\n')
        buffer = lines.pop() || ''  // 最后一段可能不完整
        
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const data = JSON.parse(line.slice(6))
          if (data.type === 'token') {
            onToken(data.content)
          } else if (data.type === 'done') {
            onDone(data)
          }
        }
      }
    })
  },
}
```

#### 3. ChatView 改造 send 函数

```typescript
// ui/src/views/ChatView.vue
// 核心改动：send() 函数中，把 sendMessage 替换为 streamMessage

async function send() {
  // ... 前面不变：取 text、创建会话、推送 user 消息 ...

  // 先塞一条空的 assistant 消息，边接收边填充
  messages.value.push({ role: 'assistant', content: '' })
  const idx = messages.value.length - 1
  scrollBottom()

  abortCtrl = new AbortController()
  sending.value = true

  try {
    await chatApi.streamMessage(
      convId.value,
      text,
      // onToken: 每收到一段就追加到消息尾部
      (token: string) => {
        messages.value[idx].content += token
        scrollBottom()
      },
      // onDone: 全部完成
      (meta: any) => {
        if (needRedirect) router.replace(`/chat/${convId.value}`)
      },
      abortCtrl.signal,
    )
  } catch (err: any) {
    if (err.name !== 'AbortError') {
      messages.value[idx].content = '发送失败，请重试'
    }
  } finally {
    sending.value = false
    abortCtrl = null
  }
}
```

---

## 方案 B：全程流（以后升级）

每个 Agent 节点都推送状态，用户看到每一步在干什么。

### SSE 事件格式

```
data: {"type": "node_start", "node": "classify_intent", "label": "分析意图..."}
data: {"type": "node_end",   "node": "classify_intent", "result": "diagnose"}
data: {"type": "node_start", "node": "rewrite_query",  "label": "优化检索词..."}
data: {"type": "node_end",   "node": "rewrite_query",  "result": "进行性肌无力 儿童..."}
data: {"type": "node_start", "node": "retrieve",       "label": "检索知识库..."}
data: {"type": "node_end",   "node": "retrieve",       "result": "召回8条文档"}
data: {"type": "node_start", "node": "diagnose",       "label": "鉴别诊断..."}
data: {"type": "node_end",   "node": "diagnose",       "result": "# 关键发现..."}
data: {"type": "node_start", "node": "verify",         "label": "验证诊断..."}
data: {"type": "node_end",   "node": "verify",         "result": "通过"}
data: {"type": "token", "content": "根据您提供的"}
data: {"type": "token", "content": "临床信息"}
data: {"type": "token", "content": "，..."}
data: {"type": "done", "intent": "diagnose", "verified": true}
```

### 后端：用 LangGraph 的 astream_events

```python
# backend/src/api/routes/chat.py
from langgraph.config import get_stream_writer

async def _generate_full_stream(conv_id: str, message: str, user_id: str):
    """全程流版本"""
    runner = AgentRunner()
    state = await runner._build_state(user_id, conv_id, message)
    
    # astream_events 捕获每个节点的开始/结束事件
    async for event in graph.astream_events(state, version="v2"):
        kind = event["event"]
        name = event.get("name", "")
        
        if kind == "on_chain_start" and name in NODE_LABELS:
            yield f"data: {json.dumps({'type': 'node_start', 'node': name, 'label': NODE_LABELS[name]}, ensure_ascii=False)}\n\n"
        
        elif kind == "on_chain_end" and name in NODE_LABELS:
            output = event["data"].get("output", {})
            yield f"data: {json.dumps({'type': 'node_end', 'node': name, 'result': str(output)[:200]}, ensure_ascii=False)}\n\n"
        
        elif kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if chunk.content:
                yield f"data: {json.dumps({'type': 'token', 'content': chunk.content}, ensure_ascii=False)}\n\n"
    
    # 完成后查最终状态
    final_state = await graph.aget_state(...)
    yield f"data: {json.dumps({'type': 'done', 'intent': final_state['intent'], 'verified': final_state['verified']}, ensure_ascii=False)}\n\n"

# 节点中英文标签
NODE_LABELS = {
    "classify_intent": "分析意图...",
    "rewrite_query":  "优化检索词...",
    "retrieve":       "检索知识库...",
    "diagnose":       "鉴别诊断推理...",
    "verify":         "验证诊断结论...",
    "generate_final": "生成诊断报告...",
    "reply_inquiry":  "查询知识库...",
}
```

**关键 API：** `graph.astream_events(state, version="v2")`
- `on_chain_start` / `on_chain_end` — 节点的开始和结束
- `on_chat_model_stream` — LLM 流式输出的每个 token

### 前端改动

```typescript
// ChatView.vue 中增加节点状态显示

const nodeStatus = ref('')  // 当前正在执行的节点名称

// streamMessage 增加 onNode 回调
await chatApi.streamMessage(convId.value, text, {
  onToken: (token) => { messages.value[idx].content += token },
  onNode: (node, label) => { nodeStatus.value = label },  // ← 新增
  onDone: (meta) => { nodeStatus.value = '' },
})

// 模板里显示：
// <div v-if="nodeStatus" class="node-status">{{ nodeStatus }}</div>
```

---

## 两种方案对比

| | 方案 A | 方案 B |
|---|--------|--------|
| 改动量 | 后端 ~30 行，前端 ~40 行 | 后端 ~60 行，前端 ~50 行 |
| 用户体验 | 思考 → 逐字显示 | 思考 → 每步可见 → 逐字显示 |
| 实现难度 | 低 | 中 |
| 需改动的文件 | chat.py, chat.ts, ChatView.vue | 同上 + nodes.py |
| 关键 API | `llm.astream()` | `graph.astream_events()` |
| 调试难度 | 低 | 需要熟悉 LangGraph 事件模型 |

---

## 建议路径

```
当前 → 方案 A（先让回复流起来）
     → 方案 B（展示推理过程，提升信任感）
```

方案 A 已经在 `ChatView.vue` 里留好了"思考中…"动效，接入流式后自然衔接。
