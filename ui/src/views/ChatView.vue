<script setup lang="ts">
import { ref, nextTick, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { marked } from 'marked'
import { chatApi } from '@/services/chat'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const convId = ref((route.params.convId as string) || '')
const convTitle = ref('')
const messages = ref<{ role: string; content: string }[]>([])
const inputText = ref('')
const sending = ref(false)
const chatBox = ref<HTMLDivElement>()
let abortCtrl: AbortController | null = null

onMounted(async () => {
  if (convId.value) await loadHistory(convId.value)
})

watch(() => route.params.convId, async (newId) => {
  convId.value = (newId as string) || ''
  messages.value = []
  if (newId) await loadHistory(newId as string)
})

async function loadHistory(id: string) {
  try {
    const { data } = await chatApi.getConv(id)
    convTitle.value = data.title
    document.title = data.title + ' - RareCanon'
    const res = await chatApi.getMessages(id)
    messages.value = Array.isArray(res.data) ? res.data : []
    scrollBottom()
  } catch { /* 忽略 */ }
}

async function send() {
  const text = inputText.value.trim()
  if (!text || sending.value) return
  inputText.value = ''

  const needRedirect = !convId.value
  if (needRedirect) {
    const { data } = await chatApi.createConv()
    convId.value = data.id
  }

  messages.value.push({ role: 'user', content: text })
  scrollBottom()

  abortCtrl = new AbortController()
  sending.value = true

  // 先塞空消息占位，边收边填充
  messages.value.push({ role: 'assistant', content: '' })
  const msgIdx = messages.value.length - 1
  scrollBottom()

  try {
    await chatApi.streamMessage(
      convId.value, text,
      (token: string) => {
        messages.value[msgIdx].content += token
        scrollBottom()
      },
      (meta: any) => {
        if (needRedirect) {
          const title = text.length > 30 ? text.slice(0, 30) + '…' : text
          chatApi.updateConv(convId.value, { title })
          convTitle.value = title
          router.replace(`/chat/${convId.value}`)
        }
      },
      abortCtrl.signal,
    )
  } catch (err: any) {
    if (err.name !== 'AbortError') {
      messages.value[msgIdx].content = '发送失败，请重试'
    }
  } finally {
    sending.value = false
    abortCtrl = null
  }
}

function stopSending() {
  if (abortCtrl) abortCtrl.abort()
}

function scrollBottom() {
  nextTick(() => {
    if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight
  })
}

function renderContent(text: string): string {
  return marked.parse(text, { breaks: true }) as string
}
</script>

<template>
  <div class="chat-page">
    <!-- 顶部标题 -->
    <div v-if="convTitle" class="chat-topbar">{{ convTitle }}</div>
    <!-- 消息区域 -->
    <div class="messages-area" ref="chatBox">
      <div v-if="messages.length === 0" class="welcome">
        <h2>RareCanon 罕见病诊断助手</h2>
        <p>输入病情描述，AI 将基于罕见病诊疗指南给出鉴别诊断</p>
      </div>
      <div v-for="(m, i) in messages" :key="i" class="msg-row" :class="m.role">
        <div class="msg-avatar">{{ m.role === 'user' ? '医' : 'AI' }}</div>
        <div class="msg-bubble">
          <div v-if="m.role === 'assistant' && m.content === ''" class="typing">
            思考中<span class="dots">...</span>
          </div>
          <div v-else class="msg-text" v-html="renderContent(m.content)" />
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="input-area">
      <div class="input-wrapper">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="2"
          placeholder="输入病情描述，如：患者男12岁，进行性双下肢肌无力2年，CK 15000..."
          :disabled="sending"
          resize="none"
          @keyup.enter.exact.prevent="send"
        />
        <el-button
          v-if="!sending"
          type="primary"
          :disabled="!inputText.trim()"
          class="send-btn"
          @click="send"
        >
          发送
        </el-button>
        <el-button
          v-else
          type="danger"
          class="send-btn"
          @click="stopSending"
        >
          停止
        </el-button>
      </div>
      <div class="input-hint">Enter 发送，Shift+Enter 换行</div>
    </div>
  </div>
</template>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #fff;
}

/* ── 顶部标题 ── */
.chat-topbar {
  text-align: center;
  padding: 12px;
  font-size: 14px;
  color: #888;
  border-bottom: 1px solid #f0f0f0;
  background: #fafafa;
}

/* ── 消息区 ── */
.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px 0;
}
.welcome {
  text-align: center;
  margin-top: 160px;
  color: #999;
}
.welcome h2 { font-size: 22px; color: #555; margin-bottom: 8px; }

.msg-row {
  max-width: 800px;
  margin: 0 auto;
  padding: 12px 24px;
  display: flex;
  gap: 12px;
  align-items: flex-start;
}
.msg-row.user { flex-direction: row-reverse; }

/* 头像 */
.msg-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
  color: #fff;
}
.msg-row.user .msg-avatar { background: #409EFF; }
.msg-row.assistant .msg-avatar { background: #67C23A; }
.msg-row.system .msg-avatar { background: #E6A23C; }

/* 气泡 */
.msg-bubble {
  padding: 12px 18px;
  border-radius: 12px;
  line-height: 1.7;
  font-size: 15px;
  max-width: calc(100% - 50px);
}
.msg-row.user .msg-bubble {
  background: #409EFF;
  color: #fff;
  border-bottom-right-radius: 4px;
}
.msg-row.assistant .msg-bubble {
  background: #f5f5f5;
  border-bottom-left-radius: 4px;
}
.msg-row.system .msg-bubble {
  background: #fdf6ec;
  color: #E6A23C;
}

.msg-text :deep(h1), .msg-text :deep(h2), .msg-text :deep(h3) { font-size: 17px; margin: 12px 0 6px; }
.msg-text :deep(h4) { font-size: 15px; margin: 8px 0 4px; }
.msg-text :deep(p) { margin: 0 0 6px; }
.msg-text :deep(ul), .msg-text :deep(ol) { padding-left: 22px; margin: 4px 0; }
.msg-text :deep(li) { margin: 2px 0; }
.msg-text :deep(hr) { border: none; border-top: 1px solid #ddd; margin: 12px 0; }
.msg-text :deep(strong) { color: inherit; font-weight: 600; }
.msg-row.user .msg-text :deep(strong) { color: #fff; }

.typing {
  color: #999;
}
.dots {
  animation: blink 1.4s infinite;
}
@keyframes blink {
  0%, 100% { opacity: 0.2; }
  50% { opacity: 1; }
}

/* ── 输入区 ── */
.input-area {
  border-top: 1px solid #e5e5e5;
  padding: 16px 24px 8px;
  background: #fff;
}
.input-wrapper {
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  gap: 8px;
  align-items: flex-end;
}
.send-btn {
  flex-shrink: 0;
}
.input-hint {
  text-align: center;
  font-size: 12px;
  color: #bbb;
  margin-top: 4px;
}
</style>
