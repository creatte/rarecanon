import { createRouter, createWebHistory } from 'vue-router'
import DefaultLayout from '@/layouts/DefaultLayout.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: DefaultLayout,
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          redirect: '/conversations',
        },
        {
          path: 'conversations',
          name: 'conversations',
          component: () => import('@/views/ConversationsView.vue'),
        },
        {
          path: 'chat',
          name: 'chat',
          component: () => import('@/views/ChatView.vue'),
        },
        {
          path: 'chat/:convId',
          name: 'chat-detail',
          component: () => import('@/views/ChatView.vue'),
        },
        {
          path: 'archived',
          name: 'archived',
          component: () => import('@/views/ArchivedView.vue'),
        },
      ],
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/RegisterView.vue'),
    },
  ],
})

// 路由守卫：未登录 → 跳登录页
router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    return '/login'
  }
  // 已登录时访问登录/注册页 → 跳首页
  if (token && (to.path === '/login' || to.path === '/register')) {
    return '/'
  }
})

export default router
