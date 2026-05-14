# RareCanon — 面向医生的罕见病智能辅助诊断系统

基于 LangGraph + RAG 的罕见病辅助诊断平台。资料源于罕见病诊疗指南，支持诊断推理和知识咨询两条链路，含长短期记忆、流式输出、会话隔离。

---

## 1. 项目架构

```
┌─────────────────────────────────────┐
│     前端 (Vue 3 + TypeScript)       │
│     Element Plus 组件库              │
└────────────────┬────────────────────┘
                 │ SSE 流式 + REST API
┌────────────────▼────────────────────┐
│      后端 API (FastAPI)             │
│  认证 │ Agent 推理 │ RAG │ 记忆 │ 会话 │
└───┬──────────────────┬──────────────┘
    │                   │
┌───▼──────┐   ┌────────▼──────┐
│PostgreSQL│   │    Redis 7    │
│+pgvector │   │  缓存/短期记忆  │
└──────────┘   └───────────────┘
```

---

## 2. 目录结构（实际）

```
RareCanon/
├── backend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── main.py              # FastAPI 入口
│   │   │   ├── deps.py              # 依赖注入
│   │   │   ├── routes/
│   │   │   │   ├── auth.py          # 注册/登录/个人信息/改密码
│   │   │   │   ├── chat.py          # SSE 流式对话
│   │   │   │   ├── conversation.py  # 会话 CRUD + 消息历史
│   │   │   │   └── rag.py           # 知识库检索
│   │   │   └── middleware/
│   │   │       └── auth_middleware.py  # 全局认证兜底
│   │   ├── core/
│   │   │   ├── config.py            # 全部环境变量
│   │   │   ├── database.py          # PostgreSQL 异步连接池
│   │   │   └── security.py          # JWT + bcrypt
│   │   ├── models/                  # ORM 模型 (User/Conversation/Message/Document/LongTermMemory)
│   │   ├── schemas/                 # Pydantic 模型
│   │   ├── rag/
│   │   │   ├── embedding.py         # BGE-M3 (FlagEmbedding)
│   │   │   └── retrieval.py         # 混合检索 (dense + sparse)
│   │   ├── agent/
│   │   │   ├── state.py             # DiagnosticState
│   │   │   ├── prompt.py            # 全部提示词模板
│   │   │   ├── tools.py             # LLM/日志/JSON解析/关键词
│   │   │   ├── nodes.py             # 节点函数 (7个)
│   │   │   ├── edges.py             # 条件边
│   │   │   ├── graph.py             # StateGraph 组装
│   │   │   ├── runner.py            # AgentRunner (记忆加载 + 流式输出)
│   │   │   └── run.py               # 本地测试入口
│   │   ├── memory/
│   │   │   ├── short_term.py        # Redis 滑动窗口 + 渐进式摘要
│   │   │   └── long_term.py         # PG 向量存储 + LLM 摘要
│   │   └── session/
│   │       └── manager.py           # 会话 CRUD + 双写 (Redis+PG)
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_agent/
│   │   └── test_api/
│   └── requirements.txt
│
├── ui/                              # 前端 (Vue 3 + TS)
│   └── src/
│       ├── layouts/
│       │   └── DefaultLayout.vue    # DeepSeek 风格侧边栏布局
│       ├── views/
│       │   ├── LoginView.vue
│       │   ├── RegisterView.vue
│       │   ├── ChatView.vue         # 对话页（流式渲染 + 气泡）
│       │   ├── ConversationsView.vue
│       │   └── ArchivedView.vue
│       ├── components/
│       │   └── ProfileDialog.vue    # 个人信息弹窗
│       ├── services/
│       │   ├── api.ts               # axios 实例 + 拦截器
│       │   ├── auth.ts
│       │   └── chat.ts              # SSE 流式接收
│       ├── stores/
│       │   └── auth.ts              # Pinia 认证状态
│       └── router/
│           └── index.ts             # 路由守卫
│
├── datasets/
│   └── test_queries.json            # 15 条测试查询
├── docs/                            # 技术文档
│   ├── frontend-plan.md
│   ├── long-term-memory-strategies.md
│   ├── streaming-output-design.md
│   └── query-strategy-comparison.md
└── .env
```

