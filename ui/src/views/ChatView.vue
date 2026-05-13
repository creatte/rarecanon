<script setup lang="ts">
import { ref, nextTick, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { chatApi } from '@/services/chat'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const convId = ref((route.params.convId as string) || '')

const messages = ref<{ role: string; content: string }[]>([])
const inputText = ref('')
const sending = ref(false)
const chatBox = ref<HTMLDivElement>()

// 加载历史消息
onMounted(async () => {
  if (convId.value) {
    try {
      const { data } = await chatApi.getConv(convId.value)
      document.title = data.title + ' - RareCanon'
      console.log(convId.value)
      const res = await chatApi.getMessages(convId.value)
      messages.value = Array.isArray(res.data) ? res.data : []
      scrollBottom()
    } catch (err: any) {
      console.error('加载历史失败:', err?.response?.status, err?.response?.data)
      ElMessage.error('会话加载失败')
    }
  }
})

// URL 变化时（切换会话 / 点击新对话 / 浏览器前进后退）
watch(() => route.params.convId, async (newId) => {
  convId.value = (newId as string) || ''
  messages.value = []
  if (newId) {
    try {
      const { data } = await chatApi.getConv(newId as string)
      document.title = data.title + ' - RareCanon'
      const res = await chatApi.getMessages(newId as string)
      messages.value = Array.isArray(res.data) ? res.data : []
      scrollBottom()
    } catch (err: any) {
      console.error('加载历史失败:', err?.response?.status, err?.response?.data)
    }
  }
})

async function send() {
  const text = inputText.value.trim()
  if (!text || sending.value) return
  inputText.value = ''

  // 如果没有会话，先创建
  const needRedirect = !convId.value
  if (needRedirect) {
    const { data } = await chatApi.createConv()
    convId.value = data.id
  }

  messages.value.push({ role: 'user', content: text })
  scrollBottom()

  sending.value = true
  try {
    const { data } = await chatApi.sendMessage(convId.value, text)
    messages.value.push({ role: 'assistant', content: data.final_response })
    scrollBottom()
    // 消息发完再更新 URL，这样刷新页面能加载历史
    if (needRedirect) {
      router.replace(`/chat/${convId.value}`)
    }
  } catch {
    messages.value.push({ role: 'system', content: '发送失败，请重试' })
  } finally {
    sending.value = false
  }
}

function scrollBottom() {
  nextTick(() => {
    if (chatBox.value) {
      chatBox.value.scrollTop = chatBox.value.scrollHeight
    }
  })
}
</script>

<template>
  <div class="chat-page">
    <!-- 消息区域 -->
    <div class="chat-messages" ref="chatBox">
      <div v-if="messages.length === 0" class="empty-hint">
        输入病情描述，开始 AI 诊断
      </div>
      <div v-for="(m, i) in messages" :key="i" :class="['message', m.role]">
        <div class="msg-role">{{ m.role === 'user' ? '你' : m.role === 'assistant' ? 'AI 诊断' : '系统' }}</div>
        <div class="msg-content" v-html="m.content.replace(/\n/g, '<br>')" />
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="chat-input">
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="3"
        placeholder="输入病情描述，如：患者男12岁，进行性双下肢肌无力2年，CK 15000..."
        :disabled="sending"
        @keyup.enter.exact.prevent="send"
      />
      <el-button
        type="primary"
        :loading="sending"
        :disabled="!inputText.trim()"
        style="margin-top:8px"
        @click="send"
      >
        {{ sending ? '分析中...' : '发送' }}
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px);
}
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
.empty-hint {
  text-align: center;
  color: #999;
  margin-top: 200px;
  font-size: 16px;
}
.message {
  margin-bottom: 16px;
}
.msg-role {
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}
.msg-content {
  background: #f5f5f5;
  padding: 12px 16px;
  border-radius: 8px;
  line-height: 1.6;
  white-space: pre-wrap;
}
.message.user .msg-content {
  background: #e8f4fd;
}
.message.system .msg-content {
  background: #fff3cd;
  color: #856404;
}
.chat-input {
  padding: 16px 20px;
  border-top: 1px solid #e6e6e6;
  background: #fff;
}
</style>
