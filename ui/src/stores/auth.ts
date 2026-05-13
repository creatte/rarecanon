/**
 * 用户认证状态
 *
 * token 存 localStorage 确保刷新不丢
 * user 基本信息同步缓存
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi, type LoginParams, type RegisterParams } from '@/services/auth'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  // ── 状态 ──
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

  // ── 是否登录 ──
  const isLoggedIn = () => !!token.value

  // ── 登录 ──
  const login = async (params: LoginParams) => {
    const { data } = await authApi.login(params)
    token.value = data.access_token
    localStorage.setItem('token', data.access_token)
    // 用 token 解析用户信息（简单存 username）
    user.value = { username: params.username }
    localStorage.setItem('user', JSON.stringify(user.value))
    router.push('/')
  }

  // ── 注册 ──
  const register = async (params: RegisterParams) => {
    const { data } = await authApi.register(params)
    token.value = data.access_token
    localStorage.setItem('token', data.access_token)
    user.value = { username: params.username }
    localStorage.setItem('user', JSON.stringify(user.value))
    router.push('/')
  }

  // ── 退出 ──
  const logout = () => {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    router.push('/login')
  }

  return { token, user, isLoggedIn, login, register, logout }
})