---

## 3. 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + TypeScript + Element Plus + Pinia + marked |
| 后端 | Python 3.11 / FastAPI + SQLAlchemy async |
| Agent | LangGraph (StateGraph) + LangChain |
| LLM | 兼容 OpenAI 格式（DeepSeek / MiMo / 任意） |
| Embedding | BAAI/bge-m3 (FlagEmbedding, 1024 维) |
| 向量库 | pgvector (PostgreSQL 扩展) |
| 缓存 | Redis 7 |
| 认证 | JWT (access + refresh) |

---

## 4. Agent 两条链路

### 诊断链路 (diagnose)

```
classify_intent → rewrite_query → retrieve → diagnose → verify → generate_final
      ↑              ↑                       ↑           │
      │              └── 证据不足 ────────────┤           │
      └── intent 错了 ───────────────────────│           │
                                             └── 通过 → 最终回复
```

### 知识咨询链路 (inquiry)

```
classify_intent → rewrite_query → retrieve → reply_inquiry → verify_inquiry → END
                                                 ↑
                                        验证失败回到 rewrite_query
```

---

## 5. API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 注册 |
| POST | `/api/v1/auth/login` | 登录 |
| POST | `/api/v1/auth/refresh` | 刷新 token |
| GET | `/api/v1/auth/me` | 当前用户信息 |
| PUT | `/api/v1/auth/me` | 更新个人信息 |
| PUT | `/api/v1/auth/password` | 修改密码 |
| POST | `/api/v1/conversations` | 创建会话 |
| GET | `/api/v1/conversations` | 会话列表 (?status=active/archived) |
| GET | `/api/v1/conversations/{id}` | 会话详情 |
| PATCH | `/api/v1/conversations/{id}` | 更新标题/状态 |
| DELETE | `/api/v1/conversations/{id}` | 软删除 |
| GET | `/api/v1/conversations/{id}/messages` | 消息历史 |
| POST | `/api/v1/chat/{id}` | 发消息 (SSE 流式返回) |
| GET | `/api/v1/rag/search` | 知识库检索 |

---

## 6. 功能清单

- [x] 注册/登录/JWT 认证 + 全局中间件兜底
- [x] RAG 知识库检索 (BGE-M3 dense+sparse)
- [x] Agent 诊断推理 (LangGraph, 双链路 + 验证 + 自纠正)
- [x] 短期记忆 (Redis 滑动窗口 20 轮 2h TTL)
- [x] 长期记忆 (归档时 LLM 摘要 → pgvector 存储)
- [x] 会话管理 (CRUD + 归档/恢复 + 双写 Redis+PG)
- [x] Chat API 流式 SSE 输出
- [x] 前端完整 (DeepSeek 风格 + 个人信息弹窗)
- [x] 基础测试 (agent 节点 + API 集成)
- [ ] Docker 部署

---

## 7. 快速开始

```bash
# 1. 配置
cp .env.example .env   # 编辑填入 LLM_API_KEY 等

# 2. 初始化数据库
psql -U postgres -c "CREATE DATABASE rarecanon;"
psql -U postgres -d rarecanon -f backend/src/scripts/init_db.sql

# 3. 启动 Redis
docker run -d --name redis -p 6379:6379 redis:7

# 4. 启动后端
cd backend
pip install -r requirements.txt
uvicorn src.api.main:app --reload --port 8000

# 5. 启动前端
cd ui
npm install
npm run dev

# 6. 导入知识库
cd backend
python src/scripts/ingest_docs.py
```

---

## 8. 路线图

- [x] Phase 1-3: 后端 + RAG + Agent
- [x] Phase 4: 记忆 + 会话管理
- [x] Phase 5: Chat API + 前端
- [x] Phase 6: 测试
- [ ] Phase 7: Docker 化
