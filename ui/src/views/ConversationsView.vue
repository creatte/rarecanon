<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { chatApi } from '@/services/chat'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const loading = ref(false)
const convs = ref<any[]>([])

onMounted(() => loadList())

async function loadList() {
  loading.value = true
  try {
    const { data } = await chatApi.listConvs()
    convs.value = data.items
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  const { data } = await chatApi.createConv()
  router.push(`/chat/${data.id}`)
}

async function handleArchive(id: string) {
  await ElMessageBox.confirm('确定归档此会话？', '提示', { type: 'warning' })
  await chatApi.updateConv(id, { status: 'archived' })
  ElMessage.success('已归档')
  await loadList()
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div class="conv-page">
    <div class="conv-header">
      <h2>会话列表</h2>
      <el-button type="primary" @click="handleCreate">新建会话</el-button>
    </div>
    <el-table :data="convs" v-loading="loading" stripe>
      <el-table-column prop="title" label="标题" min-width="200">
        <template #default="{ row }">
          <el-button text @click="router.push(`/chat/${row.id}`)">
            {{ row.title }}
          </el-button>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" width="180">
        <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button text type="danger" @click="handleArchive(row.id)">归档</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && convs.length === 0" description="暂无会话，点击上方按钮创建" />
  </div>
</template>

<style scoped>
.conv-page { padding: 24px; }
.conv-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
</style>
