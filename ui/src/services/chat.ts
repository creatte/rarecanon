/** 会话 + 对话 API */
import api from './api'

export const chatApi = {
  // 会话
  createConv: (title = '新建会话') => api.post('/conversations', { title }),
  listConvs: () => api.get('/conversations'),
  getConv: (id: string) => api.get(`/conversations/${id}`),
  updateConv: (id: string, data: { title?: string; status?: string }) =>
    api.patch(`/conversations/${id}`, data),
  deleteConv: (id: string) => api.delete(`/conversations/${id}`),

  // 消息历史
  getMessages: (convId: string) => api.get(`/conversations/${convId}/messages`),

  // 发送消息
  sendMessage: (convId: string, message: string) =>
    api.post(`/chat/${convId}`, { message }),
}
