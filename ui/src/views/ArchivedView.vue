<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { chatApi } from '@/services/chat'
import { ElMessage } from 'element-plus'

const convs = ref<any[]>([])
const loading = ref(false)

onMounted(loadList)

async function loadList() {
  loading.value = true
  try {
    const { data } = await chatApi.listConvs('archived')
    convs.value = data.items
  } finally {
    loading.value = false
  }
}

async function handleRestore(id: string) {
  await chatApi.updateConv(id, { status: 'active' })
  ElMessage.success('已恢复')
  await loadList()
}
</script>

<template>
  <div style="padding:24px">
    <h2 style="margin-bottom:16px">已归档</h2>
    <el-table :data="convs" v-loading="loading" stripe>
      <el-table-column prop="title" label="标题" min-width="300" />
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button text type="primary" @click="handleRestore(row.id)">恢复</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && convs.length === 0" description="暂无归档" />
  </div>
</template>
