/** 会话 + 对话 API */
import api from './api'

export const chatApi = {
  // 会话
  createConv: (title = '新建会话') => api.post('/conversations', { title }),
  listConvs: (status = 'active') => api.get('/conversations', { params: { status } }),
  getConv: (id: string) => api.get(`/conversations/${id}`),
  updateConv: (id: string, data: { title?: string; status?: string }) =>
    api.patch(`/conversations/${id}`, data),
  deleteConv: (id: string) => api.delete(`/conversations/${id}`),

  // 消息历史
  getMessages: (convId: string) => api.get(`/conversations/${convId}/messages`),

  // 发送消息（支持取消）
  sendMessage: (convId: string, message: string, signal?: AbortSignal) =>
    api.post(`/chat/${convId}`, { message }, { signal }),

  /** SSE 流式发送消息，逐 token 推送 */
  streamMessage: (
    convId: string,
    message: string,
    onToken: (text: string) => void,
    onDone: (meta: any) => void,
    signal?: AbortSignal,
  ) => {
    const token = localStorage.getItem('token')
    return fetch(`/api/v1/chat/${convId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
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
        const lines = buffer.split('\n\n')
        buffer = lines.pop() || ''

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
