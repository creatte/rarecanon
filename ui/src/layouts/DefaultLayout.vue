<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { chatApi } from '@/services/chat'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const route = useRoute()
import ProfileDialog from '@/components/ProfileDialog.vue'

const convs = ref<any[]>([])
const collapsed = ref(false)
const showProfile = ref(false)
const username = ref(JSON.parse(localStorage.getItem('user') || '{}').username || '用户')

async function loadConvs() {
  try {
    const { data } = await chatApi.listConvs()
    convs.value = data.items
  } catch { /* 忽略 */ }
}

onMounted(loadConvs)
watch(() => route.path, loadConvs)

async function handleRename(c: any) {
  try {
    const { value } = await ElMessageBox.prompt('新标题', '重命名', {
      inputValue: c.title,
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })
    if (value) {
      await chatApi.updateConv(c.id, { title: value })
      ElMessage.success('已重命名')
      await loadConvs()
    }
  } catch { /* 取消 */ }
}

async function handleArchive(c: any) {
  try {
    await chatApi.updateConv(c.id, { status: 'archived' })
    ElMessage.success('已归档')
    if (route.params.convId === c.id) router.push('/chat')
    await loadConvs()
  } catch { /* 忽略 */ }
}

async function handleDelete(c: any) {
  try {
    await ElMessageBox.confirm(`确定删除"${c.title}"？`, '删除会话', {
      type: 'warning',
      confirmButtonText: '删除',
    })
    await chatApi.updateConv(c.id, { status: 'deleted' })
    ElMessage.success('已删除')
    if (route.params.convId === c.id) router.push('/chat')
    await loadConvs()
  } catch { /* 取消 */ }
}

function handleLogout() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  router.push('/login')
}

function truncate(str: string, max = 20) {
  return str.length > max ? str.slice(0, max) + '…' : str
}
</script>

<template>
  <div class="app-layout">
    <!-- 侧边栏 -->
    <aside class="sidebar" :class="{ collapsed }">
      <div class="sidebar-top">
        <div class="logo" @click="router.push('/chat')">
          <span v-if="!collapsed">RareCanon</span>
          <span v-else>RC</span>
        </div>
        <el-button class="new-chat-btn" @click="router.push('/chat')" :icon="collapsed ? '' : undefined">
          {{ collapsed ? '+' : '+ 新对话' }}
        </el-button>
        <nav class="conv-list">
          <div
            v-for="c in convs"
            :key="c.id"
            class="conv-item"
            :class="{ active: route.params.convId === c.id }"
            @click="router.push(`/chat/${c.id}`)"
          >
            <span v-if="!collapsed" class="conv-title">{{ truncate(c.title) }}</span>
            <el-dropdown v-if="!collapsed" trigger="click" :hide-on-click="false" class="conv-menu">
              <span class="dots" @click.stop>⋯</span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="handleRename(c)">重命名</el-dropdown-item>
                  <el-dropdown-item @click="handleArchive(c)">归档</el-dropdown-item>
                  <el-dropdown-item @click="handleDelete(c)" style="color:red">删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
          <div style="padding: 8px 16px">
            <el-button v-if="!collapsed" text size="small" style="color:#999" @click="router.push('/archived')">
              已归档 →
            </el-button>
          </div>
        </nav>
      </div>
      <div class="sidebar-bottom">
        <el-dropdown trigger="click" placement="top-start">
          <div class="user-area">
            <span class="user-avatar">医</span>
            <span v-if="!collapsed" class="user-name">{{ username }}</span>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="showProfile = true">个人信息</el-dropdown-item>
              <el-dropdown-item @click="handleLogout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button text class="collapse-btn" @click="collapsed = !collapsed">
          {{ collapsed ? '▶' : '◀' }}
        </el-button>
      </div>
    </aside>

    <!-- 主内容 -->
    <main class="main-content">
      <RouterView />
    </main>

    <ProfileDialog v-model="showProfile" />
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
}

/* ── 侧边栏 ── */
.sidebar {
  width: 260px;
  background: #f5f5f5;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e5e5e5;
  transition: width 0.2s;
  flex-shrink: 0;
}
.sidebar.collapsed { width: 60px; }

.sidebar-top { flex: 1; overflow: hidden; }
.sidebar-bottom {
  padding: 8px;
  border-top: 1px solid #e5e5e5;
  display: flex;
  justify-content: space-between;
}

.logo {
  padding: 16px;
  font-size: 18px;
  font-weight: 600;
  cursor: pointer;
  color: #333;
}

.new-chat-btn {
  margin: 8px 12px;
  width: calc(100% - 24px);
}

.conv-list {
  overflow-y: auto;
  margin-top: 8px;
}
.conv-item {
  padding: 10px 16px;
  cursor: pointer;
  font-size: 14px;
  color: #555;
  border-radius: 6px;
  margin: 2px 8px;
  white-space: nowrap;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.conv-item:hover { background: #e8e8e8; }
.conv-item.active { background: #dcdcdc; font-weight: 500; color: #222; }
.conv-title { flex: 1; overflow: hidden; text-overflow: ellipsis; }
.dots {
  padding: 0 4px;
  font-size: 16px;
  color: #999;
  opacity: 0;
  transition: opacity 0.15s;
  cursor: pointer;
}
.conv-item:hover .dots { opacity: 1; }
.dots:hover { color: #333; }

.collapse-btn { color: #888; font-size: 13px; }
.user-area {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 8px;
  cursor: pointer;
}
.user-area:hover { background: #e8e8e8; }
.user-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: #409EFF;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  flex-shrink: 0;
}
.user-name {
  font-size: 14px;
  color: #333;
}

/* ── 主区域 ── */
.main-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
</style>
