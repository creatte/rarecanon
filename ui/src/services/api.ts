/**
 * axios 实例 + 请求/响应拦截器
 *
 * 每个请求自动从 localStorage 读取 token 附加到 Authorization 头
 * 401 时清空 token 并跳转登录页
 */
import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,  // Agent 推理可能较慢，设 2 分钟
})

// 请求拦截：自动带 token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截：统一错误处理
api.interceptors.response.use(
  (res) => res,
  (err) => {
    // 用户主动取消的不弹错误
    if (axios.isCancel(err)) return Promise.reject(err)
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      router.push('/login')
      ElMessage.error('登录已过期，请重新登录')
    } else {
      ElMessage.error(err.response?.data?.detail || '请求失败')
    }
    return Promise.reject(err)
  },
)

export default api
