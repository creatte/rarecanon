/** 认证相关 API */
import api from './api'

export interface LoginParams {
  username: string
  password: string
}

export interface RegisterParams {
  username: string
  password: string
  email: string
}

export const authApi = {
  login: (data: LoginParams) => api.post('/auth/login', data),
  register: (data: RegisterParams) => api.post('/auth/register', data),
  getProfile: () => api.get('/auth/me'),
  changePassword: (oldPassword: string, newPassword: string) =>
    api.put('/auth/password', { old_password: oldPassword, new_password: newPassword }),
  updateProfile: (data: { hospital?: string; department?: string }) =>
    api.put('/auth/me', data),
}
