# 前端实施计划

> 技术栈：Vue 3 + TypeScript + Element Plus + Pinia + Axios + Vite

## 当前状态

- Vite 官方模板，Element Plus 已安装但未引入
- 无 API 对接，无认证页面，无业务组件

---

## Phase 1 — 地基搭建

### 1.1 引入 Element Plus + 配置 axios

- 全局注册 Element Plus（中文 locale）
- 配置 axios baseURL + 请求拦截器（自动带 token）
- vite.config.ts 配置代理转发 `/api` → `localhost:8000`

### 1.2 页面布局框架

- 登录前：空白布局
- 登录后：侧边栏导航 + 顶部用户信息 + 主内容区
- 新建 `layouts/DefaultLayout.vue`

**验证点：** 页面能正常渲染 Element Plus 组件，控制台无报错

---

## Phase 2 — 认证系统

### 2.1 登录/注册页面

- `views/LoginView.vue` — 登录表单（用户名 + 密码）
- `views/RegisterView.vue` — 注册表单（用户名 + 密码 + 邮箱）
- Element Plus 表单校验

### 2.2 Pinia 用户状态

- `stores/auth.ts` — 存储 token、用户信息
- `login()` / `register()` / `logout()` actions
- token 持久化到 localStorage（刷新不丢）

### 2.3 路由守卫

- `router/index.ts` — `beforeEach` 检查 token
- 未登录 → 强制跳转 `/login`
- 已登录访问登录页 → 跳转 `/`

**验证点：** 能注册 → 登录 → 拿到 token → 访问受保护页面

---

## Phase 3 — 核心业务页面

### 3.1 API 服务层

- `services/api.ts` — axios 实例 + 通用错误处理
- `services/auth.ts` — 登录/注册 API
- `services/chat.ts` — 会话 CRUD + 发送消息 API

### 3.2 会话列表页

- `views/ConversationsView.vue`
- 显示当前用户的所有活跃会话（列表）
- 创建新会话、归档会话
- 点击进入某个会话 → 跳转聊天页

### 3.3 聊天对话页

- `views/ChatView.vue`
- 对话历史展示（Messages 列表，区分 user/assistant）
- 输入框 + 发送按钮
- 调用 `POST /api/v1/chat/{conv_id}` → 显示回复

**验证点：** 能创建会话 → 发送诊断消息 → 看到 Agent 返回的诊断结果

---

## Phase 4 — 打磨完善

### 4.1 交互优化

- 发送消息时显示 loading（Agent 推理需要几十秒）
- 错误提示（网络异常、token 过期等）
- 空状态提示

### 4.2 样式调整

- 左侧边栏宽度、配色
- 消息气泡样式（用户/助手区分）
- 响应式考虑

**验证点：** 体验顺畅，错误有提示，loading 有反馈

---

## 目录结构（最终）

```
ui/src/
├── main.ts                    # 入口：注册 Element Plus + Pinia + Router
├── App.vue                    # 根组件
├── layouts/
│   └── DefaultLayout.vue      # 登录后的主布局
├── views/
│   ├── LoginView.vue          # 登录页
│   ├── RegisterView.vue       # 注册页
│   ├── ConversationsView.vue  # 会话列表
│   └── ChatView.vue           # 聊天页
├── router/
│   └── index.ts               # 路由 + 守卫
├── stores/
│   └── auth.ts                # 用户认证状态
├── services/
│   ├── api.ts                 # axios 实例
│   ├── auth.ts                # 认证 API
│   └── chat.ts                # 对话 API
└── assets/
    └── main.css               # 全局样式
```

---

## 学习路径

| Phase | 学到的核心概念 |
|-------|--------------|
| 1.1 | Vite 代理、Element Plus 全局注册、axios 拦截器 |
| 1.2 | Vue 布局、RouterView、组件嵌套 |
| 2.1 | 表单校验、双向绑定、Element Plus 表单组件 |
| 2.2 | Pinia store、localStorage 持久化 |
| 2.3 | 路由守卫、鉴权重定向 |
| 3.1 | axios 封装、前后端接口对接 |
| 3.2 | 列表渲染、条件渲染、事件处理 |
| 3.3 | 父子组件通信、异步数据加载、列表滚动 |
| 4.1 | loading 状态管理、错误兜底 |
